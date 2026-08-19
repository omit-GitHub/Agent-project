# -*- coding: utf-8 -*-
"""UI 指纹生成器 — 程序化生成 screen_signature。

不使用整图 hash，而是根据结构化状态确定性生成。
VLM 只输出 page_type/control_bar_visible/overlay 等字段，
FingerprintBuilder 负责归一化、排序、canonical JSON 序列化和哈希。
"""
import hashlib
import json
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ScreenIdentity(BaseModel):
    """屏幕身份（用于生成 fingerprint）。"""
    signature_schema_version: Literal["v1"] = "v1"
    package: str
    activity: str
    page_type: str
    control_bar_visible: Optional[bool] = None
    overlay: Optional[str] = None
    stable_ocr_tokens: list[tuple[str, int, int]] = Field(default_factory=list)  # (text, qx, qy)
    candidate_layout: list[tuple[str, int, int, int, int]] = Field(default_factory=list)  # (kind, qx1, qy1, qx2, qy2)


class DynamicRegionMasker:
    """动态区域掩码器 — 排除视频内容 ROI 和动态 OCR token。

    player 页面：
    - 排除视频内容 ROI（通常是屏幕中央大部分区域）
    - 只保留顶部栏、底部控制条、菜单、弹窗中的文字
    - 字幕、弹幕、滚动通知、系统时钟、播放时间等动态 token 永不进入 signature
    """

    # 动态 token 模式（永不进入 stable_ocr_tokens）
    DYNAMIC_PATTERNS = [
        r"^\d{1,2}:\d{2}$",           # 时间（14:22）
        r"^\d{1,2}月\d{1,2}日",       # 日期
        r"^\d+%",                      # 百分比
        r"^[\d.]+/\d+",               # 进度（1:23/45:30）
        r"^[\d.]+倍",                 # 倍速（动态显示）
        r"^[0-9a-f]{8}",             # hash/ID
    ]

    def __init__(self, page_type: str):
        self.page_type = page_type

    def is_dynamic_token(self, text: str) -> bool:
        """判断是否为动态 token（应排除）。"""
        text = text.strip()
        for pattern in self.DYNAMIC_PATTERNS:
            if re.match(pattern, text):
                return True
        return False

    def is_video_roi(self, x: int, y: int, width: int, height: int) -> bool:
        """判断坐标是否在视频内容 ROI 内。

        默认视频区域是屏幕中央 60%×60% 区域。
        """
        if self.page_type != "player":
            return False

        # 视频区域边界（保守估计）
        margin_x = int(width * 0.20)
        margin_y = int(height * 0.15)

        return (
            margin_x <= x <= width - margin_x and
            margin_y <= y <= height - margin_y
        )


class FingerprintBuilder:
    """UI 指纹构建器。

    生成规则：
    1. 字符串清洗、枚举归一化
    2. 位置量化到 2%~5% 网格
    3. 列表排序
    4. canonical JSON 序列化
    5. SHA-256 哈希
    """

    # 位置量化网格（2%）
    QUANTIZE_GRID = 0.02

    def __init__(self, masker: Optional[DynamicRegionMasker] = None):
        self.masker = masker

    def build(self, identity: ScreenIdentity) -> str:
        """生成 screen_signature。

        Returns:
            screen_signature 字符串

        Format:
            debug_key|layout_hash

        Where:
            debug_key = v1|package|activity|page_type|bar_state|overlay
            layout_hash = sha256(canonical_json(stable_ocr_tokens, candidate_layout))[:16]
        """
        # 构建 debug key（可读部分）
        bar_state = "bar" if identity.control_bar_visible else "no_bar"
        overlay = identity.overlay or "none"
        debug_key = f"v1|{identity.package}|{identity.activity}|{identity.page_type}|{bar_state}|{overlay}"

        # 构建结构化输入
        structured_input = {
            "stable_ocr_tokens": sorted(identity.stable_ocr_tokens),
            "candidate_layout": sorted(identity.candidate_layout),
        }

        # canonical JSON 序列化
        canonical_json = json.dumps(structured_input, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

        # SHA-256 哈希
        layout_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()[:16]

        # 组合
        return f"{debug_key}|{layout_hash}"

    def quantize_position(self, pos: float, max_value: int) -> int:
        """量化位置到网格。

        Args:
            pos: 原始像素位置
            max_value: 屏幕宽度或高度

        Returns:
            量化后的网格坐标（0-50）
        """
        normalized = pos / max_value
        quantized = int(normalized / self.QUANTIZE_GRID)
        return min(50, max(0, quantized))

    def build_from_ocr(
        self,
        ocr_tokens: list[tuple[str, int, int, int]],  # (text, x, y, confidence)
        width: int,
        height: int,
    ) -> list[tuple[str, int, int]]:
        """从 OCR token 构建 stable_ocr_tokens。

        Args:
            ocr_tokens: (text, x, y, confidence) 列表
            width: 屏幕宽度
            height: 屏幕高度

        Returns:
            (text, qx, qy) 列表（已量化、排序、过滤动态 token）
        """
        stable = []
        for text, x, y, conf in ocr_tokens:
            # 过滤动态 token
            if self.masker and self.masker.is_dynamic_token(text):
                continue

            # 过滤视频 ROI
            if self.masker and self.masker.is_video_roi(x, y, width, height):
                continue

            # 量化位置
            qx = self.quantize_position(x, width)
            qy = self.quantize_position(y, height)

            stable.append((text.strip(), qx, qy))

        # 排序（按位置）
        return sorted(stable, key=lambda t: (t[1], t[2], t[0]))

    def build_from_candidates(
        self,
        candidates: list[tuple[str, int, int, int, int]],  # (kind, x1, y1, x2, y2)
        width: int,
        height: int,
    ) -> list[tuple[str, int, int, int, int]]:
        """从候选布局构建 candidate_layout。

        Args:
            candidates: (kind, x1, y1, x2, y2) 列表
            width: 屏幕宽度
            height: 屏幕高度

        Returns:
            (kind, qx1, qy1, qx2, qy2) 列表（已量化、排序）
        """
        layout = []
        for kind, x1, y1, x2, y2 in candidates:
            qx1 = self.quantize_position(x1, width)
            qy1 = self.quantize_position(y1, height)
            qx2 = self.quantize_position(x2, width)
            qy2 = self.quantize_position(y2, height)
            layout.append((kind, qx1, qy1, qx2, qy2))

        # 排序
        return sorted(layout)
