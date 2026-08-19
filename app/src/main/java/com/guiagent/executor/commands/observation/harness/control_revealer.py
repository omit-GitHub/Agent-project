# -*- coding: utf-8 -*-
"""Control Revealer — VLM 感知的控件唤出器。

对应 Cursor 任务书 §7。
通过 per-App 策略序列尝试唤出播放器控制条，每步后用 VLM 验证。
"""
import time
from typing import Optional

from ..vlm.schemas import NextAction, ActionExecutionResult
from ..vlm.screenshot import capture_screenshot

# 用绝对导入代替相对导入
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from common.utils import tap, remote_key, success_with_data, error  # noqa: E402


# 通用唤出策略（按顺序尝试）
GENERIC_REVEAL_STEPS = [
    {"type": "tap", "x": 0.50, "y": 0.50, "wait_ms": 700},
    {"type": "remote_key", "key": "DPAD_CENTER", "wait_ms": 700},
    {"type": "remote_key", "key": "MENU", "wait_ms": 900},
]


def reveal_controls(
    app_package: Optional[str] = None,
    max_steps: int = 3,
    subgoal: str = "",
) -> ActionExecutionResult:
    """唤出播放器控制条。

    Args:
        app_package: App 包名（用于选择策略，暂未实现 per-App）
        max_steps: 最大尝试步数
        subgoal: 用户子目标（用于日志）

    Returns:
        ActionExecutionResult
    """
    from ..vlm.client import QwenVlmClient
    from ..vlm.schemas import VerifyResult

    # 初始化 VLM 客户端
    try:
        vlm = QwenVlmClient()
    except Exception as e:
        return ActionExecutionResult(
            ok=False,
            action=NextAction(type="reveal_controls"),
            error_code="VLM_INIT_FAILED",
            detail=str(e),
        )

    steps_tried = []
    for i, step in enumerate(GENERIC_REVEAL_STEPS[:max_steps]):
        step_type = step["type"]
        wait_ms = step.get("wait_ms", 500)

        # 执行动作
        if step_type == "tap":
            x = int(step["x"] * 1280)
            y = int(step["y"] * 800)
            result = tap(x, y)
        elif step_type == "remote_key":
            result = remote_key(step["key"])
        else:
            continue

        if not result.get("ok"):
            steps_tried.append({
                "step": i + 1,
                "action": step_type,
                "ok": False,
                "error": result.get("error", {}).get("msg", "unknown"),
            })
            continue

        # 等待动画
        time.sleep(wait_ms / 1000.0)

        # 截图验证
        try:
            shot = capture_screenshot(output_dir="./runtime/screenshots")
            verify = vlm.verify(
                screenshot_path=shot.path,
                subgoal="唤出播放器控制条",
                action={"type": step_type, "key": step.get("key", "")},
                expected="控制条可见（有播放/暂停、倍速、清晰度等按钮）",
            )
            control_visible = verify.verification == "success"
        except Exception as e:
            control_visible = False
            verify = None

        steps_tried.append({
            "step": i + 1,
            "action": step_type,
            "ok": True,
            "control_bar_visible": control_visible,
            "verify": verify.verification if verify else "unknown",
        })

        if control_visible:
            return ActionExecutionResult(
                ok=True,
                action=NextAction(type="reveal_controls"),
                detail=f"Control bar revealed after {i+1} steps",
            )

    # 全部失败
    return ActionExecutionResult(
        ok=False,
        action=NextAction(type="reveal_controls"),
        error_code="CONTROL_BAR_NOT_REVEALED",
        detail=f"Failed after {len(steps_tried)} steps",
    )


def run(params: dict | None = None) -> dict:
    """命令入口（供 registry 调用）。"""
    params = params or {}
    result = reveal_controls(
        app_package=params.get("app"),
        max_steps=int(params.get("max_steps", 3)),
        subgoal=params.get("subgoal", ""),
    )
    if result.ok:
        return success_with_data("reveal_controls", {
            "result": result.detail,
        })
    else:
        return error(result.error_code or "REVEAL_FAILED", result.detail or "Unknown error")
