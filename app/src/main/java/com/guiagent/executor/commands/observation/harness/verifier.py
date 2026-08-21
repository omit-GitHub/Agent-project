# -*- coding: utf-8 -*-
"""分层 Verifier — 本地信号优先 + 严格四态输出。

严格 success 条件（约束 #4）：
  1. action.expected_package 命中 after.package
  2. action.expected_activity 命中 after.activity（且 package 一致）
  3. control_bar_visible: false → true
  4. action.target_role 命中 after.selected_role
  5. action.target_role 对应文字 ∈ after.ocr_tokens - before.ocr_tokens

其他任何变化（layout、非目标 OCR、局部图像）→ not_yet/unknown，绝不 success。

unknown 累计超限 → VLM fallback；VLM 不可用 → unknown。
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
    """本地快速验证器。

    严格按约束 #4 的 success 条件判断；其他一律 not_yet / unknown。
    """

    def verify(
        self,
        before: UiState,
        after: UiState,
        action: ActionSpec,
    ) -> VerificationResult:
        """基于 (before, after, action) 的本地判定。"""

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

        # 1. expected_package 命中
        if action.expected_package and after.package == action.expected_package:
            return VerificationResult(
                verification=VerificationStatus.success,
                source=VerificationSource.local,
                reason=f"reached expected package: {action.expected_package}",
                observed_state=observed,
            )

        # 2. expected_activity 命中（要求 package 一致，避免跨 App 误判）
        if (action.expected_activity
                and after.activity == action.expected_activity
                and after.package == before.package):
            return VerificationResult(
                verification=VerificationStatus.success,
                source=VerificationSource.local,
                reason=f"reached expected activity: {action.expected_activity}",
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

        # 4. target_role 命中 selected_role
        if (action.target_role
                and after.selected_role is not None
                and after.selected_role == action.target_role):
            return VerificationResult(
                verification=VerificationStatus.success,
                source=VerificationSource.local,
                reason=f"selected_role matches target: {action.target_role}",
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

        # 其他任何变化 → not_yet（本地无法判定时不谎报 success）
        return VerificationResult(
            verification=VerificationStatus.not_yet,
            source=VerificationSource.local,
            reason="no explicit target signal observed",
            observed_state=observed,
        )


# ─────────────── VLM Verifier ───────────────

class VlmVerifier:
    """VLM 视觉验证器（最后手段）。

    通过可注入 callable 调用；callable 不可用或抛错时返回 unknown。
    """

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
            # callable 返回 dict 兼容
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
    """分层验证器。

    按优先级：本地信号 → VLM fallback。
    unknown 累计超限才调用 VLM；VLM 不可用 → unknown。
    """

    def __init__(
        self,
        vlm_callable: Optional[Callable[..., Any]] = None,
        max_unknown_before_vlm: int = 1,
    ):
        self.local = LocalVerifier()
        self.vlm = VlmVerifier(vlm_callable)
        self._unknown_count = 0
        self._max_unknown_before_vlm = max_unknown_before_vlm

    def verify(
        self,
        before: UiState,
        after: UiState,
        action: ActionSpec,
    ) -> VerificationResult:
        # 本地判定
        local_result = self.local.verify(before, after, action)

        if local_result.verification != VerificationStatus.not_yet:
            # success / failed / unknown 直接返回
            if local_result.verification == VerificationStatus.unknown:
                self._unknown_count += 1
            else:
                self._unknown_count = 0
            return local_result

        # not_yet → 看是否要触发 VLM
        if self._unknown_count >= self._max_unknown_before_vlm and self.vlm._callable is not None:
            self._unknown_count = 0
            return self.vlm.verify(before, after, action)

        return local_result

    def reset_unknown_count(self):
        """新任务开始时重置 unknown 计数。"""
        self._unknown_count = 0
