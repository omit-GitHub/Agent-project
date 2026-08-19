# -*- coding: utf-8 -*-
"""Action Loop — VLM 主导的单步闭环。

对应 Cursor 任务书 §8。
实现 run_vlm_loop(): 截图 → VLM 观察 → Guard 校验 → 执行 → VLM 验证 → 循环。
"""
import json
import os
import time
import traceback
from typing import Any, Optional

from ..vlm.client import QwenVlmClient, VlmClientError, VlmInvalidOutput
from ..vlm.schemas import (
    ObserveResult,
    VerifyResult,
    ActionExecutionResult,
    VlmLoopResult,
    NextAction,
)
from ..vlm.screenshot import capture_screenshot, ScreenshotError
from .action_guard import validate_action, tap_to_pixel, ActionGuardConfig
from .control_revealer import reveal_controls

# 从现有 common/utils 导入执行函数
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.utils import tap, swipe, remote_key, global_action, set_text_by_id, find_nodes  # noqa: E402


def execute_action(
    action: NextAction,
    screen_width: int,
    screen_height: int,
) -> ActionExecutionResult:
    """执行 VLM 建议的动作。

    将 NextAction 映射到具体的 Android 操作。
    """
    try:
        if action.type == "tap":
            if not action.bbox_normalized:
                return ActionExecutionResult(ok=False, action=action, error_code="NO_BBOX")
            x, y = tap_to_pixel(action.bbox_normalized, screen_width, screen_height)
            result = tap(x, y)
            return ActionExecutionResult(
                ok=result.get("ok", False),
                action=action,
                detail=f"tapped ({x}, {y})",
            )

        elif action.type == "swipe":
            if not action.direction:
                return ActionExecutionResult(ok=False, action=action, error_code="NO_DIRECTION")
            cx, cy = screen_width // 2, screen_height // 2
            dist = int((action.distance or 0.3) * min(screen_width, screen_height))
            direction_map = {
                "up": (cx, cy + dist, cx, cy - dist),
                "down": (cx, cy - dist, cx, cy + dist),
                "left": (cx + dist, cy, cx - dist, cy),
                "right": (cx - dist, cy, cx + dist, cy),
            }
            x1, y1, x2, y2 = direction_map[action.direction]
            result = swipe(x1, y1, x2, y2)
            return ActionExecutionResult(
                ok=result.get("ok", False),
                action=action,
                detail=f"swiped {action.direction}",
            )

        elif action.type in ("remote_key", "media_key"):
            if not action.key:
                return ActionExecutionResult(ok=False, action=action, error_code="NO_KEY")
            result = remote_key(action.key)
            return ActionExecutionResult(
                ok=result.get("ok", False),
                action=action,
                detail=f"remote_key {action.key}",
            )

        elif action.type == "back":
            result = global_action("BACK")
            return ActionExecutionResult(
                ok=result.get("ok", False),
                action=action,
                detail="back",
            )

        elif action.type == "wait":
            wait_ms = action.wait_ms or 500
            time.sleep(wait_ms / 1000.0)
            return ActionExecutionResult(ok=True, action=action, detail=f"waited {wait_ms}ms")

        elif action.type == "reveal_controls":
            # 调用 Control Revealer
            result = reveal_controls()
            return ActionExecutionResult(
                ok=result.ok,
                action=action,
                detail=result.detail or "",
                error_code=result.error_code,
            )

        elif action.type in ("done", "ask_user"):
            return ActionExecutionResult(ok=True, action=action, detail=action.type)

        else:
            return ActionExecutionResult(
                ok=False,
                action=action,
                error_code="UNSUPPORTED_ACTION",
                detail=f"Unknown action type: {action.type}",
            )

    except Exception as e:
        traceback.print_exc()
        return ActionExecutionResult(
            ok=False,
            action=action,
            error_code="EXECUTION_FAILED",
            detail=str(e),
        )


def run_vlm_loop(
    *,
    subgoal: str,
    expected: str,
    initial_context: dict[str, Any] | None = None,
    max_steps: int = 6,
    max_observations: int = 3,
    screenshot_dir: str = "./runtime/screenshots",
    trace_dir: str = "./runtime/vlm_traces",
    config: ActionGuardConfig | None = None,
) -> VlmLoopResult:
    """执行 VLM 主导的动作循环。

    Args:
        subgoal: 用户子目标（如"点击 1.5 倍速"）
        expected: 可观察的成功条件（如"倍速面板中 1.5x 处于选中状态"）
        initial_context: 初始上下文（如 app_hint）
        max_steps: 最大动作步数
        max_observations: 最大 VLM 观察次数
        screenshot_dir: 截图保存目录
        trace_dir: trace 保存目录
        config: Action Guard 配置

    Returns:
        VlmLoopResult
    """
    config = config or ActionGuardConfig()
    os.makedirs(screenshot_dir, exist_ok=True)
    os.makedirs(trace_dir, exist_ok=True)

    # 初始化 VLM 客户端
    try:
        vlm = QwenVlmClient()
    except VlmClientError as e:
        return VlmLoopResult(
            ok=False,
            status="failed",
            final_message=f"VLM init failed: {e}",
        )

    trajectory = []
    steps = []
    observations = 0

    for step_idx in range(max_steps):
        # 1. 截图
        try:
            before = capture_screenshot(output_dir=screenshot_dir, request_id=f"step{step_idx}")
        except ScreenshotError as e:
            return VlmLoopResult(
                ok=False,
                status="failed",
                steps=steps,
                final_message=f"Screenshot failed: {e}",
            )

        # 2. VLM 观察
        observations += 1
        if observations > max_observations:
            return VlmLoopResult(
                ok=False,
                status="timeout",
                steps=steps,
                final_message=f"Too many observations ({observations} > {max_observations})",
            )

        try:
            observe = vlm.observe(
                screenshot_path=before.path,
                subgoal=subgoal,
                trajectory=trajectory,
            )
        except VlmInvalidOutput as e:
            steps.append({"step": step_idx, "error": f"VLM invalid output: {e}"})
            continue
        except VlmClientError as e:
            steps.append({"step": step_idx, "error": f"VLM error: {e}"})
            break

        trajectory.append({"type": "observe", "result": observe.model_dump()})

        # 3. 检查 task_status
        if observe.task_status == "done" or observe.next_action.type == "done":
            # 仍需验证
            try:
                verify = vlm.verify(before.path, subgoal, observe.next_action, expected)
            except Exception:
                verify = VerifyResult(verification="unknown", reason="Verify failed")

            steps.append({"step": step_idx, "action": "done", "verify": verify.verification})
            return VlmLoopResult(
                ok=verify.verification == "success",
                status="success" if verify.verification == "success" else "failed",
                steps=steps,
                final_message=verify.reason,
                verification=verify,
            )

        if observe.next_action.type == "ask_user":
            return VlmLoopResult(
                ok=False,
                status="blocked",
                steps=steps,
                final_message=f"Needs user confirmation: {observe.target_evidence}",
            )

        if observe.next_action.type == "reveal_controls":
            # 调用 Control Revealer
            reveal_result = reveal_controls(subgoal=subgoal)
            steps.append({"step": step_idx, "action": "reveal_controls", "ok": reveal_result.ok})
            if not reveal_result.ok:
                return VlmLoopResult(
                    ok=False,
                    status="failed",
                    steps=steps,
                    final_message=reveal_result.detail or "Control bar not revealed",
                )
            trajectory.append({"type": "reveal_controls", "ok": reveal_result.ok})
            continue

        # 4. Action Guard 校验
        decision = validate_action(
            observe.next_action,
            before.width,
            before.height,
            subgoal,
            config,
        )
        if not decision.allowed:
            steps.append({"step": step_idx, "action": "blocked", "reason": decision.reason})
            return VlmLoopResult(
                ok=False,
                status="blocked",
                steps=steps,
                final_message=f"Action blocked: {decision.reason}",
            )

        # 5. 执行动作
        executed = execute_action(decision.action, before.width, before.height)
        steps.append({
            "step": step_idx,
            "action": decision.action.type,
            "target": decision.action.target_label,
            "ok": executed.ok,
            "detail": executed.detail,
        })
        trajectory.append({"type": "action", "result": executed.model_dump()})

        if not executed.ok:
            # 执行失败，尝试一次恢复
            if step_idx < max_steps - 1:
                continue
            else:
                return VlmLoopResult(
                    ok=False,
                    status="failed",
                    steps=steps,
                    final_message=f"Action failed: {executed.detail}",
                )

        # 6. 截图验证
        try:
            after = capture_screenshot(output_dir=screenshot_dir, request_id=f"step{step_idx}_after")
        except ScreenshotError:
            after = before

        try:
            verify = vlm.verify(after.path, subgoal, decision.action, expected)
        except Exception as e:
            verify = VerifyResult(verification="unknown", reason=f"Verify error: {e}")

        steps[-1]["verify"] = verify.verification
        trajectory.append({"type": "verify", "result": verify.model_dump()})

        if verify.verification == "success":
            return VlmLoopResult(
                ok=True,
                status="success",
                steps=steps,
                final_message=verify.reason,
                verification=verify,
            )

        if verify.verification == "failed":
            # 尝试一次恢复（重观察）
            if step_idx < max_steps - 1:
                continue
            else:
                return VlmLoopResult(
                    ok=False,
                    status="failed",
                    steps=steps,
                    final_message=verify.reason,
                    verification=verify,
                )

        # verification == "not_yet" or "unknown" → 继续循环

    # 超时
    return VlmLoopResult(
        ok=False,
        status="timeout",
        steps=steps,
        final_message=f"Max steps ({max_steps}) reached",
    )


def run(params: dict) -> dict:
    """命令入口（供 registry 调用）。

    params:
        goal: 用户目标的简短描述，必填
        expected: 可观察成功条件，必填
        app_hint: 可选 App 包名/名称
    """
    result = run_vlm_loop(
        subgoal=params["goal"],
        expected=params["expected"],
        initial_context={"app_hint": params.get("app_hint")},
    )
    return {
        "ok": result.ok,
        "data": {
            "command": "vlm_execute",
            "status": result.status,
            "final_message": result.final_message,
            "steps": len(result.steps),
            "verification": result.verification.model_dump() if result.verification else None,
        },
    }
