# -*- coding: utf-8 -*-
"""RevealPlan Trace 与反例测试 — 任务 3 强化。

验证：
  - 每个 reveal 原子动作（包括被 Guard 拒绝的）都在 trace 中有记录
  - trace 中包含 guard_allowed/guard_reason/executor_ok/verification
  - 非法 bbox 反例：Guard 拒绝，executor 不调用
  - 敏感动作反例：Guard 拒绝，executor 不调用
  - Guard 拒绝时 executor_calls == 0
"""
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
_SRC_ROOT = os.path.join(_PROJECT_ROOT, "src")
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)

from harness import (
    ActionSpec, ActionGuard, ActionGuardConfig,
    run_action_loop, BBox,
)
from harness.control_revealer import ControlRevealer
from harness.schemas import RevealPlan
from harness.verifier import VerificationResult
from tests.mocks import (
    MockDecisionSource, FakeExecutor, FakeVlmVerifier,
    make_candidate, make_candidate_map, make_state,
)


def _make_reveal_state(**kwargs):
    """构造用于 reveal 测试的 state。"""
    return make_state(
        fingerprint=kwargs.get("fingerprint", "fp1"),
        package=kwargs.get("package", "com.test"),
        activity=kwargs.get("activity", "Main"),
        screen_size=kwargs.get("screen_size", (1280, 800)),
        control_bar_visible=kwargs.get("control_bar_visible", False),
        ocr_tokens=kwargs.get("ocr_tokens", set()),
        selected_role=kwargs.get("selected_role", None),
    )


class TestRevealPlanTraceFields(unittest.TestCase):
    """验证 trace 中包含所有必需字段。"""

    def test_trace_contains_all_fields(self):
        """trace 条目包含 guard_allowed/guard_reason/executor_ok/verification。"""
        revealer = ControlRevealer()
        initial_state = _make_reveal_state(control_bar_visible=False)
        after_state = _make_reveal_state(control_bar_visible=True)
        executor = FakeExecutor(after_state=after_state)
        verifier = FakeVlmVerifier([])

        action = ActionSpec(action_type="reveal_controls")
        source = MockDecisionSource([action])

        result = run_action_loop(
            source, executor, verifier,
            initial_state=initial_state,
            subgoal="test",
            control_revealer=revealer,
            max_decision_calls=10,
            max_steps=10,
            recovery_budget=2,
        )

        # 验证：trace 不为空
        self.assertGreater(len(result.trace), 0, "trace should not be empty")

        # 验证：每个 trace 条目都包含必需字段
        for te in result.trace:
            self.assertIn("guard_allowed", te, "trace must contain guard_allowed")
            self.assertIn("guard_reason", te, "trace must contain guard_reason")
            self.assertIn("executor_ok", te, "trace must contain executor_ok")
            # verification 可能为 None（Guard 拒绝时），但字段必须存在
            self.assertIn("verification", te, "trace must contain verification")


class TestRevealPlanGuardRejection(unittest.TestCase):
    """验证 Guard 拒绝时 executor 不调用。"""

    def test_guard_rejection_skips_executor(self):
        """Guard 拒绝的动作不执行，executor_calls == 0。"""
        # 创建一个自定义 ControlRevealer，返回包含非法动作的 RevealPlan
        class CustomRevealer(ControlRevealer):
            def plan(self, app, current_state, **kwargs):
                # 返回一个包含非法 bbox 的动作（超出屏幕）
                return RevealPlan(
                    strategy_id="test",
                    actions=[
                        ActionSpec(
                            action_type="tap_visual",
                            bbox_px=BBox(x1=5000, y1=5000, x2=5100, y2=5100),  # 超出屏幕
                        ),
                    ],
                )

        revealer = CustomRevealer()
        initial_state = _make_reveal_state()
        executor = FakeExecutor(after_state=initial_state)
        verifier = FakeVlmVerifier([])

        action = ActionSpec(action_type="reveal_controls")
        source = MockDecisionSource([action])

        result = run_action_loop(
            source, executor, verifier,
            initial_state=initial_state,
            subgoal="test",
            control_revealer=revealer,
            max_decision_calls=10,
            max_steps=10,
            recovery_budget=0,  # 禁用恢复
        )

        # 验证：executor 未被调用（Guard 拒绝）
        self.assertEqual(len(executor.calls), 0,
                        "Executor should not be called when Guard rejects")

        # 验证：trace 中有记录
        self.assertGreater(len(result.trace), 0, "trace should record the action")

        # 验证：trace 中记录了 Guard 拒绝
        te = result.trace[0]
        self.assertFalse(te["guard_allowed"], "guard_allowed should be False")
        self.assertIsNone(te["executor_ok"], "executor_ok should be None when Guard rejects")


class TestRevealPlanSensitiveAction(unittest.TestCase):
    """验证敏感动作被 Guard 拒绝。"""

    def test_sensitive_action_rejected(self):
        """敏感动作（如支付）被 Guard 拒绝，executor 不调用。"""
        # 创建一个自定义 ControlRevealer，返回包含敏感动作的 RevealPlan
        class SensitiveRevealer(ControlRevealer):
            def plan(self, app, current_state, **kwargs):
                # 返回一个包含敏感候选的动作
                candidate = make_candidate("pay_btn", risk_category="payment")
                candidate_map = make_candidate_map(candidates=[candidate])
                # 更新 state 以包含这个候选
                return RevealPlan(
                    strategy_id="sensitive",
                    actions=[
                        ActionSpec(
                            action_type="tap_candidate",
                            candidate_id="pay_btn",
                            candidate_map_fingerprint="v1",
                        ),
                    ],
                )

        revealer = SensitiveRevealer()
        # 创建包含敏感候选的 state
        candidate = make_candidate("pay_btn", risk_category="payment")
        candidate_map = make_candidate_map(candidates=[candidate])
        initial_state = make_state(
            fingerprint="fp1",
            package="com.test",
            activity="Main",
            candidate_map=candidate_map,
        )
        executor = FakeExecutor(after_state=initial_state)
        verifier = FakeVlmVerifier([])

        action = ActionSpec(action_type="reveal_controls")
        source = MockDecisionSource([action])

        result = run_action_loop(
            source, executor, verifier,
            initial_state=initial_state,
            subgoal="test",
            control_revealer=revealer,
            max_decision_calls=10,
            max_steps=10,
            recovery_budget=0,
        )

        # 验证：executor 未被调用（Guard 拒绝敏感动作）
        self.assertEqual(len(executor.calls), 0,
                        "Executor should not be called for sensitive actions")

        # 验证：trace 中有记录
        self.assertGreater(len(result.trace), 0, "trace should record the action")

        # 验证：trace 中记录了 Guard 拒绝
        te = result.trace[0]
        self.assertFalse(te["guard_allowed"], "guard_allowed should be False")
        self.assertEqual(te["guard_risk_level"], "high", "risk_level should be high for payment")
        self.assertIsNone(te["executor_ok"], "executor_ok should be None when Guard rejects")


class TestRecoveryActionVerifierCalled(unittest.TestCase):
    """验证 recovery 动作的 verifier 被调用。"""

    def test_recovery_action_verifier_called(self):
        """recovery 动作执行后，verifier 必须被调用。"""
        # 创建一个会失败的动作，触发 recovery
        class FailingExecutor(FakeExecutor):
            def __init__(self):
                super().__init__(after_state=_make_reveal_state())
                self.call_count = 0

            def execute(self, action, state):
                self.call_count += 1
                self.calls.append(action)
                # 第一次调用失败，后续调用成功
                if self.call_count == 1:
                    return ActionResult(
                        ok=False,
                        action=action,
                        after_state=state,
                        error_code="test_failure"
                    )
                return super().execute(action, state)

        from harness.schemas import ActionResult
        initial_state = _make_reveal_state()
        executor = FailingExecutor()
        verifier = FakeVlmVerifier([])

        # 第一个动作会失败，触发 recovery
        action1 = ActionSpec(
            action_type="tap_visual",
            bbox_px=BBox(x1=100, y1=100, x2=200, y2=200),
        )
        action2 = ActionSpec(
            action_type="tap_visual",
            bbox_px=BBox(x1=100, y1=100, x2=200, y2=200),
        )
        source = MockDecisionSource([action1, action2])

        result = run_action_loop(
            source, executor, verifier,
            initial_state=initial_state,
            subgoal="test",
            max_decision_calls=10,
            max_steps=10,
            recovery_budget=2,
        )

        # 验证：executor 被调用多次（包括 recovery）
        self.assertGreater(len(executor.calls), 1,
                          "Executor should be called multiple times including recovery")

        # 验证：verifier 被调用（通过检查 trace 中的 verification 字段）
        verification_called = False
        for te in result.trace:
            if te.get("verification") is not None:
                verification_called = True
                break

        self.assertTrue(verification_called,
                       "Verifier should be called for executed actions including recovery")


class TestRecoveryActionTraceCompleteness(unittest.TestCase):
    """验证 recovery 动作的 trace 完整性。"""

    def test_recovery_action_trace_complete(self):
        """recovery 动作的 trace 必须包含所有必需字段。"""
        # 创建一个会失败的动作，触发 recovery
        class FailingExecutor(FakeExecutor):
            def __init__(self):
                super().__init__(after_state=_make_reveal_state())
                self.call_count = 0

            def execute(self, action, state):
                self.call_count += 1
                self.calls.append(action)
                # 第一次调用失败，后续调用成功
                if self.call_count == 1:
                    return ActionResult(
                        ok=False,
                        action=action,
                        after_state=state,
                        error_code="test_failure"
                    )
                return super().execute(action, state)

        from harness.schemas import ActionResult
        initial_state = _make_reveal_state()
        executor = FailingExecutor()
        verifier = FakeVlmVerifier([])

        action1 = ActionSpec(
            action_type="tap_visual",
            bbox_px=BBox(x1=100, y1=100, x2=200, y2=200),
        )
        action2 = ActionSpec(
            action_type="tap_visual",
            bbox_px=BBox(x1=100, y1=100, x2=200, y2=200),
        )
        source = MockDecisionSource([action1, action2])

        result = run_action_loop(
            source, executor, verifier,
            initial_state=initial_state,
            subgoal="test",
            max_decision_calls=10,
            max_steps=10,
            recovery_budget=2,
        )

        # 验证：trace 不为空
        self.assertGreater(len(result.trace), 0, "trace should not be empty")

        # 验证：每个 trace 条目都包含所有必需字段
        required_fields = [
            "guard_allowed",
            "guard_reason",
            "executor_ok",
            "verification",
            "verification_source",
            "atomic_action_count",
        ]

        for te in result.trace:
            for field in required_fields:
                self.assertIn(field, te,
                            f"trace must contain {field}, got keys: {list(te.keys())}")

        # 验证：至少有一个 trace 条目的 atomic_action_count > 0（表示 recovery 动作）
        has_recovery = False
        for te in result.trace:
            if te.get("atomic_action_count", 0) > 0:
                has_recovery = True
                break

        self.assertTrue(has_recovery,
                       "At least one trace entry should have atomic_action_count > 0")


class TestRecoveryActionBudgetExceeded(unittest.TestCase):
    """验证 recovery 动作超过 atomic action budget 时正确停止。"""

    def test_recovery_action_budget_exceeded(self):
        """当 recovery 动作超过 max_steps 时，应该停止执行。"""
        # 创建一个总是失败的 executor
        class AlwaysFailingExecutor(FakeExecutor):
            def execute(self, action, state):
                self.calls.append(action)
                return ActionResult(
                    ok=False,
                    action=action,
                    after_state=state,
                    error_code="always_fail"
                )

        from harness.schemas import ActionResult
        initial_state = _make_reveal_state()
        executor = AlwaysFailingExecutor()
        verifier = FakeVlmVerifier([])

        # 多个动作，每个都会失败并触发 recovery
        actions = [
            ActionSpec(action_type="tap_visual", bbox_px=BBox(x1=100, y1=100, x2=200, y2=200)),
            ActionSpec(action_type="tap_visual", bbox_px=BBox(x1=100, y1=100, x2=200, y2=200)),
            ActionSpec(action_type="tap_visual", bbox_px=BBox(x1=100, y1=100, x2=200, y2=200)),
        ]
        source = MockDecisionSource(actions)

        # 设置很小的 max_steps，使得 recovery 动作会超过预算
        result = run_action_loop(
            source, executor, verifier,
            initial_state=initial_state,
            subgoal="test",
            max_decision_calls=10,
            max_steps=3,  # 很小的预算
            recovery_budget=2,
        )

        # 验证：executor 调用次数不超过 max_steps
        self.assertLessEqual(len(executor.calls), 3,
                           "Executor calls should not exceed max_steps")

        # 验证：最终状态应该是 action_budget_exhausted 或 failed
        self.assertIn(result.status, ["action_budget_exhausted", "failed"],
                     f"Status should be budget_exhausted or failed, got {result.status}")


if __name__ == "__main__":
    unittest.main()
