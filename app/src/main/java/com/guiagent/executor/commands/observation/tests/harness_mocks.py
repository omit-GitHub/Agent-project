# -*- coding: utf-8 -*-
"""Harness mock 基础设施。

纯 Python 环境下的 Mock/Fake 实现，用于测试 Harness 三模块（Guard / Verifier / Revealer）
以及 run_action_loop，无需真实设备、VLM、ADB 或 OCR。

所有 Fake 显式构造新对象返回，禁止原地修改入参 state（约束 #1）。
"""
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from observation.candidates.schemas import CandidateMap, PixelBBox, UiCandidate
from observation.harness.schemas import (
    ActionLoopResult,
    ActionResult,
    ActionSpec,
    UiState,
)
from observation.harness.verifier import VerificationResult


# ─────────────── Mock 决策源 ───────────────

@dataclass
class MockDecisionSource:
    """按顺序返回预设 ActionSpec；耗尽后返回 done。"""
    actions: list
    _index: int = field(default=0, init=False, repr=False)

    def next_action(self, state: UiState) -> ActionSpec:
        if self._index >= len(self.actions):
            return ActionSpec(action_type="done")
        action = self.actions[self._index]
        self._index += 1
        return action


# ─────────────── Fake 执行器 ───────────────

@dataclass
class FakeExecutor:
    """不执行真实操作，只记录 calls 并按预设改变 state。

    显式构造新 UiState 返回（禁止原地修改入参 state）。
    """
    after_state: Optional[UiState] = None
    state_transitions: dict = field(default_factory=dict)
    default_ok: bool = True
    default_error_code: Optional[str] = None
    calls: list = field(default_factory=list, init=False, repr=False)

    def execute(self, action: ActionSpec, state: UiState) -> ActionResult:
        self.calls.append(action)

        if not self.default_ok:
            return ActionResult(
                ok=False, action=action, after_state=state,
                error_code=self.default_error_code or "execution_failed",
                detail="fake executor preset failure",
            )

        # 显式构造新 state（不原地修改）
        if action.action_type in self.state_transitions:
            new_state = self.state_transitions[action.action_type](state)
        elif self.after_state is not None:
            new_state = self.after_state
        else:
            # 默认：复制当前 state（但构造新对象）
            new_state = UiState(
                fingerprint=state.fingerprint,
                package=state.package,
                activity=state.activity,
                screen_size=state.screen_size,
                candidate_map=state.candidate_map,
                control_bar_visible=state.control_bar_visible,
                ocr_tokens=set(state.ocr_tokens),
                selected_role=state.selected_role,
            )

        return ActionResult(
            ok=True, action=action, after_state=new_state,
            detail="fake executed",
        )


# ─────────────── Fake VLM Verifier ───────────────

@dataclass
class FakeVlmVerifier:
    """按顺序返回预设 VerificationResult；耗尽后返回 unknown。"""
    results: list
    _index: int = field(default=0, init=False, repr=False)

    def verify(self, before: UiState, after: UiState, action: ActionSpec) -> VerificationResult:
        if self._index >= len(self.results):
            return VerificationResult(
                verification="unknown", source="vlm",
                reason="FakeVlmVerifier exhausted",
            )
        result = self.results[self._index]
        self._index += 1
        return result


# ─────────────── Fake Clock ───────────────

@dataclass
class FakeClock:
    """替换 time.sleep/time.time，不实际 sleep。"""
    now: float = 0.0
    sleep_calls: list = field(default_factory=list, init=False, repr=False)

    def time_fn(self) -> float:
        return self.now

    def sleep(self, seconds: float):
        self.sleep_calls.append(seconds)
        self.now += seconds

    def advance(self, seconds: float):
        self.now += seconds


# ─────────────── 测试桩构造辅助 ───────────────

def make_candidate(
    candidate_id: str,
    bbox: Optional[PixelBBox] = None,
    text: Optional[str] = None,
    risk_category: Optional[str] = None,
    sensitive_category: Optional[str] = None,
    action_semantics: Optional[str] = None,
    source: str = "ocr",
    kind: str = "button",
    confidence: float = 0.9,
    clickable_likelihood: float = 0.9,
) -> UiCandidate:
    """快速构造 UiCandidate 测试桩。"""
    if bbox is None:
        bbox = PixelBBox(x1=100, y1=100, x2=200, y2=150)
    return UiCandidate(
        candidate_id=candidate_id,
        source=source,
        kind=kind,
        text=text,
        bbox_px=bbox,
        confidence=confidence,
        clickable_likelihood=clickable_likelihood,
        risk_category=risk_category,
        sensitive_category=sensitive_category,
        action_semantics=action_semantics,
    )


def make_candidate_map(
    candidates: Optional[list] = None,
    screen_version: str = "v1",
    package: str = "com.test",
    activity: str = "Main",
    width: int = 1280,
    height: int = 800,
) -> CandidateMap:
    """快速构造 CandidateMap 测试桩。"""
    return CandidateMap(
        screen_version=screen_version,
        package=package,
        activity=activity,
        width=width,
        height=height,
        screenshot_path="/tmp/fake.png",
        annotated_path="/tmp/fake_annotated.png",
        candidates=candidates or [],
        ocr_status="ok",
        detector_status="ok",
        degradation_mode="none",
        created_at=time.time(),
    )


def make_state(
    fingerprint: str = "fp1",
    package: str = "com.test",
    activity: str = "Main",
    screen_size: tuple = (1280, 800),
    candidate_map: Optional[CandidateMap] = None,
    control_bar_visible: bool = False,
    ocr_tokens: Optional[set] = None,
    selected_role: Optional[str] = None,
) -> UiState:
    """快速构造 UiState 测试桩。"""
    return UiState(
        fingerprint=fingerprint,
        package=package,
        activity=activity,
        screen_size=screen_size,
        candidate_map=candidate_map,
        control_bar_visible=control_bar_visible,
        ocr_tokens=ocr_tokens if ocr_tokens is not None else set(),
        selected_role=selected_role,
    )
