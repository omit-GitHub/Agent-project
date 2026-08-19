# -*- coding: utf-8 -*-
"""VLM 数据模型 — Pydantic 定义。

Phase A 更新：
- 添加 PixelBBox（像素坐标）
- NextAction 添加 tap_candidate 和 tap_visual 动作类型
- 添加 model_validator 强制动作约束

对应 Cursor 任务书 §3。
所有 VLM 返回必须使用这些 schema 校验，不合法的返回触发重试或报错。
"""
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, model_validator


class BBox(BaseModel):
    """归一化边界框（0~1 范围）。"""
    x1: float = Field(ge=0.0, le=1.0)
    y1: float = Field(ge=0.0, le=1.0)
    x2: float = Field(ge=0.0, le=1.0)
    y2: float = Field(ge=0.0, le=1.0)

    def center(self) -> tuple[float, float]:
        """返回 (cx, cy) 中心坐标。"""
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    def area(self) -> float:
        """返回面积（0~1 范围）。"""
        return max(0.0, (self.x2 - self.x1) * (self.y2 - self.y1))


class PixelBBox(BaseModel):
    """像素坐标边界框。"""
    x1: int = Field(ge=0)
    y1: int = Field(ge=0)
    x2: int = Field(gt=0)
    y2: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_order(self):
        if self.x1 >= self.x2 or self.y1 >= self.y2:
            raise ValueError("invalid bbox")
        return self

    def center(self) -> tuple[int, int]:
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)


class NextAction(BaseModel):
    """VLM 单步动作建议。

    Phase A 更新：
    - 添加 tap_candidate（选择候选 ID）
    - 添加 tap_visual（兜底像素坐标点击）
    - 添加 model_validator 强制动作约束
    """
    type: Literal[
        "tap_candidate", "tap_visual", "swipe", "type_text", "remote_key", "media_key",
        "wait", "back", "reveal_controls", "done", "ask_user"
    ]
    candidate_id: str | None = None  # tap_candidate 专用
    target_label: str | None = None
    bbox_px: PixelBBox | None = None  # tap_visual 专用（像素坐标）
    bbox_normalized: BBox | None = None  # 兼容旧格式
    direction: Literal["up", "down", "left", "right"] | None = None
    distance: float | None = Field(default=None, ge=0.05, le=0.95)
    text: str | None = None
    key: str | None = None
    wait_ms: int | None = Field(default=None, ge=100, le=3000)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)

    @model_validator(mode="after")
    def validate_action(self):
        """强制动作约束。"""
        if self.type == "tap_candidate":
            if not self.candidate_id:
                raise ValueError("tap_candidate requires candidate_id")
            if self.bbox_px:
                raise ValueError("tap_candidate must not have bbox_px")
        elif self.type == "tap_visual":
            if not self.bbox_px:
                raise ValueError("tap_visual requires bbox_px")
            if not self.target_label:
                raise ValueError("tap_visual requires target_label")
        elif self.type == "type_text":
            if not self.text:
                raise ValueError("type_text requires text")
        elif self.type == "swipe":
            if not self.direction:
                raise ValueError("swipe requires direction")
        elif self.type in ("remote_key", "media_key"):
            if not self.key:
                raise ValueError(f"{self.type} requires key")
        return self


class ObserveResult(BaseModel):
    """VLM 观察结果。"""
    page_type: Literal["player", "detail", "search", "list", "grid", "dialog", "overlay", "unknown"]
    control_bar_visible: bool | None = None
    overlay: str | None = None
    task_status: Literal["in_progress", "done", "blocked", "unknown"]
    next_action: NextAction
    target_evidence: str
    confidence: float = Field(ge=0.0, le=1.0)


class VerifyResult(BaseModel):
    """VLM 验证结果。"""
    verification: Literal["success", "not_yet", "failed", "unknown"]
    reason: str
    observed_state: dict[str, Any] = Field(default_factory=dict)


class ActionExecutionResult(BaseModel):
    """动作执行结果（Harness 层返回）。"""
    ok: bool
    action: NextAction
    error_code: str | None = None
    detail: str | None = None


class VlmLoopResult(BaseModel):
    """Action Loop 完整结果。"""
    ok: bool
    status: Literal["success", "blocked", "failed", "timeout"]
    steps: list[dict[str, Any]] = Field(default_factory=list)
    final_message: str = ""
    verification: VerifyResult | None = None
