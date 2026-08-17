# -*- coding: utf-8 -*-
"""Verification 子包 — 动作验证与恢复。

对外暴露:
  - verify(predicate, timeout_ms, poll_interval_ms) → VerificationResult
  - verify_after_action(action_fn, predicate, recover_fn, max_retries) → AfterActionResult
  - 8 个内置谓词（predicates 子模块）
  - 4 个内置恢复策略（recovery 子模块）
"""
from .verifier import (
    verify,
    verify_after_action,
    VerificationResult,
    AfterActionResult,
)
from .predicates import (
    PredicateResult,
    bar_visible,
    playing_state_changed,
    episode_changed,
    speed_changed,
    quality_changed,
    overlay_appeared,
    node_present,
    text_present,
)
from .recovery import (
    re_reveal,
    retry_dpad_enter,
    wait_and_retry,
    noop,
    chain,
    get_default_recovery,
)

__all__ = [
    # 主入口
    "verify",
    "verify_after_action",
    # 结果类
    "VerificationResult",
    "AfterActionResult",
    "PredicateResult",
    # 8 个谓词
    "bar_visible",
    "playing_state_changed",
    "episode_changed",
    "speed_changed",
    "quality_changed",
    "overlay_appeared",
    "node_present",
    "text_present",
    # 恢复策略
    "re_reveal",
    "retry_dpad_enter",
    "wait_and_retry",
    "noop",
    "chain",
    "get_default_recovery",
]
