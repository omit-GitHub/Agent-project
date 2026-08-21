# -*- coding: utf-8 -*-
"""Harness 核心数据模型。

生产级最小状态快照（UiState）+ Harness 专用动作/结果类型（ActionSpec / ActionResult / ActionLoopResult）。

设计原则：
  - 与 VLM / ADB / OCR 完全解耦
  - UiState 作为 Harness 的最小可观测状态；后续接真实 Android snapshot 时
    只需替换实例化位置，核心数据模型无需改名
  - ActionResult 显式携带 after_state，禁止执行器原地修改入参 state
"""
from dataclasses import dataclass, field
from typing import Any, Optional

from ..candidates.schemas import CandidateMap, PixelBBox


# ─────────────── 动作规格 ───────────────

@dataclass
class ActionSpec:
    """Harness 视角下的单步动作规格。

    与 VLM NextAction 解耦：VLM 只是 DecisionSource 的一个实现，
    Harness 内部只消费 ActionSpec。

    字段分组：
      - action_type：动作类型
      - 候选定位：candidate_id / candidate_map_fingerprint
      - 页面期望：expected_screen_fingerprint / expected_package / expected_activity
      - 目标语义：target_role / bbox_px / sensitive_hint
      - 动作参数：key / text / direction / distance / wait_ms
    """
    action_type: str

    # 候选定位
    candidate_id: Optional[str] = None
    candidate_map_fingerprint: Optional[str] = None  # vs state.candidate_map.screen_version

    # 页面期望（三个独立维度，禁止混用）
    expected_screen_fingerprint: Optional[str] = None  # vs state.fingerprint（防跨页点击）
    expected_package: Optional[str] = None              # vs state.package（Verifier 用）
    expected_activity: Optional[str] = None             # vs state.activity（Verifier 用）

    # 目标语义
    target_role: Optional[str] = None
    bbox_px: Optional[PixelBBox] = None
    sensitive_hint: Optional[str] = None  # 仅追加保守拦截信号，不作为主要敏感源

    # 动作参数
    key: Optional[str] = None
    text: Optional[str] = None
    direction: Optional[str] = None
    distance: Optional[float] = None
    wait_ms: Optional[int] = None


# ─────────────── 最小状态快照 ───────────────

@dataclass
class UiState:
    """Harness 的最小可观测 UI 状态快照。

    字段：
      - fingerprint：UI 级指纹（如 OCR+layout+package+activity 的稳定哈希）
      - package / activity：系统级状态
      - screen_size：像素尺寸 (width, height)
      - candidate_map：当前屏幕的候选集合（可为 None）
      - control_bar_visible：控制条是否可见
      - ocr_tokens：当前屏幕可见 OCR token 集合
      - selected_role：当前被选中的角色（如焦点/高亮的控件角色）
    """
    fingerprint: str
    package: str
    activity: str
    screen_size: tuple  # (width, height)
    candidate_map: Optional[CandidateMap]
    control_bar_visible: bool
    ocr_tokens: set
    selected_role: Optional[str] = None


# ─────────────── 执行结果 ───────────────

@dataclass
class ActionResult:
    """单步执行结果。

    关键约束：after_state 必须显式携带，禁止依赖执行器对 state 的隐式原地修改。
    """
    ok: bool
    action: ActionSpec
    after_state: UiState
    error_code: Optional[str] = None
    detail: Optional[str] = None


# ─────────────── 闭环结果 ───────────────

@dataclass
class ActionLoopResult:
    """run_action_loop 的完整结果。

    status 取值：
      - success：Verifier 返回 success（唯一 ok=True 出口）
      - blocked：Guard 拒绝
      - failed：执行或验证失败
      - timeout：max_steps 耗尽
      - needs_user_confirmation：action_type == "ask_user"
      - stopped_unverified：action_type == "done" 但此前未获得 Verifier success
    """
    ok: bool
    status: str
    steps: list = field(default_factory=list)
    final_message: str = ""
    verification: Any = None  # VerificationResult | None（避免循环导入）
