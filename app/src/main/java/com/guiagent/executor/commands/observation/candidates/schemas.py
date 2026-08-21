# -*- coding: utf-8 -*-
"""候选数据模型。"""
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class PixelBBox(BaseModel):
    """像素坐标边界框。"""
    x1: int = Field(ge=0)
    y1: int = Field(ge=0)
    x2: int = Field(gt=0)
    y2: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_order(self):
        if self.x1 >= self.x2 or self.y1 >= self.y2:
            raise ValueError(f"invalid bbox: x1={self.x1} >= x2={self.x2} or y1={self.y1} >= y2={self.y2}")
        return self

    def center(self) -> tuple[int, int]:
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)

    def area(self) -> int:
        return (self.x2 - self.x1) * (self.y2 - self.y1)


class UiCandidate(BaseModel):
    """UI 交互候选。"""
    candidate_id: str
    source: Literal["ocr", "visual", "ocr+visual", "memory", "vlm_fallback"]
    kind: Literal[
        "text", "icon", "button", "menu_item", "card", "image",
        "input", "slider", "progress", "switch", "unknown"
    ]
    text: Optional[str] = None
    bbox_px: PixelBBox
    text_bbox_px: Optional[PixelBBox] = None  # OCR 文字 bbox（与 bbox_px 可能不同）
    detector_label: Optional[str] = None  # 检测器标签（如 "play_button"）
    confidence: float = Field(ge=0.0, le=1.0)
    clickable_likelihood: float = Field(ge=0.0, le=1.0)
    # ── 敏感性/语义字段（供 Action Guard 做显式敏感判定，优先于 subgoal 关键词）──
    risk_category: Optional[str] = None          # "payment" / "delete" / "send" / "logout" / "password" / "authorization" / ...
    sensitive_category: Optional[str] = None     # 通用敏感分类
    action_semantics: Optional[str] = None       # 候选动作语义描述
    metadata: dict = Field(default_factory=dict)


class ProviderResult(BaseModel):
    """Provider 返回结果。"""
    provider: Literal["ocr", "visual"]
    status: Literal["ok", "empty", "timeout", "failed", "circuit_open", "disabled"]
    candidates: list[UiCandidate] = Field(default_factory=list)
    latency_ms: float
    error_code: Optional[str] = None


class CandidateMap(BaseModel):
    """候选地图（一次观察的完整结果）。"""
    screen_version: str
    package: str
    activity: str
    page_type: str = "unknown"
    width: int
    height: int
    screenshot_path: str
    annotated_path: str  # SoM 标注图路径
    candidates: list[UiCandidate]
    ocr_status: Literal["ok", "empty", "timeout", "failed", "circuit_open", "disabled"]
    detector_status: Literal["ok", "empty", "timeout", "failed", "circuit_open", "disabled"]
    degradation_mode: Literal["none", "ocr_only", "visual_only", "no_candidates"]
    provider_latency_ms: dict[str, float] = Field(default_factory=dict)
    created_at: float
