# -*- coding: utf-8 -*-
"""Visual Detector 包。"""
from .interface import UiDetector, DetectionResult
from .config import (
    DETECTOR_TYPE,
    MOCK_GRID_SIZE,
    MOCK_MIN_CONFIDENCE,
    OMNIPARSER_URL,
    OMNIPARSER_TIMEOUT_MS,
    OMNIPARSER_MIN_CONFIDENCE,
)


def create_detector() -> UiDetector:
    """根据配置创建 detector 实例。"""
    if DETECTOR_TYPE == "mock":
        from .mock_detector import MockDetector
        return MockDetector(
            grid_size=MOCK_GRID_SIZE,
            min_confidence=MOCK_MIN_CONFIDENCE,
        )
    elif DETECTOR_TYPE == "omniparser":
        from .sidecar_client import SidecarDetector
        return SidecarDetector(
            url=OMNIPARSER_URL,
            timeout_ms=OMNIPARSER_TIMEOUT_MS,
            min_confidence=OMNIPARSER_MIN_CONFIDENCE,
        )
    else:
        raise ValueError(f"Unknown detector type: {DETECTOR_TYPE}")


__all__ = [
    "UiDetector",
    "DetectionResult",
    "create_detector",
    "DETECTOR_TYPE",
]
