# -*- coding: utf-8 -*-
"""基于 OpenCV 的真实 Visual Detector。

使用边缘检测 + 轮廓分析识别交互区域：
- 按钮：矩形轮廓，宽高比合理
- 图标：小矩形或圆形轮廓
- 卡片：大矩形轮廓
- 文字按钮：通过 OCR 辅助判断（可选）

这是真实 detector，不是 mock。性能有限但可用于 B0 smoke test。
"""
import cv2
import numpy as np
from typing import List, Tuple

from .interface import UiDetector, DetectionResult


class OpenCVDetector(UiDetector):
    """OpenCV 基于规则的 UI 元素检测器。"""

    def __init__(
        self,
        min_area: int = 400,      # 最小面积 (20x20)
        max_area: int = 100000,   # 最大面积
        min_confidence: float = 0.3,
    ):
        self.min_area = min_area
        self.max_area = max_area
        self.min_confidence = min_confidence

    def detect(self, screenshot_path: str) -> List[DetectionResult]:
        """从截图中检测交互区域。"""
        # 读取图像
        img = cv2.imread(screenshot_path)
        if img is None:
            return []

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # 边缘检测
        edges = cv2.Canny(blurred, 50, 150)

        # 查找轮廓
        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        results = []
        img_height, img_width = img.shape[:2]

        for contour in contours:
            area = cv2.contourArea(contour)

            # 过滤面积
            if area < self.min_area or area > self.max_area:
                continue

            # 外接矩形
            x, y, w, h = cv2.boundingRect(contour)

            # 过滤宽高比（排除过长/过扁的）
            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio > 5 or aspect_ratio < 0.2:
                continue

            # 计算置信度（基于面积和形状规则度）
            # 矩形度 = 轮廓面积 / 外接矩形面积
            rect_area = w * h
            solidity = area / rect_area if rect_area > 0 else 0

            # 置信度：矩形度越高越可能是按钮/卡片
            confidence = min(1.0, solidity * 1.2)

            if confidence < self.min_confidence:
                continue

            # 分类
            kind = self._classify_element(w, h, area, img_width, img_height)

            results.append(DetectionResult(
                kind=kind,
                bbox_px=(x, y, x + w, y + h),
                confidence=confidence,
            ))

        # 按置信度排序
        results.sort(key=lambda r: r.confidence, reverse=True)

        return results

    def _classify_element(
        self, w: int, h: int, area: int, img_w: int, img_h: int
    ) -> str:
        """根据尺寸和位置分类元素。"""
        # 卡片：大区域
        if area > 20000:
            return "card"

        # 按钮：中等大小，宽高比合理
        if 1000 < area < 20000 and 0.5 < w/h < 3:
            return "text_button"

        # 图标：小正方形
        if area < 1000 and 0.7 < w/h < 1.3:
            return "icon"

        # 菜单项：长条形
        if w > h * 2:
            return "menu_item"

        return "unknown"

    def get_metadata(self) -> dict:
        return {
            "name": "OpenCVDetector",
            "version": "1.0.0",
            "device": "cpu",
            "method": "edge_detection+contour_analysis",
        }
