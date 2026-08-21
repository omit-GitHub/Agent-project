# -*- coding: utf-8 -*-
"""Action Loop — Harness 层的受限恢复闭环。

run_action_loop(decision_source, executor, verifier, ...) 通过 Protocol 与
VLM / ADB / 具体 App 完全解耦：
  - decision_source 只是"给下一个动作"的协议，VLM 是实现之一
  - executor 只是"执行动作并返回新状态"的协议
  - verifier 只是"判断执行是否达成目标"的协议

关键约束：
  - ask_user → needs_user_confirmation（不进 executor）
  - done 无 prior success → stopped_unverified
  - ok=True 唯一出口：Verifier 返回 success
  - Guard decision=ask_user / reject → 不进 executor
  - verifier failed / unknown → 有限恢复（recovery_budget）
  - reveal_controls → 集成 ControlRevealer
  - 总动作预算 max_steps=8、总决策调用预算 max_decision_calls=4
  - 每步写结构化 trace

本模块无任何外部依赖（不依赖 VLM / ADB / 具体 App）。
"""
from typing import Optional, Protocol, runtime_checkable

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


# ─────────────── 主循环 ───────────────

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
    max_decision_calls: int = 4,
    recovery_budget: int = 2,
    control_revealer=None,
) -> ActionLoopResult:
    """Harness 受限恢复闭环。

    约束：
      - guard 全程复用
      - failed_candidate_keys 从 guard.failed_candidates 取
      - ask_user → needs_user_confirmation
      - done 无 prior success → stopped_unverified
      - ok=True 唯一出口：Verifier success
      - Guard decision=ask_user/reject → 不进 executor
      - verifier failed/unknown → 有限恢复
      - reveal_controls → 集成 ControlRevealer
    """
    config = config or ActionGuardConfig()
    guard = guard or ActionGuard()
    current_state = initial_state
    steps: list = []
    trace: list = []
    last_verification: Optional[VerificationResult] = None
    recovery_count = 0
    decision_calls = 0
    action_count = 0

    for step_idx in range(max_steps):
        # ── 决策预算检查 ──
        if decision_calls >= max_decision_calls:
            return ActionLoopResult(
                ok=False, status="decision_budget_exhausted",
                steps=steps, trace=trace,
                final_message=f"max_decision_calls={max_decision_calls} reached",
                verification=last_verification,
                recovery_count=recovery_count,
                decision_calls=decision_calls,
                action_count=action_count,
            )

        action = decision_source.next_action(current_state)
        decision_calls += 1
        before_state = current_state

        # 初始化 trace entry
        trace_entry = {
            "step": step_idx,
            "action_type": action.action_type,
            "target": action.candidate_id or action.target_role or "",
            "guard_reason": "",
            "guard_allowed": True,
            "guard_decision": "allow",
            "executor_ok": None,
            "verification": None,
            "verification_source": None,
            "recovery_count": recovery_count,
            "strategy_id": None,
        }

        # ── ask_user：不进 executor ──
        if action.action_type == "ask_user":
            trace_entry["guard_reason"] = "lifecycle: ask_user"
            trace.append(trace_entry)
            return ActionLoopResult(
                ok=False, status="needs_user_confirmation",
                steps=steps, trace=trace,
                final_message="action asks for user input",
                verification=last_verification,
                recovery_count=recovery_count,
                decision_calls=decision_calls,
                action_count=action_count,
            )

        # ── done：不自动 ok ──
        if action.action_type == "done":
            trace_entry["guard_reason"] = "lifecycle: done"
            trace.append(trace_entry)
            if (last_verification is not None
                    and last_verification.verification == VerificationStatus.success):
                return ActionLoopResult(
                    ok=True, status="success", steps=steps, trace=trace,
                    final_message=last_verification.reason,
                    verification=last_verification,
                    recovery_count=recovery_count,
                    decision_calls=decision_calls,
                    action_count=action_count,
                )
            return ActionLoopResult(
                ok=False, status="stopped_unverified", steps=steps, trace=trace,
                final_message="done without prior verified success",
                verification=last_verification,
                recovery_count=recovery_count,
                decision_calls=decision_calls,
                action_count=action_count,
            )

        # ── reveal_controls：集成 ControlRevealer ──
        if action.action_type == "reveal_controls":
            if control_revealer is not None:
                try:
                    success, candidate_map, strategy_id = control_revealer.reveal(
                        app=current_state.package,
                        executor=executor,
                        verifier=verifier,
                        current_state=current_state,
                        activity=current_state.activity,
                    )
                    trace_entry["strategy_id"] = strategy_id
                    if success:
                        # 更新 current_state 带新 candidate_map
                        current_state = UiState(
                            fingerprint=current_state.fingerprint,
                            package=current_state.package,
                            activity=current_state.activity,
                            screen_size=current_state.screen_size,
                            candidate_map=candidate_map,
                            control_bar_visible=True,
                            ocr_tokens=set(current_state.ocr_tokens),
                            selected_role=current_state.selected_role,
                        )
                        trace_entry["guard_reason"] = "reveal succeeded"
                        trace_entry["executor_ok"] = True
                        trace.append(trace_entry)
                        steps.append({
                            "step": step_idx,
                            "action": "reveal_controls",
                            "target": strategy_id,
                            "ok": True,
                            "detail": f"reveal via {strategy_id}",
                        })
                        # reveal 成功不直接返回 success，让决策源决定下一步
                        continue
                    else:
                        trace_entry["guard_reason"] = "reveal failed"
                        trace_entry["executor_ok"] = False
                        trace.append(trace_entry)
                        if recovery_count < recovery_budget:
                            recovery_count += 1
                            continue
                        return ActionLoopResult(
                            ok=False, status="reveal_failed",
                            steps=steps, trace=trace,
                            final_message=f"reveal failed via {strategy_id}",
                            verification=last_verification,
                            recovery_count=recovery_count,
                            decision_calls=decision_calls,
                            action_count=action_count,
                        )
                except Exception as e:
                    trace_entry["guard_reason"] = f"reveal error: {e}"
                    trace_entry["executor_ok"] = False
                    trace.append(trace_entry)
                    if recovery_count < recovery_budget:
                        recovery_count += 1
                        continue
                    return ActionLoopResult(
                        ok=False, status="reveal_failed",
                        steps=steps, trace=trace,
                        final_message=f"reveal error: {e}",
                        verification=last_verification,
                        recovery_count=recovery_count,
                        decision_calls=decision_calls,
                        action_count=action_count,
                    )
            else:
                # 没有 control_revealer → 当作 safe op 跳过
                trace_entry["guard_reason"] = "no control_revealer, skipped"
                trace.append(trace_entry)
                continue

        # ── Guard 校验 ──
        decision = validate_action(
            action, current_state, subgoal,
            guard.failed_candidates,
            guard=guard, config=config,
        )
        trace_entry["guard_reason"] = decision.reason
        trace_entry["guard_allowed"] = decision.allowed
        trace_entry["guard_decision"] = decision.decision

        if not decision.allowed:
            trace.append(trace_entry)
            # 敏感操作 → ask_user 或 reject（绝不进 executor）
            if decision.decision in ("ask_user", "reject"):
                status = f"guard_{decision.decision}"
                return ActionLoopResult(
                    ok=False, status=status,
                    steps=steps, trace=trace,
                    final_message=f"blocked: {decision.reason}",
                    verification=last_verification,
                    recovery_count=recovery_count,
                    decision_calls=decision_calls,
                    action_count=action_count,
                )
            # 其他拒绝 → 尝试恢复
            if recovery_count < recovery_budget:
                recovery_count += 1
                continue
            return ActionLoopResult(
                ok=False, status="blocked",
                steps=steps, trace=trace,
                final_message=f"blocked: {decision.reason}",
                verification=last_verification,
                recovery_count=recovery_count,
                decision_calls=decision_calls,
                action_count=action_count,
            )

        # ── 执行 ──
        result = executor.execute(action, current_state)
        action_count += 1
        trace_entry["executor_ok"] = result.ok

        steps.append({
            "step": step_idx,
            "action": action.action_type,
            "target": action.candidate_id or action.target_role,
            "ok": result.ok,
            "detail": result.detail,
        })

        # ── executor 失败 → 记录并尝试恢复 ──
        if not result.ok:
            if action.candidate_id:
                guard.record_failure(current_state.fingerprint, action.candidate_id)
            trace.append(trace_entry)
            if recovery_count < recovery_budget:
                recovery_count += 1
                continue
            return ActionLoopResult(
                ok=False, status="failed",
                steps=steps, trace=trace,
                final_message=result.error_code or "execution failed",
                verification=last_verification,
                recovery_count=recovery_count,
                decision_calls=decision_calls,
                action_count=action_count,
            )

        after_state = result.after_state

        # ── 验证 ──
        verification = verifier.verify(before_state, after_state, action)
        last_verification = verification
        trace_entry["verification"] = verification.verification.value
        trace_entry["verification_source"] = verification.source.value
        steps[-1]["verify"] = verification.verification.value

        # ── verifier success → 唯一 ok=True 出口 ──
        if verification.verification == VerificationStatus.success:
            trace.append(trace_entry)
            return ActionLoopResult(
                ok=True, status="success", steps=steps, trace=trace,
                final_message=verification.reason,
                verification=verification,
                recovery_count=recovery_count,
                decision_calls=decision_calls,
                action_count=action_count,
            )

        # ── verifier failed → 记录并尝试恢复 ──
        if verification.verification == VerificationStatus.failed:
            if action.candidate_id:
                guard.record_failure(current_state.fingerprint, action.candidate_id)
            trace.append(trace_entry)
            if recovery_count < recovery_budget:
                recovery_count += 1
                current_state = after_state
                continue
            return ActionLoopResult(
                ok=False, status="failed",
                steps=steps, trace=trace,
                final_message=verification.reason,
                verification=verification,
                recovery_count=recovery_count,
                decision_calls=decision_calls,
                action_count=action_count,
            )

        # ── verifier unknown → 有限重观察后停止 ──
        if verification.verification == VerificationStatus.unknown:
            trace.append(trace_entry)
            if recovery_count < recovery_budget:
                recovery_count += 1
                current_state = after_state
                continue
            return ActionLoopResult(
                ok=False, status="unknown_exhausted",
                steps=steps, trace=trace,
                final_message=verification.reason,
                verification=verification,
                recovery_count=recovery_count,
                decision_calls=decision_calls,
                action_count=action_count,
            )

        # ── not_yet → 状态推进继续 ──
        trace.append(trace_entry)
        current_state = after_state

    return ActionLoopResult(
        ok=False, status="timeout", steps=steps, trace=trace,
        final_message=f"max_steps={max_steps} reached",
        verification=last_verification,
        recovery_count=recovery_count,
        decision_calls=decision_calls,
        action_count=action_count,
    )
