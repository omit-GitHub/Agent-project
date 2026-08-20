# -*- coding: utf-8 -*-
"""Mock Visual Detector — 用于测试和基准对比。

生成规则的网格候选，模拟 detector 输出。
"""
from typing import List

from .interface import UiDetector, DetectionResult


class MockDetector(UiDetector):
    """模拟 detector，生成规则网格候选。"""

    def __init__(self, grid_size: int = 200, min_confidence: float = 0.7):
        self.grid_size = grid_size
        self.min_confidence = min_confidence

    def detect(self, screenshot_path: str) -> List[DetectionResult]:
        """生成网格候选。"""
        from PIL import Image
        img = Image.open(screenshot_path)
        width, height = img.size

        results = []
        for y in range(0, height, self.grid_size):
            for x in range(0, width, self.grid_size):
                x2 = min(x + self.grid_size, width)
                y2 = min(y + self.grid_size, height)
                # 模拟置信度（中心区域更高）
                cx = (x + x2) / 2
                cy = (y + y2) / 2
                conf = 1.0 - (abs(cx - width/2) / width + abs(cy - height/2) / height) * 0.5
                if conf >= self.min_confidence:
                    results.append(DetectionResult(
                        kind="button",
                        bbox_px=(x, y, x2, y2),
                        confidence=conf,
                    ))
        return results

    def get_metadata(self) -> dict:
        return {
            "name": "MockDetector",
            "version": "1.0.0",
            "device": "cpu",
        }
