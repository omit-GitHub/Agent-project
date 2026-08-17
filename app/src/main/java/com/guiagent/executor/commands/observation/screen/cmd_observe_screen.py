# -*- coding: utf-8 -*-
"""observe_screen — 纯观察，返回当前页面可供 Agent 决策的元素。

设计原则：
  - 纯观察，不改变设备状态（不 tap、不滑动）
  - 返回 dump_status 和 ocr_status，说明数据可用性
  - 计算 screen_version，用于后续点击时校验
  - 提取可操作候选容器（clickable 祖先节点）
  - 融合 dump 和 OCR，返回统一元素列表

工作流：
  1. 获取当前包名、Activity、屏幕尺寸
  2. 截图并计算哈希
  3. dump UI 树并计算哈希
  4. 组合为 screen_version
  5. 提取可操作候选容器（clickable 祖先）
  6. 对截图运行 OCR
  7. 融合两者，返回统一元素列表

返回格式：
  {
    "screen_version": "pkg:activity:shotHash:treeHash",
    "package": "com.example.video",
    "activity": "PlayerActivity",
    "screen_size": {"width": 1280, "height": 800},
    "dump_status": "ok|partial|unavailable",
    "ocr_status": "ok|empty|failed",
    "elements": [...]
  }
"""
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from send import send
from common.utils import success_with_data, error
from observation.observation_cache import update_observation


# ─────────────────────── 屏幕信息采集 ───────────────────────

def get_screen_info():
    """获取当前屏幕基本信息（包名、Activity、尺寸）。"""
    try:
        resp = send({"id": "obs_ping", "op": "ping", "args": {}})
        if not resp.get("ok"):
            return None

        data = resp.get("data", {})
        return {
            "package": data.get("package", ""),
            "activity": data.get("activity", ""),
            "screen": data.get("screen", {"width": 1280, "height": 800}),
        }
    except Exception as e:
        print(f"[observe_screen] 获取屏幕信息失败: {e}")
        return None


def capture_screenshot():
    """截图并返回 (image_bytes, hash)。失败返回 (None, None)。"""
    import subprocess
    import tempfile

    try:
        # 截图
        result = subprocess.run(
            ["adb", "exec-out", "screencap", "-p"],
            capture_output=True,
            timeout=5
        )
        if result.returncode != 0:
            return None, None

        image_bytes = result.stdout
        if not image_bytes:
            return None, None

        # 计算哈希
        shot_hash = hashlib.md5(image_bytes).hexdigest()[:12]
        return image_bytes, shot_hash

    except Exception as e:
        print(f"[observe_screen] 截图失败: {e}")
        return None, None


def dump_ui_tree(depth=6):
    """dump UI 树，返回 (tree, hash, status)。

    status: "ok" | "partial" | "unavailable"
    """
    try:
        resp = send({
            "id": "obs_dump",
            "op": "dump",
            "args": {
                "depth": depth,
                "include": ["id", "text", "bounds", "clickable", "enabled", "desc", "cls", "pkg"]
            }
        })

        if not resp.get("ok"):
            return None, None, "unavailable"

        tree = resp.get("data", {}).get("window")
        if tree is None:
            return None, None, "unavailable"

        # 检查是否有有效节点
        node_count = count_nodes(tree)
        if node_count == 0:
            return tree, "empty", "partial"

        # 计算树哈希
        tree_json = json.dumps(tree, sort_keys=True, ensure_ascii=False)
        tree_hash = hashlib.md5(tree_json.encode()).hexdigest()[:12]

        # 判断状态：如果节点太少，可能是 partial
        status = "ok" if node_count > 10 else "partial"

        return tree, tree_hash, status

    except Exception as e:
        print(f"[observe_screen] dump 失败: {e}")
        return None, None, "unavailable"


def count_nodes(node):
    """递归统计节点数量。"""
    if node is None:
        return 0
    count = 1
    for child in node.get("children", []):
        count += count_nodes(child)
    return count


# ─────────────────────── 可操作候选容器提取 ───────────────────────

def find_clickable_ancestors(node, results=None, path=None):
    """提取所有可操作候选容器。

    对每个节点：
      - 如果 clickable=true，它是候选容器
      - 收集其内部子节点的 text、desc、resource_id 等证据

    返回: list of {
        "bounds": {...},
        "clickable": True,
        "enabled": True,
        "evidence": {
            "text": "...",
            "content_desc": "...",
            "resource_id": "...",
            "child_texts": [...]
        }
    }
    """
    if results is None:
        results = []
    if path is None:
        path = []

    if node is None:
        return results

    # 收集当前节点的证据
    evidence = {
        "text": node.get("text", ""),
        "content_desc": node.get("desc", ""),
        "resource_id": node.get("id", ""),
        "class": node.get("cls", ""),
        "child_texts": [],
    }

    # 收集子节点文本
    def collect_child_texts(n, depth=0):
        if depth > 3:  # 只收集 3 层内的文本
            return
        text = n.get("text", "")
        if text and text not in evidence["child_texts"]:
            evidence["child_texts"].append(text)
        for child in n.get("children", []):
            collect_child_texts(child, depth + 1)

    collect_child_texts(node)

    # 如果当前节点可点击，加入候选
    if node.get("clickable", False) and node.get("enabled", True):
        bounds = node.get("bounds")
        if bounds:
            results.append({
                "bounds": bounds,
                "clickable": True,
                "enabled": node.get("enabled", True),
                "evidence": evidence,
            })

    # 递归处理子节点
    for child in node.get("children", []):
        find_clickable_ancestors(child, results, path + [node])

    return results


# ─────────────────────── OCR ───────────────────────

def run_ocr_on_image(image_bytes):
    """对截图运行 OCR，返回 (items, status)。

    items: list of {text, bounds, confidence}
    status: "ok" | "empty" | "failed"
    """
    if not image_bytes:
        return [], "failed"

    try:
        from rapidocr_onnxruntime import RapidOCR
        import tempfile

        # 写入临时文件
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(image_bytes)
            temp_path = f.name

        try:
            engine = RapidOCR()
            result, _ = engine(temp_path)

            if not result:
                return [], "empty"

            items = []
            for item in result:
                box = item[0]
                text = item[1].strip()
                confidence = float(item[2])

                if not text:
                    continue

                # 过滤明显噪声（太短的可能是误识别）
                if len(text) < 2 and confidence < 0.5:
                    continue

                # 计算 bounds
                x1 = min(p[0] for p in box)
                y1 = min(p[1] for p in box)
                x2 = max(p[0] for p in box)
                y2 = max(p[1] for p in box)

                items.append({
                    "text": text,
                    "bounds": [int(x1), int(y1), int(x2), int(y2)],
                    "confidence": round(confidence, 3),
                })

            status = "ok" if items else "empty"
            return items, status

        finally:
            try:
                os.unlink(temp_path)
            except:
                pass

    except Exception as e:
        print(f"[observe_screen] OCR 失败: {e}")
        return [], "failed"


# ─────────────────────── 融合逻辑 ───────────────────────

def fuse_dump_and_ocr(clickable_containers, ocr_items):
    """融合 dump 候选容器和 OCR 文本。

    对每个 OCR 文本，找最佳匹配的候选容器：
      1. 包含关系优先：OCR 框落在容器 bounds 内
      2. 重叠程度：IoU / 覆盖率
      3. 语义证据：容器证据与 OCR 文本一致

    返回统一元素列表。
    """
    elements = []
    element_id_counter = [0]

    def next_element_id():
        element_id_counter[0] += 1
        return f"e_{element_id_counter[0]}"

    # 对每个 OCR 项，尝试匹配候选容器
    matched_containers = set()

    for ocr_item in ocr_items:
        ocr_text = ocr_item["text"]
        ocr_bounds = ocr_item["bounds"]
        ocr_conf = ocr_item["confidence"]

        # 找最佳匹配的容器
        best_container = None
        best_score = 0.0

        for idx, container in enumerate(clickable_containers):
            container_bounds = container["bounds"]
            evidence = container["evidence"]

            # 计算匹配分数
            score = calculate_match_score(ocr_bounds, container_bounds, ocr_text, evidence)

            if score > best_score:
                best_score = score
                best_container = (idx, container)

        # 如果找到匹配（分数 > 阈值）
        if best_container and best_score > 0.5:
            idx, container = best_container
            matched_containers.add(idx)

            # 计算 action_rect 和 action_point
            cb = container["bounds"]
            action_rect = [cb["l"], cb["t"], cb["r"], cb["b"]]
            action_point = [(cb["l"] + cb["r"]) // 2, (cb["t"] + cb["b"]) // 2]

            elements.append({
                "element_id": next_element_id(),
                "label": ocr_text,
                "action_rect": action_rect,
                "action_point": action_point,
                "source": "dump+ocr",
                "click_confidence": round(min(0.95, best_score), 2),
                "evidence": {
                    "ocr": {
                        "text": ocr_text,
                        "bounds": ocr_bounds,
                        "confidence": ocr_conf,
                    },
                    "dump": {
                        "text": container["evidence"]["text"],
                        "content_desc": container["evidence"]["content_desc"],
                        "resource_id": container["evidence"]["resource_id"],
                        "clickable": True,
                    }
                }
            })
        else:
            # OCR-only 元素
            action_rect = ocr_bounds
            action_point = [(ocr_bounds[0] + ocr_bounds[2]) // 2,
                           (ocr_bounds[1] + ocr_bounds[3]) // 2]

            elements.append({
                "element_id": next_element_id(),
                "label": ocr_text,
                "action_rect": action_rect,
                "action_point": action_point,
                "source": "ocr",
                "click_confidence": round(min(0.6, ocr_conf * 0.7), 2),
                "evidence": {
                    "ocr": {
                        "text": ocr_text,
                        "bounds": ocr_bounds,
                        "confidence": ocr_conf,
                    },
                    "dump": None
                }
            })

    # 添加未匹配的 dump 容器（有语义证据但 OCR 没识别到文本）
    for idx, container in enumerate(clickable_containers):
        if idx in matched_containers:
            continue

        evidence = container["evidence"]
        # 只保留有语义证据的（text、desc 或 resource_id）
        label = evidence["text"] or evidence["content_desc"]
        if not label and not evidence["resource_id"]:
            continue

        # 跳过太小的容器
        cb = container["bounds"]
        w = cb["r"] - cb["l"]
        h = cb["b"] - cb["t"]
        if w < 20 or h < 20:
            continue

        action_rect = [cb["l"], cb["t"], cb["r"], cb["b"]]
        action_point = [(cb["l"] + cb["r"]) // 2, (cb["t"] + cb["b"]) // 2]

        elements.append({
            "element_id": next_element_id(),
            "label": label or evidence["resource_id"],
            "action_rect": action_rect,
            "action_point": action_point,
            "source": "dump",
            "click_confidence": 0.8 if label else 0.6,
            "evidence": {
                "ocr": None,
                "dump": {
                    "text": evidence["text"],
                    "content_desc": evidence["content_desc"],
                    "resource_id": evidence["resource_id"],
                    "clickable": True,
                }
            }
        })

    # 排序：dump+ocr 高置信度 → dump → ocr
    elements.sort(key=lambda e: (
        0 if e["source"] == "dump+ocr" and e["click_confidence"] > 0.8 else 1,
        0 if e["source"] == "dump" else 1,
        -e["click_confidence"]
    ))

    return elements


def calculate_match_score(ocr_bounds, container_bounds, ocr_text, evidence):
    """计算 OCR 文本与容器的匹配分数。

    考虑：
      1. 包含关系（OCR 框是否在容器内）
      2. 重叠程度（IoU / 覆盖率）
      3. 语义证据（文本是否一致）
    """
    ox1, oy1, ox2, oy2 = ocr_bounds
    cx1, cy1, cx2, cy2 = container_bounds["l"], container_bounds["t"], \
                         container_bounds["r"], container_bounds["b"]

    # 1. 包含关系：OCR 框中心是否在容器内
    ocx = (ox1 + ox2) / 2
    ocy = (oy1 + oy2) / 2
    contained = (cx1 <= ocx <= cx2) and (cy1 <= ocy <= cy2)

    if not contained:
        return 0.0

    # 2. 重叠程度：OCR 框面积占容器面积的比例
    ocr_area = (ox2 - ox1) * (oy2 - oy1)
    container_area = (cx2 - cx1) * (cy2 - cy1)

    if container_area == 0:
        return 0.0

    coverage = ocr_area / container_area
    coverage_score = min(1.0, coverage * 2)  # 50% 覆盖率得满分

    # 3. 语义证据
    semantic_score = 0.0
    if evidence["text"] and ocr_text in evidence["text"]:
        semantic_score = 0.3
    elif evidence["content_desc"] and ocr_text in evidence["content_desc"]:
        semantic_score = 0.3
    elif evidence["text"] and similarity(ocr_text, evidence["text"]) > 0.7:
        semantic_score = 0.2

    # 综合分数
    score = coverage_score * 0.6 + semantic_score + 0.1  # 基础分 0.1（已包含）

    return min(1.0, score)


def similarity(s1, s2):
    """简单的字符串相似度（基于字符重叠）。"""
    if not s1 or not s2:
        return 0.0
    set1 = set(s1)
    set2 = set(s2)
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0


# ─────────────────────── 主入口 ───────────────────────

def handler(params=None):
    """observe_screen 命令处理器。"""
    try:
        # 1. 获取屏幕信息
        screen_info = get_screen_info()
        if not screen_info:
            return error("SCREEN_INFO_FAILED", "无法获取屏幕信息")

        package = screen_info["package"]
        activity = screen_info["activity"]
        screen_size = screen_info["screen"]

        # 2. 截图
        image_bytes, shot_hash = capture_screenshot()
        if not image_bytes:
            return error("SCREENSHOT_FAILED", "截图失败")

        # 3. dump UI 树
        tree, tree_hash, dump_status = dump_ui_tree(depth=6)

        # 4. 计算 screen_version
        screen_version = f"{package}:{activity}:{shot_hash}:{tree_hash or 'none'}"

        # 5. 提取可操作候选容器
        clickable_containers = []
        if tree and dump_status != "unavailable":
            clickable_containers = find_clickable_ancestors(tree)

        # 6. 运行 OCR
        ocr_items, ocr_status = run_ocr_on_image(image_bytes)

        # 7. 融合
        elements = fuse_dump_and_ocr(clickable_containers, ocr_items)

        # 8. 更新观察缓存
        update_observation(screen_version, elements)

        # 9. 返回结果
        return success_with_data("observe_screen", {
            "screen_version": screen_version,
            "package": package,
            "activity": activity,
            "screen_size": screen_size,
            "dump_status": dump_status,
            "ocr_status": ocr_status,
            "element_count": len(elements),
            "elements": elements,
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return error("EXECUTION_FAILED", str(e))


def observe_screen(params=None):
    """命令入口函数。"""
    return handler(params)
