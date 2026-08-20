# -*- coding: utf-8 -*-
"""Focus-Aware DPAD Executor — 焦点感知的 DPAD 导航执行器。

提供 4 级 API（从低到高）:
  Level 1: dpad_press(key)              — 单次按键 + 焦点追踪
  Level 2: dpad_navigate(dir, count)    — 多次连续导航
  Level 3: focus_element(target, ...)   — 目标导向导航
  Level 4: dpad_confirm()               — 在当前焦点元素上按 ENTER

所有带 track_focus=True 的操作都会：
  1. dump UI 树记录当前焦点
  2. 执行按键
  3. 等待 UI 响应
  4. dump UI 树检测焦点是否移动
  5. 返回焦点变化信息

设计要点：
  - 默认 track_focus=True（代价是一次额外 dump，但换来可靠的焦点状态）
  - track_focus=False 时盲按（快但无反馈，仅用于性能敏感场景）
  - focus_element 支持按 id 或 text 匹配，失败时返回已走路径
"""
import os
import sys
import time
import traceback
from typing import Optional, Dict, Any, List

# 让本模块能找到 common / send
_HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from send import send                                               # noqa: E402
from common.utils import success_with_data, error                   # noqa: E402

from .focus_tracker import (                                        # noqa: E402
    find_focused_node,
    get_focused_id,
    get_focused_info,
    detect_focus_change,
)
from .keymaps import (                                              # noqa: E402
    DIRECTION_TO_KEY,
    OPPOSITE_DIRECTION,
    get_keymap,
)


# ─────────────── 常量 ───────────────

DEFAULT_POST_KEY_WAIT_MS = 300      # 按键后默认等待 UI 响应
FOCUS_SETTLE_WAIT_MS = 150          # 焦点稳定额外等待


# ─────────────── 辅助函数 ───────────────

def _do_dump():
    """dump UI 树（直接 WS 调用）。失败返回空 dict。"""
    try:
        r = send({
            "id": f"dpad_dump_{id(None)}",
            "op": "dump",
            "args": {"depth": 5, "include": ["id", "text", "class", "focused",
                                              "clickable", "bounds", "content_desc"]},
        })
        if r.get("ok"):
            return r.get("data", {}).get("window", {}) or r.get("data", {})
    except Exception:
        pass
    return {}


def _do_key(key: str) -> Dict[str, Any]:
    """发送一个 remote_key。返回 WS 响应 dict。"""
    try:
        return send({
            "id": f"dpad_{key}_{id(key)}",
            "op": "remote_key",
            "args": {"key": key},
        })
    except Exception as e:
        return {"ok": False, "err": {"code": "KEY_FAILED", "msg": str(e)}}


def _normalize_direction(direction: str) -> Optional[str]:
    """把方向字符串归一化为 DIRECTION_TO_KEY 的 key。"""
    if not direction:
        return None
    d = direction.strip().upper()
    # 支持中文方向名
    zh_map = {"上": "UP", "下": "DOWN", "左": "LEFT", "右": "RIGHT",
              "向上": "UP", "向下": "DOWN", "向左": "LEFT", "向右": "RIGHT"}
    if d in zh_map:
        d = zh_map[d]
    return DIRECTION_TO_KEY.get(d)


# ─────────────── Level 1: 单次按键 ───────────────

def dpad_press(
    key: str,
    track_focus: bool = True,
    wait_ms: int = DEFAULT_POST_KEY_WAIT_MS,
) -> Dict[str, Any]:
    """按一次 DPAD 键，可选追踪焦点变化。

    Args:
        key: "UP" | "DOWN" | "LEFT" | "RIGHT" | "ENTER" | "BACK" | "MENU" | ...
        track_focus: 是否 dump 树追踪焦点变化
        wait_ms: 按键后等待时间（毫秒）

    Returns:
        {
            "ok": True/False,
            "key": "UP",
            "key_result": {...},                # WS 响应
            "focus_moved": True/False,          # 仅当 track_focus=True
            "tracking_available": True/False,
            "old_focus_id": ...,
            "new_focus_id": ...,
            "new_focus_info": {...},            # 新焦点节点摘要
        }
    """
    result = {"ok": True, "key": key}

    # 1. 按键前 dump（如果需要追踪）
    tree_before = _do_dump() if track_focus else None

    # 2. 发送按键
    key_result = _do_key(key)
    result["key_result"] = key_result
    if not key_result.get("ok"):
        result["ok"] = False
        result["error"] = key_result.get("err", {}).get("msg", "key failed")
        return result

    # 3. 等待 UI 响应
    if wait_ms > 0:
        time.sleep(wait_ms / 1000.0)

    # 4. 焦点追踪
    if track_focus:
        tree_after = _do_dump()
        change = detect_focus_change(tree_before, tree_after)
        result.update(change)
    else:
        result["focus_moved"] = None
        result["tracking_available"] = False

    return result


# ─────────────── Level 2: 连续导航 ───────────────

def dpad_navigate(
    direction: str,
    count: int = 1,
    track_focus: bool = True,
    wait_ms: int = DEFAULT_POST_KEY_WAIT_MS,
) -> Dict[str, Any]:
    """连续按 N 次方向键。

    Args:
        direction: "UP" | "DOWN" | "LEFT" | "RIGHT"（或中文）
        count: 按几次（默认 1）
        track_focus: 是否每次按键都追踪焦点
        wait_ms: 每次按键后等待

    Returns:
        {
            "ok": True/False,
            "direction": "RIGHT",
            "presses": 3,
            "focus_changes": [...],            # 每次按键的焦点变化
            "final_focus_id": ...,
            "final_focus_info": {...},
            "focus_moved_total": True/False,   # 整体焦点是否变化
        }
    """
    key = _normalize_direction(direction)
    if not key:
        return error("BAD_DIRECTION", f"Unknown direction: {direction}")

    count = max(1, int(count))
    result = {
        "ok": True,
        "direction": key,
        "presses": count,
        "focus_changes": [],
        "final_focus_id": None,
        "final_focus_info": None,
        "focus_moved_total": False,
    }

    # 记录初始焦点
    initial_tree = _do_dump() if track_focus else None
    initial_focus_id = get_focused_id(initial_tree) if track_focus else None

    # 连续按键
    for i in range(count):
        press = dpad_press(key, track_focus=track_focus, wait_ms=wait_ms)
        if not press.get("ok"):
            result["ok"] = False
            result["failed_at"] = i + 1
            result["error"] = press.get("error")
            break
        if track_focus:
            result["focus_changes"].append({
                "press": i + 1,
                "focus_moved": press.get("focus_moved"),
                "new_focus_id": press.get("new_focus_id"),
                "new_focus_text": press.get("new_focus_text"),
            })

    # 最终焦点
    if track_focus:
        final_tree = _do_dump()
        result["final_focus_id"] = get_focused_id(final_tree)
        result["final_focus_info"] = get_focused_info(final_tree)
        result["focus_moved_total"] = (
            initial_focus_id is not None
            and result["final_focus_id"] != initial_focus_id
        )

    return success_with_data("dpad_navigate", result)


# ─────────────── Level 3: 目标导向导航 ───────────────

def focus_element(
    target_id: Optional[str] = None,
    target_text: Optional[str] = None,
    max_presses: int = 10,
    direction: Optional[str] = None,
    wait_ms: int = DEFAULT_POST_KEY_WAIT_MS,
) -> Dict[str, Any]:
    """通过 DPAD 导航把焦点移到目标元素。

    策略（按优先级）：
      1. 如果指定了 direction，沿该方向一直按直到匹配或达到 max_presses
      2. 否则尝试四个方向，取最先匹配到的
      3. 匹配：当前焦点节点的 id 包含 target_id 或 text 包含 target_text

    Args:
        target_id: 目标元素的 resource-id 子串
        target_text: 目标元素的文字子串
        max_presses: 单方向最大按键次数
        direction: 指定方向（可选，不指定则尝试四方向）
        wait_ms: 每次按键后等待

    Returns:
        {
            "ok": True,
            "found": True/False,
            "target_id": ..., "target_text": ...,
            "focus_id": ...,
            "focus_text": ...,
            "presses_used": N,
            "direction": "RIGHT",
            "path": [...],                    # 经过的焦点 id 列表
        }
        或 error(...)
    """
    if not target_id and not target_text:
        return error("BAD_ARGS", "Must provide target_id or target_text")

    max_presses = max(1, int(max_presses))

    def _matches(focus_info):
        if not focus_info:
            return False
        if target_id and target_id.lower() in (focus_info.get("id") or "").lower():
            return True
        if target_text and target_text in (focus_info.get("text") or ""):
            return True
        if target_text and target_text in (focus_info.get("content_desc") or ""):
            return True
        return False

    def _try_direction(dir_key):
        """沿一个方向尝试导航。返回 (found, info_dict, path)。"""
        path = []
        for i in range(max_presses):
            # 检查当前焦点是否已匹配
            tree = _do_dump()
            current = get_focused_info(tree)
            path.append({
                "press": i,
                "focus_id": current.get("id") if current else None,
                "focus_text": current.get("text") if current else None,
            })
            if _matches(current):
                return True, current, path

            # 按键
            press = dpad_press(dir_key, track_focus=False, wait_ms=wait_ms)
            if not press.get("ok"):
                return False, current, path

        # 最后一次检查（按完 max_presses 次后）
        tree = _do_dump()
        current = get_focused_info(tree)
        path.append({
            "press": max_presses,
            "focus_id": current.get("id") if current else None,
            "focus_text": current.get("text") if current else None,
        })
        if _matches(current):
            return True, current, path

        return False, current, path

    # 执行
    directions = [direction] if direction else ["RIGHT", "DOWN", "LEFT", "UP"]
    for dir_key in directions:
        normalized = _normalize_direction(dir_key)
        if not normalized:
            continue
        found, info, path = _try_direction(normalized)
        if found:
            return success_with_data("focus_element", {
                "found": True,
                "target_id": target_id,
                "target_text": target_text,
                "focus_id": info.get("id"),
                "focus_text": info.get("text"),
                "focus_info": info,
                "presses_used": len(path),
                "direction": normalized,
                "path": path,
            })

    # 全部方向都失败
    return success_with_data("focus_element", {
        "found": False,
        "target_id": target_id,
        "target_text": target_text,
        "presses_used": 0,
        "direction": None,
        "path": [],
        "hint": "Target not found in any direction within max_presses",
    })


# ─────────────── Level 4: 确认选择 ───────────────

def dpad_confirm(wait_ms: int = DEFAULT_POST_KEY_WAIT_MS) -> Dict[str, Any]:
    """在当前焦点元素上按 ENTER（DPAD 确认键）。

    Returns:
        同 dpad_press(ENTER)
    """
    return dpad_press("ENTER", track_focus=True, wait_ms=wait_ms)


# ─────────────── 命令封装（给 registry 注册用）───────────────

def run_navigate(params=None):
    """dpad_navigate 命令入口。

    params: {"direction": "RIGHT", "count": 3}
    """
    params = params or {}
    direction = params.get("direction", "")
    count = int(params.get("count", 1))
    return dpad_navigate(direction=direction, count=count)


def run_confirm(params=None):
    """dpad_confirm 命令入口。"""
    return dpad_confirm()


def run_press(params=None):
    """dpad_press 命令入口（可选暴露给 Agent）。

    params: {"key": "ENTER"}
    """
    params = params or {}
    key = params.get("key", "ENTER")
    return dpad_press(key=key)


def run_focus_element(params=None):
    """focus_element 命令入口。

    params: {"target_id": "btn_pause"} 或 {"target_text": "暂停"}
    """
    params = params or {}
    return focus_element(
        target_id=params.get("target_id"),
        target_text=params.get("target_text"),
        max_presses=int(params.get("max_presses", 10)),
        direction=params.get("direction"),
    )
