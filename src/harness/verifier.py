# -*- coding: utf-8 -*-
"""分层 Verifier — 本地信号优先 + 严格四态输出。

严格 success 条件：
  1. action.expected_package 命中 after.package（且 before.package 不同 → 状态转移）
  2. action.expected_activity 命中 after.activity（且 before.activity 不同 → 状态转移，package 一致）
  3. control_bar_visible: false → true
  4. action.target_role 命中 after.selected_role
  5. action.target_role 对应文字 ∈ after.ocr_tokens - before.ocr_tokens

其他任何变化（layout、非目标 OCR、局部图像）→ not_yet/unknown，绝不 success。

Fallback 逻辑：
  - LocalVerifier 连续 not_yet 达 max_local_observations → 调 VLM
  - VLM 无法判断返回 unknown
  - unknown 不得视为 success，只能有限重观察后停止
  - VLM 不可用 + 观测耗尽 → unknown

本模块无任何外部依赖（不依赖 VLM / ADB / 具体 App）。
"""
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from .schemas import ActionSpec, UiState


# ─────────────── 枚举 ───────────────

class VerificationStatus(str, Enum):
    success = "success"
    not_yet = "not_yet"
    failed = "failed"
    unknown = "unknown"


class VerificationSource(str, Enum):
    local = "local"
    vlm = "vlm"


# ─────────────── 验证结果 ───────────────

class VerificationResult(BaseModel):
    """严格 schema 的四态验证结果。"""
    verification: VerificationStatus
    source: VerificationSource
    reason: str
    observed_state: dict = Field(default_factory=dict)


# ─────────────── Local Verifier ───────────────

class LocalVerifier:
    """本地快速验证器。严格按 success 条件判断。"""

    def verify(
        self,
        before: UiState,
        after: UiState,
        action: ActionSpec,
    ) -> VerificationResult:
        observed: dict = {
            "before_package": before.package,
            "after_package": after.package,
            "before_activity": before.activity,
            "after_activity": after.activity,
            "before_bar": before.control_bar_visible,
            "after_bar": after.control_bar_visible,
            "before_selected_role": before.selected_role,
            "after_selected_role": after.selected_role,
            "target_role": action.target_role,
            "expected_package": action.expected_package,
            "expected_activity": action.expected_activity,
        }

        # 1. expected_package 命中 — 要求状态转移 (before ≠ expected)
        if (action.expected_package
                and before.package != action.expected_package
                and after.package == action.expected_package):
            return VerificationResult(
                verification=VerificationStatus.success,
                source=VerificationSource.local,
                reason=f"package transition to expected: {action.expected_package}",
                observed_state=observed,
            )

        # 2. expected_activity 命中（package 一致 + 状态转移）
        if (action.expected_activity
                and before.activity != action.expected_activity
                and after.activity == action.expected_activity
                and after.package == before.package):
            return VerificationResult(
                verification=VerificationStatus.success,
                source=VerificationSource.local,
                reason=f"activity transition to expected: {action.expected_activity}",
                observed_state=observed,
            )

        # 3. control_bar false → true
        if not before.control_bar_visible and after.control_bar_visible:
            return VerificationResult(
                verification=VerificationStatus.success,
                source=VerificationSource.local,
                reason="control_bar became visible",
                observed_state=observed,
            )

        # 4. target_role 命中 selected_role — 要求状态转移 (before ≠ target)
        if (action.target_role
                and before.selected_role != action.target_role
                and after.selected_role == action.target_role):
            return VerificationResult(
                verification=VerificationStatus.success,
                source=VerificationSource.local,
                reason=f"selected_role transition to target: {action.target_role}",
                observed_state=observed,
            )

        # 5. target_role 对应 OCR 出现
        if action.target_role:
            new_tokens = after.ocr_tokens - before.ocr_tokens
            if action.target_role in new_tokens:
                return VerificationResult(
                    verification=VerificationStatus.success,
                    source=VerificationSource.local,
                    reason=f"target_role OCR token appeared: {action.target_role}",
                    observed_state={**observed, "new_tokens": sorted(new_tokens)[:10]},
                )

        # 其他任何变化 → not_yet
        return VerificationResult(
            verification=VerificationStatus.not_yet,
            source=VerificationSource.local,
            reason="no explicit target signal observed",
            observed_state=observed,
        )


# ─────────────── VLM Verifier ───────────────

class VlmVerifier:
    """VLM 视觉验证器（最后手段）。通过可注入 callable 调用。"""

    def __init__(self, callable_fn: Optional[Callable[..., Any]] = None):
        self._callable = callable_fn

    def verify(
        self,
        before: UiState,
        after: UiState,
        action: ActionSpec,
    ) -> VerificationResult:
        if self._callable is None:
            return VerificationResult(
                verification=VerificationStatus.unknown,
                source=VerificationSource.vlm,
                reason="VLM callable not provided",
            )
        try:
            result = self._callable(before, after, action)
            if isinstance(result, VerificationResult):
                return result
            if isinstance(result, dict):
                return VerificationResult(
                    verification=VerificationStatus(result.get("verification", "unknown")),
                    source=VerificationSource.vlm,
                    reason=result.get("reason", ""),
                    observed_state=result.get("observed_state", {}),
                )
            return VerificationResult(
                verification=VerificationStatus.unknown,
                source=VerificationSource.vlm,
                reason=f"VLM returned unexpected type: {type(result).__name__}",
            )
        except Exception as e:
            return VerificationResult(
                verification=VerificationStatus.unknown,
                source=VerificationSource.vlm,
                reason=f"VLM error: {e}",
            )


# ─────────────── Layered Verifier ───────────────

class LayeredVerifier:
    """分层验证器：本地信号 → VLM fallback。

    Fallback 触发条件：
      - LocalVerifier 连续 not_yet 达 max_local_observations → 调 VLM
      - VLM 返回 unknown → 允许有限重观察（最多 max_vlm_unknown 次）
      - 超限 → 返回 unknown（不得视为 success）
      - VLM 不可用 + 观测耗尽 → 返回 unknown
    """

    def __init__(
        self,
        vlm_callable: Optional[Callable[..., Any]] = None,
        max_local_observations: int = 3,
        max_vlm_unknown: int = 1,
    ):
        self.local = LocalVerifier()
        self.vlm = VlmVerifier(vlm_callable)
        self._consecutive_not_yet = 0
        self._max_local_observations = max_local_observations
        self._vlm_unknown_count = 0
        self._max_vlm_unknown = max_vlm_unknown

    def verify(
        self,
        before: UiState,
        after: UiState,
        action: ActionSpec,
    ) -> VerificationResult:
        local_result = self.local.verify(before, after, action)

        # success / failed → 重置计数，直接返回
        if local_result.verification == VerificationStatus.success:
            self._consecutive_not_yet = 0
            self._vlm_unknown_count = 0
            return local_result

        if local_result.verification == VerificationStatus.failed:
            self._consecutive_not_yet = 0
            self._vlm_unknown_count = 0
            return local_result

        # not_yet → 递增计数
        self._consecutive_not_yet += 1

        # 达到本地观测阈值 → 尝试 VLM fallback
        if self._consecutive_not_yet >= self._max_local_observations:
            if self.vlm._callable is not None:
                vlm_result = self.vlm.verify(before, after, action)

                if vlm_result.verification == VerificationStatus.unknown:
                    self._vlm_unknown_count += 1
                    if self._vlm_unknown_count > self._max_vlm_unknown:
                        # VLM unknown 超限 → 返回 unknown 停止
                        self._consecutive_not_yet = 0
                        return VerificationResult(
                            verification=VerificationStatus.unknown,
                            source=VerificationSource.vlm,
                            reason=f"VLM uncertain after {self._vlm_unknown_count} attempts",
                            observed_state=vlm_result.observed_state,
                        )
                    # 第 1 次 VLM unknown → 返回 not_yet 允许继续观察
                    return VerificationResult(
                        verification=VerificationStatus.not_yet,
                        source=VerificationSource.vlm,
                        reason="VLM uncertain, will re-observe",
                        observed_state=vlm_result.observed_state,
                    )

                # VLM 给出确定结论（success/failed）
                self._consecutive_not_yet = 0
                self._vlm_unknown_count = 0
                return vlm_result

            # VLM 不可用 → 观测耗尽后返回 unknown
            if self._consecutive_not_yet >= self._max_local_observations + self._max_vlm_unknown + 1:
                return VerificationResult(
                    verification=VerificationStatus.unknown,
                    source=VerificationSource.local,
                    reason="exhausted observation budget without VLM",
                    observed_state=local_result.observed_state,
                )

        return local_result

    def reset(self):
        """重置所有计数器。"""
        self._consecutive_not_yet = 0
        self._vlm_unknown_count = 0

    # 向后兼容
    def reset_unknown_count(self):
        """向后兼容：重置计数器。"""
        self.reset()
