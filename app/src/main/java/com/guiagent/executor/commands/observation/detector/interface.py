# -*- coding: utf-8 -*-
"""Visual UI Detector 接口定义。

Detector 负责从截图中识别交互区域（图标、按钮、卡片等），
不要求正确命名图标，只要求定位准确。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DetectionResult:
    """单个检测结果。"""
    kind: str  # "icon", "button", "card", "image", "text", "unknown"
    bbox_px: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float
    label: Optional[str] = None  # 可选标签


class UiDetector(ABC):
    """UI Detector 抽象基类。"""

    @abstractmethod
    def detect(self, screenshot_path: str) -> List[DetectionResult]:
        """从截图中检测交互区域。

        Args:
            screenshot_path: 截图文件路径

        Returns:
            检测结果列表
        """
        pass

    @abstractmethod
    def get_metadata(self) -> dict:
        """获取 detector 元信息。

        Returns:
            {"name": str, "version": str, "device": str}
        """
        pass
