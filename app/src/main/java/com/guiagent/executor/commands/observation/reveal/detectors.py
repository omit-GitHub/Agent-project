# -*- coding: utf-8 -*-
"""控件显隐检测器 — 判断"控制条出现了吗？"

提供三级检测，按置信度从高到低：
  1. 高：a11y 树里出现控制条容器节点（ID 匹配）
  2. 中：a11y 树里出现典型控制按钮 ID
  3. 低：OCR 文字匹配（暂停/选集/倍速等）

任何一级返回 True 即可确认控件已显。

设计要点：
  - 不依赖单一信号（单一信号容易误判）
  - 高置信度信号存在时直接返回，不浪费 OCR 开销
  - OCR 仅作为最后兜底（且要求同时满足多个文字线索）
"""
import os
import sys
from typing import Optional, Dict, Any, List

# 让本模块能找到 common/utils 和 send
_HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from send import send  # noqa: E402


# ─────────────── 高置信度：控制条容器 ID ───────────────

# 任一 ID 出现 → 控制条可见（强信号）
CONTROL_BAR_CONTAINER_IDS = (
    # 通用
    "playercontrolbar", "player_control_bar",
    "player_bottom_bar", "playerbottombar",
    "player_control", "playercontrol",
    "control_bar", "controlbar",
    "bottom_control", "player_bottom",
    # 爱奇艺
    "iqiyi_player_bottom", "qiyi_control",
    "player_bottom_layout",
    # 腾讯
    "qlive_bottom", "player_bottom_root",
)


# ─────────────── 中置信度：典型按钮 ID ───────────────

# 控制条上常见的按钮 ID（任一出现 → 控制条很可能可见）
TYPICAL_CONTROL_BUTTON_IDS = (
    # 播放/暂停
    "btn_pause", "btnpause", "pause_btn",
    "btn_play", "btnplay", "play_btn", "playbtn",
    # 下一集 / 上一集
    "im_play_next", "nextbtn", "btn_next", "next_btn",
    "im_play_last", "prevbtn", "btn_prev", "prev_btn",
    # 倍速 / 清晰度
    "textview_speed", "speedbtn", "speed_btn",
    "textview_resolution", "qualitybtn", "quality_btn",
    # 选集
    "tv_change_episode", "episodebtn", "episode_btn",
)


# ─────────────── 低置信度：OCR 文字线索 ───────────────

# 控制条上常见的文字（中文 + 英文）
TYPICAL_CONTROL_TEXTS = (
    # 中文
    "暂停", "播放", "选集", "倍速", "清晰度",
    "下一集", "上一集", "详情", "简介",
    # 英文（部分 App 用英文按钮）
    "pause", "play", "episodes", "speed",
    "0.75x", "1.0x", "1.25x", "1.5x", "2.0x",
    "480P", "720P", "1080P",
)

# OCR 触发阈值：至少匹配 N 个不同文字线索才判定为控制条可见
OCR_MIN_MATCHES = 2


# ─────────────── 主入口 ───────────────

def detect_control_bar(
    tree: Optional[Dict[str, Any]] = None,
    ocr_texts: Optional[List[str]] = None,
    run_ocr_if_needed: bool = True,
) -> Dict[str, Any]:
    """检测控制条是否可见。

    Args:
        tree: UI 树根节点。为 None 时自动 dump。
        ocr_texts: 已提取的 OCR 文字列表。为 None 且 run_ocr_if_needed=True 时自动跑 OCR。
        run_ocr_if_needed: 高/中置信度都失败时，是否自动跑 OCR。

    Returns:
        {
            "visible": True/False,
            "confidence": "high" | "medium" | "low" | "none",
            "method": "container_id" | "button_id" | "ocr_text" | "none",
            "evidence": {...}   # 触发判定的具体证据
        }
    """
    # 1. 准备 UI 树
    if tree is None:
        tree = _dump_tree()

    # 2. 收集树里的所有 ID（小写）
    ids_lower = _collect_ids_lower(tree)

    # 3. 高置信度：容器 ID
    for id_lower in ids_lower:
        for pattern in CONTROL_BAR_CONTAINER_IDS:
            if pattern in id_lower:
                return {
                    "visible": True,
                    "confidence": "high",
                    "method": "container_id",
                    "evidence": {"matched_id": id_lower, "pattern": pattern},
                }

    # 4. 中置信度：按钮 ID
    matched_buttons = []
    for id_lower in ids_lower:
        for pattern in TYPICAL_CONTROL_BUTTON_IDS:
            if pattern in id_lower:
                matched_buttons.append({"id": id_lower, "pattern": pattern})
                break
    if matched_buttons:
        return {
            "visible": True,
            "confidence": "medium",
            "method": "button_id",
            "evidence": {"matched_buttons": matched_buttons[:5]},  # 限制大小
        }

    # 5. 低置信度：OCR 文字
    if run_ocr_if_needed:
        if ocr_texts is None:
            ocr_texts = _run_ocr()
        if ocr_texts:
            matched_texts = []
            for text in ocr_texts:
                text_lower = text.lower()
                for pattern in TYPICAL_CONTROL_TEXTS:
                    if pattern.lower() in text_lower:
                        matched_texts.append({"text": text, "pattern": pattern})
                        break
            if len(matched_texts) >= OCR_MIN_MATCHES:
                return {
                    "visible": True,
                    "confidence": "low",
                    "method": "ocr_text",
                    "evidence": {"matched_texts": matched_texts[:5]},
                }

    # 6. 都没命中
    return {
        "visible": False,
        "confidence": "none",
        "method": "none",
        "evidence": {},
    }


# ─────────────── 辅助 ───────────────

def _dump_tree() -> Dict[str, Any]:
    """dump UI 树。失败返回空 dict。"""
    try:
        r = send({
            "id": "det_dump",
            "op": "dump",
            "args": {"depth": 4, "include": ["id", "text", "class"]},
        })
        if r.get("ok"):
            return r.get("data", {}).get("window", {}) or r.get("data", {})
    except Exception:
        pass
    return {}


def _collect_ids_lower(tree: Dict[str, Any]) -> List[str]:
    """DFS 收集所有节点 ID 的小写形式。"""
    ids = []
    if not tree:
        return ids

    def visit(node):
        if not node:
            return
        nid = (node.get("id") or "").strip()
        if nid:
            ids.append(nid.lower())
        for child in node.get("children", []) or []:
            visit(child)

    visit(tree)
    return ids


def _run_ocr() -> List[str]:
    """运行 OCR 并返回识别到的文字列表。失败返回 []。

    通过 adb screencap + RapidOCR 实现。
    注意：依赖 rapidocr_onnxruntime，未安装时返回 []。
    """
    try:
        import subprocess
        import tempfile
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return []

    try:
        result = subprocess.run(
            ["adb", "exec-out", "screencap", "-p"],
            capture_output=True, timeout=5,
        )
        if result.returncode != 0 or not result.stdout:
            return []

        # 写入临时文件
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(result.stdout)
            tmp_path = f.name

        try:
            engine = RapidOCR()
            ocr_result, _ = engine(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        if not ocr_result:
            return []

        # ocr_result 格式: [[box, text, confidence], ...]
        return [item[1].strip() for item in ocr_result if item[1] and item[1].strip()]

    except Exception:
        return []
