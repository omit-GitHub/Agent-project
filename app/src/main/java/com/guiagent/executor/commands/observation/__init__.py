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
# 4 个核心能力：state (Phase 0) + reveal (Phase 2) + dpad (Phase 3) + verify (Phase 4)
# 辅助：screen (observe/click，从原 ocr/ 迁移) + observation_cache

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
from .verify import (
    verify,
    verify_after_action,
    VerificationResult,
    AfterActionResult,
    PredicateResult,
    # 8 个谓词
    bar_visible,
    playing_state_changed,
    episode_changed,
    speed_changed,
    quality_changed,
    overlay_appeared,
    node_present,
    text_present,
    # 恢复策略
    re_reveal,
    retry_dpad_enter,
    wait_and_retry,
    noop,
    chain,
)
# screen 子模块（observe/click）懒加载以避免启动时跑 OCR import
# 用 `from observation.screen import observe_screen` 直接导入也可以
from . import screen
from . import observation_cache

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
    # Verification
    "verify",
    "verify_after_action",
    "VerificationResult",
    "AfterActionResult",
    "PredicateResult",
    "bar_visible",
    "playing_state_changed",
    "episode_changed",
    "speed_changed",
    "quality_changed",
    "overlay_appeared",
    "node_present",
    "text_present",
    "re_reveal",
    "retry_dpad_enter",
    "wait_and_retry",
    "noop",
    "chain",
    # Screen observation (from old ocr/)
    "screen",
    "observation_cache",
]
