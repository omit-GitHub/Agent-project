# -*- coding: utf-8 -*-
"""Action Loop — Harness 层的受限恢复闭环。

三类预算严格分离：
  - decision_calls：仅 DecisionSource.next_action() 次数
  - atomic_action_count：所有 executor.execute() 次数（含 recovery/reveal/wait）
  - recovery_count：进入 RecoveryPlan 次数

恢复序列由 RecoveryPlanner 生成，不调用 DecisionSource。
恢复结束后才再次决策。

ControlRevealer 只输出 RevealPlan。action_loop 逐条执行 plan.actions，
每条走完整 guard → executor.execute → verifier.verify 路径。

关键约束：
  - ask_user → needs_user_confirmation（不进 executor）
  - done 无 prior success → stopped_unverified
  - ok=True 唯一出口：Verifier 返回 success
  - Guard risk_level=high + not allowed → guard_reject（绝不进 executor）
  - Guard risk_level=medium + not allowed → needs_user_confirmation
  - Guard requires_refinement=True → needs_refinement → 受限恢复
  - requires_refinement 时禁止 executor 调用
  - selected_role 必须本次状态转移才可 success
  - 多 OCR token 采用"全集出现"语义
  - reveal 成功后使用完整 after_state

本模块无任何外部依赖（不依赖 VLM / ADB / 具体 App）。
"""
import time
from typing import Optional, Protocol, runtime_checkable

from .action_guard import ActionGuard, ActionGuardConfig, validate_action
from .control_revealer import ControlRevealer
from .schemas import (
    ActionLoopResult, ActionResult, ActionSpec, RevealPlan, UiState,
)
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


@runtime_checkable
class RecoveryPlanner(Protocol):
    """恢复规划器。生成恢复动作序列，不调用 DecisionSource。"""
    def plan(
        self,
        failed_action: ActionSpec,
        current_state: UiState,
        failure_reason: str,
        recovery_attempt: int,
    ) -> list: ...


# ─────────────── 默认 RecoveryPlanner ───────────────

class DefaultRecoveryPlanner:
    """默认恢复规划器。返回一个 back 动作作为恢复。"""

    def plan(self, failed_action, current_state, failure_reason, recovery_attempt):
        return [ActionSpec(action_type="back")]


# ─────────────── Reveal 成功验证 ───────────────

def _verify_reveal_success(
    before_state: UiState,
    after_state: UiState,
    target_role: Optional[str] = None,
    expected_ocr_tokens: Optional[set] = None,
) -> tuple:
    """验证单步 reveal 是否成功。

    成功条件（任一满足即可）：
      1. control_bar_visible: false → true
      2. selected_role 状态转移：before ≠ target → after == target
      3. 多 OCR token 全集出现：expected_ocr_tokens ⊆ (after.ocr_tokens - before.ocr_tokens)

    Returns: (success: bool, reason: str)
    """
    # 1. control_bar_visible: false → true
    if not before_state.control_bar_visible and after_state.control_bar_visible:
        return True, "control_bar became visible"

    # 2. selected_role 状态转移
    if target_role and before_state.selected_role != target_role and after_state.selected_role == target_role:
        return True, f"selected_role transition to '{target_role}'"

    # 3. 多 OCR token 全集出现
    if expected_ocr_tokens:
        new_tokens = after_state.ocr_tokens - before_state.ocr_tokens
        if expected_ocr_tokens.issubset(new_tokens):
            return True, f"all expected OCR tokens appeared: {sorted(expected_ocr_tokens)}"

    return False, "no reveal success signal"


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
    control_revealer: Optional[ControlRevealer] = None,
    recovery_planner: Optional[RecoveryPlanner] = None,
    target_role: Optional[str] = None,
    expected_ocr_tokens: Optional[set] = None,
) -> ActionLoopResult:
    """Harness 受限恢复闭环。

    三类预算严格分离：
      - decision_calls：DecisionSource.next_action() 次数
      - atomic_action_count：所有 executor.execute() 次数
      - recovery_count：进入 RecoveryPlan 次数
    """
    config = config or ActionGuardConfig()
    guard = guard or ActionGuard()
    recovery_planner = recovery_planner or DefaultRecoveryPlanner()
    current_state = initial_state
    steps: list = []
    trace: list = []
    last_verification: Optional[VerificationResult] = None
    recovery_count = 0
    decision_calls = 0
    atomic_action_count = 0

    def _make_trace(step_idx, action, strategy_id=None):
        return {
            "step": step_idx,
            "action_type": action.action_type,
            "target": action.candidate_id or action.target_role or "",
            "guard_reason": "",
            "guard_allowed": True,
            "guard_risk_level": "low",
            "guard_requires_refinement": False,
            "executor_ok": None,
            "verification": None,
            "verification_source": None,
            "recovery_count": recovery_count,
            "strategy_id": strategy_id,
        }

    def _return(ok, status, msg, verification=None):
        return ActionLoopResult(
            ok=ok, status=status, steps=steps, trace=trace,
            final_message=msg, verification=verification or last_verification,
            recovery_count=recovery_count,
            decision_calls=decision_calls,
            atomic_action_count=atomic_action_count,
            final_state=current_state,
        )

    # ── 主决策循环 ──
    while True:
        # 决策预算检查
        if decision_calls >= max_decision_calls:
            return _return(False, "decision_budget_exhausted",
                           f"max_decision_calls={max_decision_calls} reached")

        action = decision_source.next_action(current_state)
        decision_calls += 1
        before_state = current_state
        step_idx = len(steps)
        strategy_id = None

        # ── ask_user ──
        if action.action_type == "ask_user":
            te = _make_trace(step_idx, action)
            te["guard_reason"] = "lifecycle: ask_user"
            trace.append(te)
            return _return(False, "needs_user_confirmation",
                           "action asks for user input")

        # ── done ──
        if action.action_type == "done":
            te = _make_trace(step_idx, action)
            te["guard_reason"] = "lifecycle: done"
            trace.append(te)
            if (last_verification is not None
                    and last_verification.verification == VerificationStatus.success):
                return _return(True, "success", last_verification.reason, last_verification)
            return _return(False, "stopped_unverified",
                           "done without prior verified success")

        # ── reveal_controls ──
        if action.action_type == "reveal_controls":
            if control_revealer is not None:
                plan = control_revealer.plan(
                    app=current_state.package,
                    current_state=current_state,
                    activity=current_state.activity,
                )
                strategy_id = plan.strategy_id

                # 逐条执行 plan.actions
                reveal_success = False
                for plan_action in plan.actions:
                    # 动作预算检查
                    if atomic_action_count >= max_steps:
                        return _return(False, "action_budget_exhausted",
                                       f"max_steps={max_steps} reached during reveal")

                    # Guard 校验
                    g = validate_action(
                        plan_action, current_state, subgoal,
                        guard.failed_candidates, guard=guard, config=config,
                    )

                    # 创建 trace 条目（无论是否通过 Guard）
                    te = _make_trace(step_idx, plan_action, strategy_id)
                    te["guard_reason"] = g.reason
                    te["guard_allowed"] = g.allowed
                    te["guard_risk_level"] = g.risk_level
                    te["guard_requires_refinement"] = g.requires_refinement

                    if not g.allowed or g.requires_refinement:
                        # Guard 拒绝：记录 trace 但不执行
                        te["executor_ok"] = None
                        te["verification"] = None
                        trace.append(te)
                        continue  # 跳过不合格动作

                    # 执行
                    r_before = current_state
                    start_time = time.time()
                    result = executor.execute(plan_action, current_state)
                    atomic_action_count += 1

                    if not result.ok:
                        te["executor_ok"] = result.ok
                        trace.append(te)
                        continue

                    after = result.after_state

                    # 验证 reveal 成功
                    success, reason = _verify_reveal_success(
                        r_before, after,
                        target_role=target_role,
                        expected_ocr_tokens=expected_ocr_tokens,
                    )
                    latency_ms = (time.time() - start_time) * 1000

                    te["executor_ok"] = result.ok
                    steps.append({
                        "step": len(steps),
                        "action": plan_action.action_type,
                        "target": plan_action.candidate_id or plan_action.target_role,
                        "ok": result.ok,
                        "detail": result.detail,
                    })

                    if success:
                        control_revealer.record_success(strategy_id, latency_ms)
                        # 使用完整 after_state
                        current_state = after
                        reveal_success = True
                        trace.append(te)
                        break

                    # 普通 verifier 也检查一下
                    v = verifier.verify(r_before, after, plan_action)
                    te["verification"] = v.verification.value
                    te["verification_source"] = v.source.value
                    trace.append(te)

                    if v.verification == VerificationStatus.success:
                        control_revealer.record_success(strategy_id, latency_ms)
                        current_state = after
                        reveal_success = True
                        break

                    # 更新状态继续
                    current_state = after

                if reveal_success:
                    continue  # reveal 成功，回到决策循环

                # reveal 全部动作执行完毕但未成功
                control_revealer.record_semantic_failure(strategy_id)

                # 尝试恢复
                if recovery_count < recovery_budget:
                    recovery_count += 1
                    recovery_actions = recovery_planner.plan(
                        action, current_state, "reveal_failed", recovery_count,
                    )
                    for ra in recovery_actions:
                        if atomic_action_count >= max_steps:
                            return _return(False, "action_budget_exhausted",
                                           "max_steps reached during recovery")
                        rg = validate_action(
                            ra, current_state, subgoal,
                            guard.failed_candidates, guard=guard, config=config,
                        )
                        if not rg.allowed:
                            continue
                        rr = executor.execute(ra, current_state)
                        atomic_action_count += 1
                        if rr.ok:
                            current_state = rr.after_state
                    continue

                return _return(False, "reveal_failed",
                               f"reveal failed via {strategy_id}")
            else:
                te = _make_trace(step_idx, action)
                te["guard_reason"] = "no control_revealer, skipped"
                trace.append(te)
                continue

        # ── Guard 校验 ──
        decision = validate_action(
            action, current_state, subgoal,
            guard.failed_candidates, guard=guard, config=config,
        )

        te = _make_trace(step_idx, action)
        te["guard_reason"] = decision.reason
        te["guard_allowed"] = decision.allowed
        te["guard_risk_level"] = decision.risk_level
        te["guard_requires_refinement"] = decision.requires_refinement

        if not decision.allowed:
            trace.append(te)

            # requires_refinement → 受限恢复
            if decision.requires_refinement:
                if recovery_count < recovery_budget:
                    recovery_count += 1
                    recovery_actions = recovery_planner.plan(
                        action, current_state, "needs_refinement", recovery_count,
                    )
                    for ra in recovery_actions:
                        if atomic_action_count >= max_steps:
                            return _return(False, "action_budget_exhausted",
                                           "max_steps reached during recovery")
                        rg = validate_action(
                            ra, current_state, subgoal,
                            guard.failed_candidates, guard=guard, config=config,
                        )
                        if not rg.allowed:
                            continue
                        rr = executor.execute(ra, current_state)
                        atomic_action_count += 1
                        if rr.ok:
                            current_state = rr.after_state
                    continue
                return _return(False, "needs_refinement",
                               f"refinement needed: {decision.reason}")

            # risk_level=high → guard_reject
            if decision.risk_level == "high":
                return _return(False, "guard_reject",
                               f"blocked (high risk): {decision.reason}")

            # risk_level=medium → needs_user_confirmation
            if decision.risk_level == "medium":
                return _return(False, "needs_user_confirmation",
                               f"blocked (medium risk): {decision.reason}")

            # 其他 → 受限恢复
            if recovery_count < recovery_budget:
                recovery_count += 1
                recovery_actions = recovery_planner.plan(
                    action, current_state, decision.error_code or "blocked", recovery_count,
                )
                for ra in recovery_actions:
                    if atomic_action_count >= max_steps:
                        return _return(False, "action_budget_exhausted",
                                       "max_steps reached during recovery")
                    rg = validate_action(
                        ra, current_state, subgoal,
                        guard.failed_candidates, guard=guard, config=config,
                    )
                    if not rg.allowed:
                        continue
                    rr = executor.execute(ra, current_state)
                    atomic_action_count += 1
                    if rr.ok:
                        current_state = rr.after_state
                continue
            return _return(False, "blocked", f"blocked: {decision.reason}")

        # ── 执行 ──
        if atomic_action_count >= max_steps:
            return _return(False, "action_budget_exhausted",
                           f"max_steps={max_steps} reached")

        result = executor.execute(action, current_state)
        atomic_action_count += 1
        te["executor_ok"] = result.ok

        steps.append({
            "step": len(steps),
            "action": action.action_type,
            "target": action.candidate_id or action.target_role,
            "ok": result.ok,
            "detail": result.detail,
        })

        if not result.ok:
            if action.candidate_id:
                guard.record_failure(current_state.fingerprint, action.candidate_id)
            trace.append(te)
            # 尝试恢复
            if recovery_count < recovery_budget:
                recovery_count += 1
                recovery_actions = recovery_planner.plan(
                    action, current_state, result.error_code or "execution_failed", recovery_count,
                )
                for ra in recovery_actions:
                    if atomic_action_count >= max_steps:
                        return _return(False, "action_budget_exhausted",
                                       "max_steps reached during recovery")
                    rg = validate_action(
                        ra, current_state, subgoal,
                        guard.failed_candidates, guard=guard, config=config,
                    )
                    if not rg.allowed:
                        continue
                    rr = executor.execute(ra, current_state)
                    atomic_action_count += 1
                    if rr.ok:
                        current_state = rr.after_state
                continue
            return _return(False, "failed", result.error_code or "execution failed")

        after_state = result.after_state

        # ── 验证 ──
        verification = verifier.verify(before_state, after_state, action)
        last_verification = verification
        te["verification"] = verification.verification.value
        te["verification_source"] = verification.source.value
        steps[-1]["verify"] = verification.verification.value

        # ── success → 唯一 ok=True 出口 ──
        if verification.verification == VerificationStatus.success:
            trace.append(te)
            return _return(True, "success", verification.reason, verification)

        # ── failed → 记录并尝试恢复 ──
        if verification.verification == VerificationStatus.failed:
            if action.candidate_id:
                guard.record_failure(current_state.fingerprint, action.candidate_id)
            trace.append(te)
            if recovery_count < recovery_budget:
                recovery_count += 1
                current_state = after_state
                recovery_actions = recovery_planner.plan(
                    action, current_state, "verification_failed", recovery_count,
                )
                for ra in recovery_actions:
                    if atomic_action_count >= max_steps:
                        return _return(False, "action_budget_exhausted",
                                       "max_steps reached during recovery")
                    rg = validate_action(
                        ra, current_state, subgoal,
                        guard.failed_candidates, guard=guard, config=config,
                    )
                    if not rg.allowed:
                        continue
                    rr = executor.execute(ra, current_state)
                    atomic_action_count += 1
                    if rr.ok:
                        current_state = rr.after_state
                continue
            return _return(False, "failed", verification.reason)

        # ── unknown → 有限重观察 ──
        if verification.verification == VerificationStatus.unknown:
            trace.append(te)
            if recovery_count < recovery_budget:
                recovery_count += 1
                current_state = after_state
                continue
            return _return(False, "unknown_exhausted", verification.reason)

        # ── not_yet → 继续 ──
        trace.append(te)
        current_state = after_state
