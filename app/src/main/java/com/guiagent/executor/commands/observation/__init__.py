# -*- coding: utf-8 -*-
"""Observation 子包 — 多模态 UI 观测与状态化执行层。

重构自原 ocr/ 子包，包含 4 个核心能力:
  - state/       UI State Resolver（结构化状态输出）
  - reveal/      Control Revealer（隐藏控件显式唤出）
  - dpad/        Focus-Aware DPAD Executor（焦点导航）
  - verify/      Action Verification + Recovery（动作验证与恢复）
  - screen/      observe_screen / click_element（屏幕观察与点击）
  - ocr/         OCR 引擎（仅用于可见文字提取，不再作为隐藏按钮定位器）

本 __init__.py 暴露最常用入口，便于 commands 层一行 import。
"""

# 顶层能力入口（详细实现在子包）
# 当前已实现：state (Phase 0) + reveal (Phase 2) + dpad (Phase 3)
# 后续：verify (Phase 4) + screen (Phase 6) + ocr (Phase 6)

from .state import (
    resolve_state,
    StateSnapshot,
    PlayerState,
    PAGE_TYPE_STRUCTURED,
    PAGE_TYPE_VISUAL,
    PAGE_TYPE_PLAYER,
    PAGE_TYPE_UNKNOWN,
)
from .reveal import (
    reveal_controls,
    detect_control_bar,
    detect_app_from_pkg,
)
from .dpad import (
    dpad_press,
    dpad_navigate,
    dpad_confirm,
    focus_element,
    detect_focus_change,
)

__all__ = [
    # State Resolver
    "resolve_state",
    "StateSnapshot",
    "PlayerState",
    "PAGE_TYPE_STRUCTURED",
    "PAGE_TYPE_VISUAL",
    "PAGE_TYPE_PLAYER",
    "PAGE_TYPE_UNKNOWN",
    # Control Revealer
    "reveal_controls",
    "detect_control_bar",
    "detect_app_from_pkg",
    # DPAD Executor
    "dpad_press",
    "dpad_navigate",
    "dpad_confirm",
    "focus_element",
    "detect_focus_change",
]
