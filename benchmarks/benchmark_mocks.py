# -*- coding: utf-8 -*-
"""Benchmark Mocks — Benchmark 专用的 Mock 实现。

提供 Mock DecisionSource、Executor、Verifier 的实现。
"""
from dataclasses import dataclass, field
from typing import Optional

from harness import ActionSpec, UiState, ActionResult
from harness.verifier import VerificationResult, VerificationStatus


@dataclass
class MockDecisionSource:
    """Mock 决策源。"""
    actions: list
    _index: int = field(default=0, init=False, repr=False)

    def next_action(self, state: UiState) -> ActionSpec:
        if self._index >= len(self.actions):
            return ActionSpec(action_type="done")
        action = self.actions[self._index]
        self._index += 1
        return action

    def reset(self):
        self._index = 0


@dataclass
class MockExecutor:
    """Mock 执行器。"""
    after_state: Optional[UiState] = None
    default_ok: bool = True
    fail_sequence: list = field(default_factory=list)  # 前 N 次执行失败
    call_count: int = field(default=0, init=False, repr=False)
    calls: list = field(default_factory=list, init=False, repr=False)

    def execute(self, action: ActionSpec, state: UiState) -> ActionResult:
        self.calls.append(action)
        self.call_count += 1

        # 检查是否在失败序列中
        if self.call_count <= len(self.fail_sequence) and not self.fail_sequence[self.call_count - 1]:
            return ActionResult(
                ok=False,
                action=action,
                after_state=state,
                error_code="mock_execution_failed",
            )

        after_state = self.after_state if self.after_state is not None else state
        return ActionResult(
            ok=self.default_ok,
            action=action,
            after_state=after_state,
            detail="mock_executed",
        )

    def reset(self):
        self.call_count = 0
        self.calls = []


@dataclass
class MockVerifier:
    """Mock 验证器。"""
    results: list  # list[VerificationResult]
    _index: int = field(default=0, init=False, repr=False)

    def verify(self, before: UiState, after: UiState, action: ActionSpec) -> VerificationResult:
        if self._index >= len(self.results):
            return VerificationResult(
                verification=VerificationStatus.unknown,
                source="mock",
                reason="mock_verifier_exhausted",
            )
        result = self.results[self._index]
        self._index += 1
        return result

    def reset(self):
        self._index = 0


def create_default_after_state(initial_state: UiState) -> UiState:
    """创建默认的 after_state（验证成功）。"""
    return UiState(
        fingerprint=f"{initial_state.fingerprint}_after",
        package=initial_state.package,
        activity=initial_state.activity,
        screen_size=initial_state.screen_size,
        candidate_map=initial_state.candidate_map,
        control_bar_visible=initial_state.control_bar_visible,
        ocr_tokens=initial_state.ocr_tokens,
        selected_role=initial_state.selected_role,
    )


def create_success_verification() -> VerificationResult:
    """创建成功的验证结果。"""
    return VerificationResult(
        verification=VerificationStatus.success,
        source="local",
        reason="mock_success",
    )


def create_not_yet_verification() -> VerificationResult:
    """创建 not_yet 验证结果。"""
    return VerificationResult(
        verification=VerificationStatus.not_yet,
        source="local",
        reason="mock_not_yet",
    )


def create_unknown_verification() -> VerificationResult:
    """创建 unknown 验证结果。"""
    return VerificationResult(
        verification=VerificationStatus.unknown,
        source="local",
        reason="mock_unknown",
    )
