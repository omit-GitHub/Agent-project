# -*- coding: utf-8 -*-
"""OCR 引擎 — RapidOCR 单例和候选生成。"""
import os
import re
import time
from dataclasses import dataclass
from typing import Literal, Optional

from ..candidates.schemas import PixelBBox, UiCandidate


@dataclass
class OCRResult:
    """OCR 识别结果。"""
    text: str
    bbox: list[tuple[float, float]]  # 4 个角点 [(x,y), ...]
    confidence: float


class OCREngine:
    """RapidOCR 单例封装。

    进程级懒加载，不得每次观察重新初始化。
    """

    _instance: Optional["OCREngine"] = None
    _initialized: bool = False

    def __init__(self):
        self._engine = None
        self._enabled = os.environ.get("OCR_ENABLED", "true").lower() in ("true", "1", "yes")
        self._min_confidence = float(os.environ.get("OCR_MIN_CONFIDENCE", "0.35"))
        self._language = os.environ.get("OCR_LANGUAGE", "ch")

    @classmethod
    def get_instance(cls) -> "OCREngine":
        """获取单例。"""
        if cls._instance is None or not cls._initialized:
            cls._instance = cls()
            cls._initialized = True
        return cls._instance

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _lazy_init(self):
        """懒加载 RapidOCR。"""
        if self._engine is not None:
            return
        if not self._enabled:
            return
        try:
            from rapidocr_onnxruntime import RapidOCR
            self._engine = RapidOCR()
        except ImportError:
            self._enabled = False

    def detect(self, screenshot_path: str) -> list[UiCandidate]:
        """执行 OCR 识别，返回候选列表。

        Args:
            screenshot_path: 截图文件路径

        Returns:
            UiCandidate 列表（source=ocr, kind=text）
        """
        if not self._enabled:
            return []

        self._lazy_init()
        if self._engine is None:
            return []

        start = time.time()
        try:
            ocr_result, _ = self._engine(screenshot_path)
        except Exception:
            return []

        candidates = []
        for i, (box, text, confidence) in enumerate(ocr_result):
            conf = float(confidence) if confidence else 0.0

            # 过滤低置信度
            if conf < self._min_confidence:
                continue

            # 过滤空串和噪声
            text = text.strip()
            if not text or len(text) < 1:
                continue

            # 过滤状态栏时间等明显噪声
            if self._is_noise(text):
                continue

            # 构建 bbox
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            bbox = PixelBBox(
                x1=max(0, int(min(xs))),
                y1=max(0, int(min(ys))),
                x2=int(max(xs)),
                y2=int(max(ys)),
            )

            # OCR 框是文字锚点，clickable_likelihood <= 0.55
            candidate = UiCandidate(
                candidate_id=f"T{i+1}",
                source="ocr",
                kind="text",
                text=text,
                bbox_px=bbox,
                text_bbox_px=bbox,  # OCR 的 bbox 就是文字 bbox
                confidence=conf,
                clickable_likelihood=min(0.55, conf * 0.7),
            )
            candidates.append(candidate)

        return candidates

    def _is_noise(self, text: str) -> bool:
        """判断是否为噪声文本。"""
        # 状态栏时间（如 14:22）
        if re.match(r"^\d{1,2}:\d{2}$", text):
            return True
        # 日期（如 08月19日）
        if re.match(r"^\d{1,2}月\d{1,2}日", text):
            return True
        # 纯符号
        if re.match(r"^[\W_]+$", text):
            return True
        return False
