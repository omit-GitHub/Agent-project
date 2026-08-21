# -*- coding: utf-8 -*-
"""Harness Framework — VLM 决策与真实设备执行之间的确定性安全边界。

主要能力：
  - Action Guard：动作合法性多重校验
  - Layered Verifier：本地信号优先 + 严格四态输出
  - Control Revealer：隐藏控件唤出，带三态状态机
  - run_action_loop：Protocol 驱动的最小闭环
  - ActionSpec / UiState / ActionResult / ActionLoopResult：最小数据模型

本包无任何外部依赖（除 pydantic）。
"""
from .types import BBox, Candidate, CandidateMap
from .schemas import ActionSpec, UiState, ActionResult, ActionLoopResult
from .action_guard import (
    ActionGuard,
    ActionGuardConfig,
    GuardDecision,
    InvalidBBoxError,
    validate_action,
    tap_to_pixel,
)
from .verifier import (
    LayeredVerifier,
    LocalVerifier,
    VlmVerifier,
    VerificationResult,
    VerificationSource,
    VerificationStatus,
)
from .control_revealer import (
    ControlRevealer,
    RevealStrategyManager,
    RevealStrategyRecord,
    DEFAULT_REVEAL_SEQUENCE,
)
from .timing import PhaseTimings, TimingStats, TimingTracker
from .action_loop import (
    run_action_loop,
    DecisionSource,
    ActionExecutor,
    StateVerifier,
)

__version__ = "0.1.0"

__all__ = [
    # types
    "BBox",
    "Candidate",
    "CandidateMap",
    # schemas
    "ActionSpec",
    "UiState",
    "ActionResult",
    "ActionLoopResult",
    # action_guard
    "ActionGuard",
    "ActionGuardConfig",
    "GuardDecision",
    "InvalidBBoxError",
    "validate_action",
    "tap_to_pixel",
    # verifier
    "LayeredVerifier",
    "LocalVerifier",
    "VlmVerifier",
    "VerificationResult",
    "VerificationSource",
    "VerificationStatus",
    # control_revealer
    "ControlRevealer",
    "RevealStrategyManager",
    "RevealStrategyRecord",
    "DEFAULT_REVEAL_SEQUENCE",
    # timing
    "TimingTracker",
    "PhaseTimings",
    "TimingStats",
    # action_loop
    "run_action_loop",
    "DecisionSource",
    "ActionExecutor",
    "StateVerifier",
]
