# -*- coding: utf-8 -*-
"""DPAD Executor 子包 — 焦点感知的 DPAD 导航。

对外暴露:
  - dpad_press(key, track_focus)         → dict  (Level 1)
  - dpad_navigate(direction, count)      → dict  (Level 2)
  - focus_element(target_id/text)        → dict  (Level 3)
  - dpad_confirm()                       → dict  (Level 4)
  - detect_focus_change(before, after)   → dict  (焦点追踪原语)
  - get_focused_id(tree) / get_focused_info(tree)
"""
from .executor import (
    dpad_press,
    dpad_navigate,
    dpad_confirm,
    focus_element,
    run_navigate,
    run_confirm,
    run_press,
    run_focus_element,
)
from .focus_tracker import (
    find_focused_node,
    get_focused_id,
    get_focused_info,
    detect_focus_change,
)
from .keymaps import (
    get_keymap,
    list_apps,
    list_contexts,
    KEYMAPS,
    DIRECTION_TO_KEY,
    OPPOSITE_DIRECTION,
)

__all__ = [
    # 主入口 (executor)
    "dpad_press",
    "dpad_navigate",
    "dpad_confirm",
    "focus_element",
    # 命令封装
    "run_navigate",
    "run_confirm",
    "run_press",
    "run_focus_element",
    # 焦点追踪
    "find_focused_node",
    "get_focused_id",
    "get_focused_info",
    "detect_focus_change",
    # 键位映射
    "get_keymap",
    "list_apps",
    "list_contexts",
    "KEYMAPS",
    "DIRECTION_TO_KEY",
    "OPPOSITE_DIRECTION",
]
