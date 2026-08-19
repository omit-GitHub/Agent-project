# -*- coding: utf-8 -*-
"""候选构建器 — 并行执行 OCR 和 Visual Detector，合并结果。

Phase A 初版只实现 OCR 通路，Visual Detector 在 Phase B 实现。
"""
import os
import time
from typing import Optional

from ..screen.models import ScreenshotFrame
from ..screen.provider import AdbScreenshotProvider
from ..ocr.engine import OCREngine
from .schemas import CandidateMap, ProviderResult, UiCandidate
from .fingerprint import ScreenIdentity, FingerprintBuilder, DynamicRegionMasker


class CandidateBuilder:
    """候选构建器。

    并行调用 OCR 和 Visual Detector provider，合并结果生成 CandidateMap。
    Phase A 初版只有 OCR provider，Visual Detector 在 Phase B 添加。
    """

    def __init__(
        self,
        screenshot_provider: Optional[AdbScreenshotProvider] = None,
        output_dir: str = "./runtime/screenshots",
    ):
        self.screenshot_provider = screenshot_provider or AdbScreenshotProvider(output_dir=output_dir)
        self.ocr_engine = OCREngine.get_instance()
        self.fingerprint_builder = FingerprintBuilder()

    def build(
        self,
        request_id: Optional[str] = None,
        package: str = "",
        activity: str = "",
        page_type: str = "unknown",
        control_bar_visible: Optional[bool] = None,
        overlay: Optional[str] = None,
    ) -> CandidateMap:
        """构建候选地图。

        Args:
            request_id: 请求 ID（用于截图文件名）
            package: 当前 App 包名
            activity: 当前 Activity
            page_type: 页面类型
            control_bar_visible: 控制条是否可见
            overlay: 当前浮层类型

        Returns:
            CandidateMap
        """
        start_time = time.time()

        # 1. 截图
        frame = self.screenshot_provider.capture(request_id=request_id)

        # 2. 并行执行 provider（Phase A 只有 OCR）
        ocr_result = self._run_ocr(frame)

        # 3. 构建 UI fingerprint
        stable_ocr_tokens = self.fingerprint_builder.build_from_ocr(
            [(c.text or "", c.bbox_px.center()[0], c.bbox_px.center()[1], c.confidence)
             for c in ocr_result.candidates],
            frame.width,
            frame.height,
        )

        candidate_layout = self.fingerprint_builder.build_from_candidates(
            [(c.kind, c.bbox_px.x1, c.bbox_px.y1, c.bbox_px.x2, c.bbox_px.y2)
             for c in ocr_result.candidates],
            frame.width,
            frame.height,
        )

        identity = ScreenIdentity(
            package=package,
            activity=activity,
            page_type=page_type,
            control_bar_visible=control_bar_visible,
            overlay=overlay,
            stable_ocr_tokens=stable_ocr_tokens,
            candidate_layout=candidate_layout,
        )

        screen_signature = self.fingerprint_builder.build(identity)
        screen_version = f"{screen_signature}|{frame.captured_at}"

        # 4. 生成 CandidateMap
        candidate_map = CandidateMap(
            screen_version=screen_version,
            package=package,
            activity=activity,
            page_type=page_type,
            width=frame.width,
            height=frame.height,
            screenshot_path=frame.path,
            annotated_path=frame.path,  # Phase A 还没有 SoM 标注
            candidates=ocr_result.candidates,
            ocr_status=ocr_result.status,
            detector_status="disabled",  # Phase B 启用
            degradation_mode="ocr_only" if ocr_result.status == "ok" else "no_candidates",
            provider_latency_ms={"ocr": ocr_result.latency_ms},
            created_at=time.time(),
        )

        # 5. 更新缓存
        from ..observation_cache import update_observation_from_candidate_map
        update_observation_from_candidate_map(candidate_map)

        return candidate_map

    def _run_ocr(self, frame: ScreenshotFrame) -> ProviderResult:
        """执行 OCR provider。

        Returns:
            ProviderResult
        """
        start = time.time()

        if not self.ocr_engine.enabled:
            return ProviderResult(
                provider="ocr",
                status="disabled",
                latency_ms=0,
            )

        try:
            candidates = self.ocr_engine.detect(frame.path)
            latency = (time.time() - start) * 1000

            status = "ok" if candidates else "empty"
            return ProviderResult(
                provider="ocr",
                status=status,
                candidates=candidates,
                latency_ms=latency,
            )

        except Exception as e:
            latency = (time.time() - start) * 1000
            return ProviderResult(
                provider="ocr",
                status="failed",
                latency_ms=latency,
                error_code=str(e),
            )
