# -*- coding: utf-8 -*-
"""VLM 子包 — VLM Client + Prompt + Schema + Screenshot。"""
from .client import QwenVlmClient, VlmClientError, VlmInvalidOutput
from .schemas import (
    BBox,
    NextAction,
    ObserveResult,
    VerifyResult,
    ActionExecutionResult,
    VlmLoopResult,
)
from .prompts import build_observe_prompt, build_verify_prompt
from .screenshot import capture_screenshot, ScreenshotError, Screenshot

__all__ = [
    "QwenVlmClient",
    "VlmClientError",
    "VlmInvalidOutput",
    "BBox",
    "NextAction",
    "ObserveResult",
    "VerifyResult",
    "ActionExecutionResult",
    "VlmLoopResult",
    "build_observe_prompt",
    "build_verify_prompt",
    "capture_screenshot",
    "ScreenshotError",
    "Screenshot",
]
