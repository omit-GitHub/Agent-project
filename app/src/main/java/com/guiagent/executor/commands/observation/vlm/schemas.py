# -*- coding: utf-8 -*-
"""VLM 数据模型 — Pydantic 定义。

对应 Cursor 任务书 §3。
所有 VLM 返回必须使用这些 schema 校验，不合法的返回触发重试或报错。
"""
from typing import Any, Literal
from pydantic import BaseModel, Field


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


class NextAction(BaseModel):
    """VLM 单步动作建议。"""
    type: Literal[
        "tap", "swipe", "type_text", "remote_key", "media_key",
        "wait", "back", "reveal_controls", "done", "ask_user"
    ]
    target_label: str | None = None
    bbox_normalized: BBox | None = None
    direction: Literal["up", "down", "left", "right"] | None = None
    distance: float | None = Field(default=None, ge=0.05, le=0.95)
    text: str | None = None
    key: str | None = None
    wait_ms: int | None = Field(default=None, ge=100, le=3000)


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
