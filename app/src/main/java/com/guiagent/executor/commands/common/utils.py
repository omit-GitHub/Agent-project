# -*- coding: utf-8 -*-
"""共享工具函数 — 所有命令模块的公共基础。

提供:
  - 响应构造: success() / error() / success_with_data()
  - WS 操作封装: tap() / swipe() / gesture() / find_node() / click_node_by_id() / set_text_by_id()
  - UI 树工具: find_node_in_tree() / collect_texts() / group_by_row() / flatten_rows()
  - 屏幕信息: get_screen()
  - 全局操作: go_back() / go_home() / remote_key()
  - sleep() 封装
"""
import json
import os
import sys
import time
import uuid

# 确保能找到根目录的 send.py
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from send import send as _ws_send  # noqa: E402


# ─────────────────────── ID 生成 ───────────────────────

def _next_id():
    """生成唯一操作 ID（避免并发时冲突）。"""
    return str(uuid.uuid4())[:8]


# ─────────────────────── 响应构造 ───────────────────────

def success(command, result):
    """构造成功响应。

    对标 Java CompoundResponse.success(command, result):
    {"ok": true, "data": {"command": "...", "result": "..."}}
    """
    return {
        "ok": True,
        "data": {
            "command": command,
            "result": result,
        },
    }


def success_with_data(command, data):
    """构造成功响应（自定义 data）。

    对标 Java CompoundResponse.successWithData(command, data):
    {"ok": true, "data": {"command": "...", ...data}}
    """
    d = dict(data) if data else {}
    d["command"] = command
    return {"ok": True, "data": d}


def error(code, message):
    """构造错误响应。

    对标 Java CompoundResponse.error(code, message):
    {"ok": false, "error": {"code": "...", "message": "..."}}
    """
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
        },
    }


# ─────────────────────── WS 操作封装 ───────────────────────

def op(name, **args):
    """发送一条 WS 操作并返回响应 dict。自动分配唯一 ID。

    用法: op("tap", x=640, y=400)
    """
    req = {"id": _next_id(), "op": name, "args": args}
    return _ws_send(req)


def tap(x, y):
    """坐标点击。"""
    return op("tap", x=int(x), y=int(y))


def swipe(x1, y1, x2, y2, duration=300):
    """滑动。"""
    return op("swipe", x1=int(x1), y1=int(y1), x2=int(x2), y2=int(y2), duration=int(duration))


def gesture(points, duration=200):
    """多点手势。points: [[x,y], ...]"""
    return op("gesture", points=points, duration=int(duration))


def click_node_by_id(id_substring):
    """通过 ID 子串点击节点。"""
    return op("click_node", id=id_substring)


def set_text_by_id(id_substring, text):
    """通过 ID 子串设置文本。"""
    return op("set_text", id=id_substring, text=text)


def find_nodes(id_substring, limit=20):
    """查找匹配 ID 子串的节点。"""
    return op("find", id=id_substring, limit=limit)


def dump(depth=3, include=None):
    """dump UI 树。"""
    args = {"depth": int(depth)}
    if include:
        args["include"] = include
    return op("dump", **args)


def ping():
    """ping 获取屏幕信息。"""
    return op("ping")


def global_action(action):
    """全局操作: BACK / HOME / RECENTS / SCREENSHOT。"""
    return op("global", action=action)


def remote_key(key, duration=None):
    """遥控器按键。"""
    args = {"key": key}
    if duration is not None:
        args["duration"] = int(duration)
    return op("remote_key", **args)


def start_app(package, cls=None):
    """启动应用。"""
    args = {"package": package}
    if cls:
        args["class"] = cls
    return op("start", **args)


def wait(ms):
    """等待指定毫秒。"""
    return op("wait", ms=int(ms))


def scroll_node(id_substring, direction="down"):
    """滚动节点。"""
    return op("scroll_node", id=id_substring, direction=direction)


# ─────────────────────── 屏幕信息 ───────────────────────

def get_screen():
    """获取屏幕尺寸 (w, h)。失败返回默认值 (1280, 800)。"""
    r = ping()
    if r.get("ok"):
        screen = r.get("data", {}).get("screen", {})
        return screen.get("w", 1280), screen.get("h", 800)
    return 1280, 800


# ─────────────────────── UI 树工具 ───────────────────────

def find_node_in_tree(node, id_substring):
    """在 dump 返回的 JSON 树中递归查找 ID 包含 id_substring 的第一个节点。

    对标 Java Nodes.findNodeById(root, idSubstring)。
    返回节点 dict 或 None。
    """
    if node is None:
        return None
    nid = node.get("id", "")
    if id_substring in nid:
        return node
    for child in node.get("children", []):
        found = find_node_in_tree(child, id_substring)
        if found is not None:
            return found
    return None


def find_all_nodes_in_tree(node, id_substring, results=None):
    """在 dump 返回的 JSON 树中递归查找所有 ID 包含 id_substring 的节点。"""
    if results is None:
        results = []
    if node is None:
        return results
    nid = node.get("id", "")
    if id_substring in nid:
        results.append(node)
    for child in node.get("children", []):
        find_all_nodes_in_tree(child, id_substring, results)
    return results


def node_center(node):
    """获取节点 bounds 中心坐标 (cx, cy)。"""
    b = node.get("bounds", {})
    cx = (b.get("l", 0) + b.get("r", 0)) // 2
    cy = (b.get("t", 0) + b.get("b", 0)) // 2
    return cx, cy


def node_bounds(node):
    """获取节点 bounds (l, t, r, b)。"""
    b = node.get("bounds", {})
    return b.get("l", 0), b.get("t", 0), b.get("r", 0), b.get("b", 0)


def node_height(node):
    """获取节点高度。"""
    b = node.get("bounds", {})
    return b.get("b", 0) - b.get("t", 0)


def collect_texts(node, max_count=12, max_len=30, _out=None):
    """DFS 收集去重后的可见文本（对标 Java StateCapture.collectTexts）。

    最多 max_count 条，每条不超过 max_len 字符。
    返回 list[str]。
    """
    if _out is None:
        _out = []
    if node is None or len(_out) >= max_count:
        return _out

    text = node.get("text", "")
    if text:
        t = text.strip()
        if t and len(t) <= max_len and t not in _out:
            _out.append(t)

    for child in node.get("children", []):
        if len(_out) >= max_count:
            break
        collect_texts(child, max_count, max_len, _out)
    return _out


def contains_text(node, expected):
    """检查 UI 树中是否包含指定文本（对标 Java SearchCommand.containsText）。"""
    if node is None or not expected:
        return False
    text = node.get("text", "")
    if text and expected in text:
        return True
    desc = node.get("desc", "")
    if desc and expected in desc:
        return True
    for child in node.get("children", []):
        if contains_text(child, expected):
            return True
    return False


# ─────────────────────── 行分组工具 ───────────────────────

def group_by_row(nodes, tolerance=30):
    """将节点按 y 坐标分组为视觉行（对标 Java AccessibilityGrid.groupByRow）。

    同一 y 中心（容差 tolerance px）的节点归为一行；行内按 x 排序；
    行与行按 y 排序。返回 list[list[node]]。
    """
    if not nodes:
        return []

    rows = []
    for node in nodes:
        _, cy = node_center(node)
        matched = False
        for row in rows:
            _, row_cy = node_center(row[0])
            if abs(cy - row_cy) < tolerance:
                row.append(node)
                matched = True
                break
        if not matched:
            rows.append([node])

    # 行内按 x 排序
    for row in rows:
        row.sort(key=lambda n: node_center(n)[0])
    # 行间按 y 排序
    rows.sort(key=lambda row: node_center(row[0])[1])
    return rows


def flatten_rows(rows):
    """将行分组结果展平为列表（对标 Java AccessibilityGrid.flatten）。"""
    result = []
    for row in rows:
        result.extend(row)
    return result


def detect_columns(nodes, tolerance=30):
    """检测列数（按 x 坐标分组，数有多少个不同的 x）。

    对标 Java AiQiyiSelectEpisodeCommand.detectColumns()。
    """
    if not nodes:
        return 1
    xs = []
    for node in nodes:
        cx, _ = node_center(node)
        matched = False
        for x in xs:
            if abs(cx - x) < tolerance:
                matched = True
                break
        if not matched:
            xs.append(cx)
    return len(xs)


# ─────────────────────── 高层快捷操作 ───────────────────────

def go_back():
    """按返回键。"""
    return global_action("BACK")


def go_home():
    """按主页键。"""
    return global_action("HOME")


def sleep_ms(ms):
    """休眠指定毫秒。"""
    time.sleep(ms / 1000.0)


def sleep(seconds):
    """休眠指定秒数。"""
    time.sleep(seconds)


def parse_count(params, default=1, max_val=20):
    """从 params dict 中安全解析 count 参数。

    对标 Java 中 params.has("count") ? params.get("count").getAsInt() : default 模式。
    """
    if not params:
        return default
    count = params.get("count", default)
    try:
        count = int(count)
    except (ValueError, TypeError):
        return default
    return max(1, min(count, max_val))


def parse_values(params):
    """从 params 中解析 values 数组。

    支持:
    - {"values": [1, 2]} → [1, 2]
    - {"params": [1, 2]} → [1, 2]  (HTTP 数组格式被包装后的情况)
    - 其他 → None
    """
    if not params:
        return None
    if "values" in params:
        v = params["values"]
        if isinstance(v, list):
            return v
    if "params" in params:
        v = params["params"]
        if isinstance(v, list):
            return v
    return None
