# -*- coding: utf-8 -*-
"""Action Loop — Harness 层的最小闭环。

新 API：run_action_loop(decision_source, executor, verifier, ...)
  - decision_source / executor / verifier 均为 Protocol，与 VLM / ADB / OCR 解耦
  - ask_user / done 由本函数直接处理（不进 executor）
  - ok=True 的唯一出口是 Verifier 返回 success
  - executor 失败 / verifier failed → 记录 candidate 失败并停止
  - verifier not_yet / unknown → current_state = after_state 继续
  - max_steps 耗尽 → timeout

旧 API：run_vlm_loop(...) / run(params) — deprecated，lazy 导入 VLM / ADB。
"""
import warnings
from dataclasses import dataclass
from typing import Any, Optional, Protocol, runtime_checkable

from .action_guard import ActionGuard, ActionGuardConfig, validate_action
from .schemas import ActionLoopResult, ActionResult, ActionSpec, UiState
from .verifier import VerificationResult, VerificationStatus


# ─────────────── Protocols ───────────────

@runtime_checkable
class DecisionSource(Protocol):
    """动作决策源。VLM 只是实现之一。"""

    def next_action(self, state: UiState) -> ActionSpec: ...


@runtime_checkable
class ActionExecutor(Protocol):
    """动作执行器。必须显式返回 after_state（禁止原地修改入参 state）。"""

    def execute(self, action: ActionSpec, state: UiState) -> ActionResult: ...


@runtime_checkable
class StateVerifier(Protocol):
    """状态验证器。"""

    def verify(self, before: UiState, after: UiState, action: ActionSpec) -> VerificationResult: ...


# ─────────────── 新主循环 ───────────────

def run_action_loop(
    decision_source: DecisionSource,
    executor: ActionExecutor,
    verifier: StateVerifier,
    *,
    initial_state: UiState,
    subgoal: str,
    guard: Optional[ActionGuard] = None,
    config: Optional[ActionGuardConfig] = None,
    max_steps: int = 8,
) -> ActionLoopResult:
    """Harness 最小闭环。

    约束：
      - guard 全程复用，不变成未使用变量
      - failed_candidate_keys 从 guard.failed_candidates 取，每次执行/验证失败后回写
      - ask_user → needs_user_confirmation
      - done 无 prior success → stopped_unverified
      - ok=True 唯一出口：Verifier success
    """
    config = config or ActionGuardConfig()
    guard = guard or ActionGuard()
    current_state = initial_state
    steps: list = []
    last_verification: Optional[VerificationResult] = None

    for step_idx in range(max_steps):
        action = decision_source.next_action(current_state)
        before_state = current_state

        # ── ask_user：不进 executor（约束 #12）──
        if action.action_type == "ask_user":
            return ActionLoopResult(
                ok=False, status="needs_user_confirmation",
                steps=steps, final_message="action asks for user input",
                verification=last_verification,
            )

        # ── done：不自动 ok（约束 #12）──
        if action.action_type == "done":
            if (last_verification is not None
                    and last_verification.verification == VerificationStatus.success):
                return ActionLoopResult(
                    ok=True, status="success", steps=steps,
                    final_message=last_verification.reason,
                    verification=last_verification,
                )
            return ActionLoopResult(
                ok=False, status="stopped_unverified", steps=steps,
                final_message="done without prior verified success",
                verification=last_verification,
            )

        # ── Guard 校验 ──
        decision = validate_action(
            action, current_state, subgoal,
            guard.failed_candidates,
            guard=guard, config=config,
        )
        if not decision.allowed:
            return ActionLoopResult(
                ok=False, status="blocked", steps=steps,
                final_message=f"blocked: {decision.reason}",
                verification=last_verification,
            )

        # ── 执行 ──
        result = executor.execute(action, current_state)
        steps.append({
            "step": step_idx,
            "action": action.action_type,
            "target": action.candidate_id or action.target_role,
            "ok": result.ok,
            "detail": result.detail,
        })

        # ── executor 失败 → 记录并停止（约束 #13）──
        if not result.ok:
            if action.candidate_id:
                guard.record_failure(current_state.fingerprint, action.candidate_id)
            return ActionLoopResult(
                ok=False, status="failed", steps=steps,
                final_message=result.error_code or "execution failed",
                verification=last_verification,
            )

        after_state = result.after_state

        # ── 验证 ──
        verification = verifier.verify(before_state, after_state, action)
        last_verification = verification
        steps[-1]["verify"] = verification.verification.value

        # ── verifier success → 唯一 ok=True 出口（约束 #13）──
        if verification.verification == VerificationStatus.success:
            return ActionLoopResult(
                ok=True, status="success", steps=steps,
                final_message=verification.reason,
                verification=verification,
            )

        # ── verifier failed → 记录并停止（约束 #13，本阶段不恢复）──
        if verification.verification == VerificationStatus.failed:
            if action.candidate_id:
                guard.record_failure(current_state.fingerprint, action.candidate_id)
            return ActionLoopResult(
                ok=False, status="failed", steps=steps,
                final_message=verification.reason,
                verification=verification,
            )

        # ── not_yet / unknown → 状态推进继续 ──
        current_state = after_state

    return ActionLoopResult(
        ok=False, status="timeout", steps=steps,
        final_message=f"max_steps={max_steps} reached",
        verification=last_verification,
    )


# ─────────────── 旧兼容入口（deprecated，lazy imports）───────────────

def run_vlm_loop(
    *,
    subgoal: str,
    expected: str,
    initial_context: Optional[dict] = None,
    max_steps: int = 6,
    max_observations: int = 3,
    screenshot_dir: str = "./runtime/screenshots",
    trace_dir: str = "./runtime/vlm_traces",
    config: Optional[ActionGuardConfig] = None,
) -> Any:
    """[deprecated] 旧 VLM 主循环。请改用 run_action_loop。

    保留签名供向后兼容；VLM / ADB / common.utils 改为 lazy 导入。
    """
    warnings.warn(
        "run_vlm_loop is deprecated; use run_action_loop",
        DeprecationWarning, stacklevel=2,
    )

    # Lazy imports（模块级不依赖 VLM / ADB）
    from ..vlm.client import QwenVlmClient, VlmClientError, VlmInvalidOutput
    from ..vlm.schemas import VerifyResult, VlmLoopResult
    from ..vlm.screenshot import capture_screenshot, ScreenshotError
    from .action_guard import GuardDecision
    from .control_revealer import ControlRevealer
    import os
    import time
    import traceback

    # 旧执行器：直接调用 common.utils
    sys_path_hack = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    import sys
    if sys_path_hack not in sys.path:
        sys.path.insert(0, sys_path_hack)
    from common.utils import tap, swipe, remote_key, global_action

    config = config or ActionGuardConfig()
    os.makedirs(screenshot_dir, exist_ok=True)
    os.makedirs(trace_dir, exist_ok=True)

    try:
        vlm = QwenVlmClient()
    except VlmClientError as e:
        from ..vlm.schemas import VlmLoopResult
        return VlmLoopResult(ok=False, status="failed", final_message=f"VLM init failed: {e}")

    from ..vlm.schemas import VlmLoopResult, VerifyResult, ActionExecutionResult, NextAction

    trajectory = []
    steps = []
    observations = 0

    for step_idx in range(max_steps):
        try:
            before = capture_screenshot(output_dir=screenshot_dir, request_id=f"step{step_idx}")
        except ScreenshotError as e:
            return VlmLoopResult(ok=False, status="failed", steps=steps,
                                  final_message=f"Screenshot failed: {e}")

        observations += 1
        if observations > max_observations:
            return VlmLoopResult(ok=False, status="timeout", steps=steps,
                                  final_message=f"Too many observations ({observations})")

        try:
            observe = vlm.observe(screenshot_path=before.path, subgoal=subgoal, trajectory=trajectory)
        except VlmInvalidOutput as e:
            steps.append({"step": step_idx, "error": f"VLM invalid output: {e}"})
            continue
        except VlmClientError as e:
            steps.append({"step": step_idx, "error": f"VLM error: {e}"})
            break

        trajectory.append({"type": "observe", "result": observe.model_dump()})

        if observe.task_status == "done" or observe.next_action.type == "done":
            try:
                verify = vlm.verify(before.path, subgoal, observe.next_action, expected)
            except Exception:
                verify = VerifyResult(verification="unknown", reason="Verify failed")
            steps.append({"step": step_idx, "action": "done", "verify": verify.verification})
            return VlmLoopResult(
                ok=verify.verification == "success",
                status="success" if verify.verification == "success" else "failed",
                steps=steps, final_message=verify.reason, verification=verify,
            )

        if observe.next_action.type == "ask_user":
            return VlmLoopResult(ok=False, status="blocked", steps=steps,
                                  final_message=f"Needs user confirmation: {observe.target_evidence}")

        if observe.next_action.type == "reveal_controls":
            revealer = ControlRevealer()
            ok, _ = revealer.reveal(app=(initial_context or {}).get("app_hint", "unknown"))
            steps.append({"step": step_idx, "action": "reveal_controls", "ok": ok})
            if not ok:
                return VlmLoopResult(ok=False, status="failed", steps=steps,
                                      final_message="Control bar not revealed")
            trajectory.append({"type": "reveal_controls", "ok": ok})
            continue

        # Action Guard (旧接口)
        from .action_guard import ActionGuard as _OldGuard
        old_guard = _OldGuard()
        decision = old_guard.validate(
            action_type=observe.next_action.type,
            candidate_id=observe.next_action.candidate_id,
            target_label=observe.next_action.target_label,
            bbox_px=observe.next_action.bbox_px,
            key=observe.next_action.key,
            text=observe.next_action.text,
            direction=observe.next_action.direction,
            distance=observe.next_action.distance,
            candidate_map=None,
            subgoal=subgoal,
            screen_width=before.width,
            screen_height=before.height,
        )
        if not decision.allowed:
            steps.append({"step": step_idx, "action": "blocked", "reason": decision.reason})
            return VlmLoopResult(ok=False, status="blocked", steps=steps,
                                  final_message=f"Action blocked: {decision.reason}")

        # 执行
        action = observe.next_action
        executed_ok = False
        detail = ""
        try:
            if action.type == "tap_candidate" or action.type == "tap_visual":
                if action.bbox_px:
                    cx = (action.bbox_px.x1 + action.bbox_px.x2) // 2
                    cy = (action.bbox_px.y1 + action.bbox_px.y2) // 2
                    r = tap(cx, cy)
                    executed_ok = r.get("ok", False)
                    detail = f"tapped ({cx}, {cy})"
            elif action.type == "swipe":
                cx, cy = before.width // 2, before.height // 2
                dist = int((action.distance or 0.3) * min(before.width, before.height))
                dm = {
                    "up": (cx, cy + dist, cx, cy - dist),
                    "down": (cx, cy - dist, cx, cy + dist),
                    "left": (cx + dist, cy, cx - dist, cy),
                    "right": (cx - dist, cy, cx + dist, cy),
                }
                x1, y1, x2, y2 = dm[action.direction]
                r = swipe(x1, y1, x2, y2)
                executed_ok = r.get("ok", False)
                detail = f"swiped {action.direction}"
            elif action.type in ("remote_key", "media_key"):
                r = remote_key(action.key)
                executed_ok = r.get("ok", False)
                detail = f"remote_key {action.key}"
            elif action.type == "back":
                r = global_action("BACK")
                executed_ok = r.get("ok", False)
                detail = "back"
            elif action.type == "wait":
                time.sleep((action.wait_ms or 500) / 1000.0)
                executed_ok = True
                detail = f"waited {action.wait_ms}ms"
            elif action.type in ("done", "ask_user"):
                executed_ok = True
                detail = action.type
        except Exception as e:
            traceback.print_exc()
            detail = str(e)

        steps.append({"step": step_idx, "action": action.type,
                      "target": action.target_label, "ok": executed_ok, "detail": detail})
        if not executed_ok:
            if step_idx < max_steps - 1:
                continue
            return VlmLoopResult(ok=False, status="failed", steps=steps,
                                  final_message=f"Action failed: {detail}")

        try:
            after = capture_screenshot(output_dir=screenshot_dir, request_id=f"step{step_idx}_after")
        except ScreenshotError:
            after = before

        try:
            verify = vlm.verify(after.path, subgoal, action, expected)
        except Exception as e:
            verify = VerifyResult(verification="unknown", reason=f"Verify error: {e}")

        steps[-1]["verify"] = verify.verification
        trajectory.append({"type": "verify", "result": verify.model_dump()})

        if verify.verification == "success":
            return VlmLoopResult(ok=True, status="success", steps=steps,
                                  final_message=verify.reason, verification=verify)
        if verify.verification == "failed":
            if step_idx < max_steps - 1:
                continue
            return VlmLoopResult(ok=False, status="failed", steps=steps,
                                  final_message=verify.reason, verification=verify)

    return VlmLoopResult(ok=False, status="timeout", steps=steps,
                          final_message=f"Max steps ({max_steps}) reached")


def run(params: dict) -> dict:
    """[deprecated] 旧命令入口。"""
    warnings.warn(
        "run() is deprecated; use run_action_loop",
        DeprecationWarning, stacklevel=2,
    )
    result = run_vlm_loop(
        subgoal=params["goal"],
        expected=params["expected"],
        initial_context={"app_hint": params.get("app_hint")},
    )
    from ..vlm.schemas import VlmLoopResult
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
