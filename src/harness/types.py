# -*- coding: utf-8 -*-
"""Harness 最小依赖类型。

独立定义，不依赖任何外部项目。本模块提供：
  - BBox：像素边界框
  - Candidate：UI 交互候选（最小字段集）
  - CandidateMap：一次观察的候选集合

这些类型是 Harness 的最小 UI 观测语义。上层接入真实系统时（Android / Web / 桌面），
只需在边界把系统的 UI 表示转成本模块类型即可。
"""
from dataclasses import dataclass, field
from typing import Literal, Optional


# ─────────────── 边界框 ───────────────

@dataclass(frozen=True)
class BBox:
    """像素边界框（不可变）。

    约束：x1 < x2，y1 < y2，所有坐标 ≥ 0。
    """
    x1: int
    y1: int
    x2: int
    y2: int

    def __post_init__(self):
        if self.x1 < 0 or self.y1 < 0:
            raise ValueError(f"BBox has negative origin: {self}")
        if self.x1 >= self.x2 or self.y1 >= self.y2:
            raise ValueError(f"BBox is degenerate: {self}")

    def center(self) -> tuple[int, int]:
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)

    def area(self) -> int:
        return (self.x2 - self.x1) * (self.y2 - self.y1)

    def fits_in(self, width: int, height: int) -> bool:
        """是否完全位于 (width, height) 屏幕内。"""
        return self.x2 <= width and self.y2 <= height


# ─────────────── 候选 ───────────────

@dataclass
class Candidate:
    """UI 交互候选（最小字段集）。

    字段：
      - candidate_id：唯一标识
      - bbox_px：像素边界框
      - risk_category：显式风险分类（如 "payment" / "delete" / "logout"）
      - sensitive_category：通用敏感分类
      - action_semantics：动作语义描述
      - text：候选关联的文字（可选）
      - confidence：检测置信度 (0..1)
      - clickable_likelihood：可点击可能性 (0..1)
      - source：来源（"ocr" / "visual" / "memory" / ...）
      - kind：控件类型（"button" / "text" / "icon" / ...）
    """
    candidate_id: str
    bbox_px: BBox
    risk_category: Optional[str] = None
    sensitive_category: Optional[str] = None
    action_semantics: Optional[str] = None
    text: Optional[str] = None
    confidence: float = 0.0
    clickable_likelihood: float = 0.0
    source: str = "unknown"
    kind: str = "unknown"


# ─────────────── 候选地图 ───────────────

@dataclass
class CandidateMap:
    """一次观察的候选集合。

    字段：
      - screen_version：本次候选生成的版本/指纹（用于匹配 action.candidate_map_fingerprint）
      - package：当前 App 包名
      - activity：当前 Activity
      - width / height：屏幕像素尺寸
      - candidates：候选列表
      - created_at：生成时间戳
    """
    screen_version: str
    package: str
    activity: str
    width: int
    height: int
    candidates: list = field(default_factory=list)
    created_at: float = 0.0
