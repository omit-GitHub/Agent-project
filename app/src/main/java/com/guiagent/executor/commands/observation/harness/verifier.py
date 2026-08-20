# -*- coding: utf-8 -*-
"""Verifier — 分层结果验证机制。

验证优先级（从低成本到高成本）：
  1. 包名/Activity 变化
  2. 目标 OCR 文字出现/消失
  3. 候选布局变化
  4. 目标局部 patch 变化
  5. 选中态/弹窗/控制条检测
  6. VLM 视觉验证（最后手段）

unknown 与 success 严格区分，避免"调用未报错"被误判为成功。
"""
import hashlib
import time
from dataclasses import dataclass
from typing import Literal, Optional

from ..candidates.schemas import CandidateMap


@dataclass
class VerificationResult:
    """验证结果。"""
    status: Literal["success", "not_yet", "failed", "unknown"]
    level: str = ""          # 验证层级（local_ocr, local_layout, vlm, ...）
    reason: str = ""
    evidence: dict = None

    def __post_init__(self):
        if self.evidence is None:
            self.evidence = {}


class LocalVerifier:
    """本地快速验证器。

    不依赖 VLM，使用 OCR 文字、候选布局、像素 patch 等信号。
    """

    def __init__(self):
        self._last_ocr_tokens = set()
        self._last_layout_hash = ""

    def check_page_change(
        self,
        before_pkg: str,
        after_pkg: str,
        before_activity: str,
        after_activity: str,
    ) -> VerificationResult:
        """检查包名/Activity 是否变化。"""
        if before_pkg != after_pkg:
            return VerificationResult(
                status="success",
                level="local_page",
                reason=f"Package changed: {before_pkg} -> {after_pkg}",
                evidence={"before_pkg": before_pkg, "after_pkg": after_pkg},
            )
        return VerificationResult(
            status="unknown",
            level="local_page",
            reason="Package unchanged",
        )

    def check_ocr_target(
        self,
        before_tokens: set,
        after_tokens: set,
        target_text: str,
        should_appear: bool = True,
    ) -> VerificationResult:
        """检查目标 OCR 文字是否出现/消失。"""
        new_tokens = after_tokens - before_tokens
        removed_tokens = before_tokens - after_tokens

        if should_appear:
            # 目标文字应该出现
            for token in new_tokens:
                if target_text.lower() in token.lower():
                    return VerificationResult(
                        status="success",
                        level="local_ocr",
                        reason=f"Target '{target_text}' appeared in OCR",
                        evidence={"new_token": token},
                    )
            return VerificationResult(
                status="not_yet" if after_tokens else "failed",
                level="local_ocr",
                reason=f"Target '{target_text}' not found in new OCR tokens",
                evidence={"new_tokens": list(new_tokens)[:5]},
            )
        else:
            # 目标文字应该消失
            for token in removed_tokens:
                if target_text.lower() in token.lower():
                    return VerificationResult(
                        status="success",
                        level="local_ocr",
                        reason=f"Target '{target_text}' disappeared from OCR",
                    )
            return VerificationResult(
                status="unknown",
                level="local_ocr",
                reason=f"Cannot confirm '{target_text}' disappearance",
            )

    def check_layout_change(
        self,
        before_map: Optional[CandidateMap],
        after_map: Optional[CandidateMap],
    ) -> VerificationResult:
        """检查候选布局是否变化。"""
        if before_map is None or after_map is None:
            return VerificationResult(
                status="unknown",
                level="local_layout",
                reason="Missing candidate map",
            )

        before_count = len(before_map.candidates)
        after_count = len(after_map.candidates)

        if before_count != after_count:
            return VerificationResult(
                status="success",
                level="local_layout",
                reason=f"Candidate count changed: {before_count} -> {after_count}",
                evidence={"before": before_count, "after": after_count},
            )

        # 检查候选位置是否有显著变化
        before_positions = set()
        for c in before_map.candidates:
            pos = (c.bbox_px.x1 // 50, c.bbox_px.y1 // 50)
            before_positions.add(pos)

        after_positions = set()
        for c in after_map.candidates:
            pos = (c.bbox_px.x1 // 50, c.bbox_px.y1 // 50)
            after_positions.add(pos)

        if before_positions != after_positions:
            return VerificationResult(
                status="success",
                level="local_layout",
                reason="Candidate positions changed significantly",
            )

        return VerificationResult(
            status="not_yet",
            level="local_layout",
            reason="Layout unchanged",
        )

    def check_control_bar(
        self,
        before_visible: Optional[bool],
        after_visible: Optional[bool],
        should_be_visible: bool = True,
    ) -> VerificationResult:
        """检查控制条是否出现/消失。"""
        if after_visible is None:
            return VerificationResult(
                status="unknown",
                level="local_control_bar",
                reason="Control bar status unknown",
            )

        if should_be_visible and after_visible:
            return VerificationResult(
                status="success",
                level="local_control_bar",
                reason="Control bar appeared",
            )
        elif not should_be_visible and not after_visible:
            return VerificationResult(
                status="success",
                level="local_control_bar",
                reason="Control bar hidden as expected",
            )
        else:
            return VerificationResult(
                status="failed",
                level="local_control_bar",
                reason=f"Control bar visibility mismatch: expected={should_be_visible}, actual={after_visible}",
            )


class VlmVerifier:
    """VLM 视觉验证器（最后手段）。

    仅在本地验证无法判定时调用。
    """

    def __init__(self, vlm_client=None):
        self._client = vlm_client

    def verify(
        self,
        screenshot_path: str,
        subgoal: str,
        expected: str,
        action_description: str = "",
    ) -> VerificationResult:
        """调用 VLM 进行视觉验证。"""
        if self._client is None:
            return VerificationResult(
                status="unknown",
                level="vlm",
                reason="VLM client not available",
            )

        try:
            result = self._client.verify(
                screenshot_path=screenshot_path,
                subgoal=subgoal,
                action={"description": action_description},
                expected=expected,
            )

            return VerificationResult(
                status=result.verification,
                level="vlm",
                reason=result.reason,
                evidence=result.observed_state,
            )
        except Exception as e:
            return VerificationResult(
                status="unknown",
                level="vlm",
                reason=f"VLM verification error: {e}",
            )


class LayeredVerifier:
    """分层验证器。

    按优先级依次尝试本地验证，失败时才调用 VLM。
    """

    def __init__(self, vlm_client=None):
        self.local = LocalVerifier()
        self.vlm = VlmVerifier(vlm_client)
        self._unknown_count = 0
        self._max_unknown_retries = 1  # unknown 最多重试 1 次

    def verify(
        self,
        before_pkg: str,
        after_pkg: str,
        before_activity: str,
        after_activity: str,
        before_ocr_tokens: set,
        after_ocr_tokens: set,
        before_map: Optional[CandidateMap],
        after_map: Optional[CandidateMap],
        before_control_bar: Optional[bool],
        after_control_bar: Optional[bool],
        target_text: str = "",
        should_appear: bool = True,
        should_bar_be_visible: bool = True,
        vlm_screenshot: Optional[str] = None,
        vlm_subgoal: str = "",
        vlm_expected: str = "",
    ) -> VerificationResult:
        """分层验证。

        Returns:
            VerificationResult
        """
        # Level 1: 包名/Activity 变化
        result = self.local.check_page_change(
            before_pkg, after_pkg, before_activity, after_activity,
        )
        if result.status == "success":
            return result

        # Level 2: 目标 OCR 文字出现/消失
        if target_text:
            result = self.local.check_ocr_target(
                before_ocr_tokens, after_ocr_tokens,
                target_text, should_appear,
            )
            if result.status in ("success", "failed"):
                return result

        # Level 3: 候选布局变化
        result = self.local.check_layout_change(before_map, after_map)
        if result.status == "success":
            return result

        # Level 4: 控制条状态
        result = self.local.check_control_bar(
            before_control_bar, after_control_bar, should_bar_be_visible,
        )
        if result.status in ("success", "failed"):
            return result

        # Level 5: VLM 视觉验证（最后手段）
        if vlm_screenshot and vlm_subgoal:
            if self._unknown_count < self._max_unknown_retries:
                self._unknown_count += 1
                return self.vlm.verify(
                    screenshot_path=vlm_screenshot,
                    subgoal=vlm_subgoal,
                    expected=vlm_expected,
                )
            else:
                return VerificationResult(
                    status="unknown",
                    level="vlm_skipped",
                    reason=f"Max unknown retries ({self._max_unknown_retries}) exceeded",
                )

        return VerificationResult(
            status="unknown",
            level="exhausted",
            reason="All local checks inconclusive, no VLM available",
        )

    def reset_unknown_count(self):
        """重置 unknown 计数（新任务开始时调用）。"""
        self._unknown_count = 0
