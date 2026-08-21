# -*- coding: utf-8 -*-
"""Control Revealer State Machine Tests — active/probation/stale、基础设施失败不污染、stale generic fallback、新版本保留历史。

运行：
  cd harness-framework
  python -m unittest tests.test_control_revealer_state_machine -v
"""
import json
import os
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
_SRC_ROOT = os.path.join(_PROJECT_ROOT, "src")
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)

from harness.schemas import ActionSpec, UiState, ActionResult, RevealPlan
from harness.types import BBox, Candidate, CandidateMap
from harness.verifier import VerificationResult, VerificationStatus
from harness.control_revealer import (
    RevealStrategyRecord,
    RevealStrategyManager,
    ControlRevealer,
)
from tests.mocks import make_state, make_candidate_map, FakeExecutor


# ═══════════════ Mock 基础设施 ═══════════════

class RevealerFakeExecutor:
    """模拟 ActionExecutor，可配置执行后的状态。"""

    def __init__(self, after_state=None, ok=True):
        self.after_state = after_state
        self.ok = ok
        self.calls = []

    def execute(self, action: ActionSpec, state: UiState) -> ActionResult:
        self.calls.append(action)
        after = self.after_state if self.after_state is not None else state
        return ActionResult(ok=self.ok, action=action, after_state=after)


class RevealerFakeVerifier:
    """模拟 StateVerifier。"""

    def verify(self, before: UiState, after: UiState, action: ActionSpec):
        return VerificationResult(
            verification=VerificationStatus.success,
            source="mock",
            reason="mock verify"
        )


# ═══════════════ 状态转换测试 ═══════════════

class TestStateTransitions(unittest.TestCase):
    """测试状态机转换：active → probation → stale。"""

    def test_01_initial_state_is_active(self):
        """新策略初始状态为 active。"""
        record = RevealStrategyRecord(strategy_id="s1", app="com.test")
        self.assertEqual(record.state, "active")
        self.assertEqual(record.consecutive_failures, 0)
        self.assertEqual(record.success_count, 0)
        self.assertEqual(record.failure_count, 0)

    def test_02_active_to_probation(self):
        """active: consecutive_failures=2 后 state=probation。"""
        record = RevealStrategyRecord(strategy_id="s1", app="com.test")
        record.record_semantic_failure()
        self.assertEqual(record.state, "active")
        self.assertEqual(record.consecutive_failures, 1)

        record.record_semantic_failure()
        self.assertEqual(record.state, "probation")
        self.assertEqual(record.consecutive_failures, 2)

    def test_03_probation_to_active(self):
        """probation: 连续 2 次 success 后 state=active。"""
        record = RevealStrategyRecord(strategy_id="s1", app="com.test")
        record.record_semantic_failure()
        record.record_semantic_failure()
        self.assertEqual(record.state, "probation")

        # 2 次连续成功 → 恢复 active
        record.record_success(100.0)
        self.assertEqual(record.state, "probation")  # 只有 1 次
        record.record_success(100.0)
        self.assertEqual(record.state, "active")

    def test_04_probation_to_stale(self):
        """probation: consecutive_failures=3 后 state=stale。"""
        record = RevealStrategyRecord(strategy_id="s1", app="com.test")
        record.record_semantic_failure()
        record.record_semantic_failure()
        self.assertEqual(record.state, "probation")

        record.record_semantic_failure()
        self.assertEqual(record.state, "stale")
        self.assertEqual(record.consecutive_failures, 3)

    def test_05_active_to_stale_consecutive(self):
        """active: consecutive_failures=3 后 state=stale。"""
        record = RevealStrategyRecord(strategy_id="s1", app="com.test")
        record.record_semantic_failure()
        record.record_semantic_failure()
        record.record_semantic_failure()
        self.assertEqual(record.state, "stale")

    def test_06_active_to_stale_rolling_window(self):
        """rolling window: 5 次中 4 次 failure → state=stale。"""
        record = RevealStrategyRecord(strategy_id="s1", app="com.test")
        # 模式: S F F F F → consecutive_failures 不会到 3（因为有 reset）
        # 但实际上 record_success 会 reset consecutive_failures
        # 我们需要 5 次中 4 次 failure 但 consecutive < 3
        # 模式: F F S F F → consecutive_failures: 1,2,0,1,2
        # 不行，consecutive 到不了 3 但 rolling window 有 4 个 failure
        record.record_semantic_failure()  # F: consec=1, window=[F]
        record.record_semantic_failure()  # F: consec=2, window=[F,F]
        record.record_success(100.0)       # S: consec=0, window=[F,F,S]
        record.record_semantic_failure()  # F: consec=1, window=[F,F,S,F]
        record.record_semantic_failure()  # F: consec=2, window=[F,F,S,F,F]
        # window 有 4/5 failures → stale
        self.assertEqual(record.state, "stale")

    def test_07_infrastructure_failure_no_pollution(self):
        """基础设施失败不污染统计。"""
        record = RevealStrategyRecord(strategy_id="s1", app="com.test")
        record.record_success(100.0)
        initial_success = record.success_count
        initial_failure = record.failure_count
        initial_consec = record.consecutive_failures
        initial_rate = record.success_rate

        record.record_infrastructure_failure()

        self.assertEqual(record.success_count, initial_success)
        self.assertEqual(record.failure_count, initial_failure)
        self.assertEqual(record.consecutive_failures, initial_consec)
        self.assertEqual(record.success_rate, initial_rate)
        self.assertEqual(record.state, "active")

    def test_08_success_resets_consecutive_failures(self):
        """成功重置连续失败计数。"""
        record = RevealStrategyRecord(strategy_id="s1", app="com.test")
        record.record_semantic_failure()
        record.record_semantic_failure()
        self.assertEqual(record.consecutive_failures, 2)

        record.record_success(50.0)
        self.assertEqual(record.consecutive_failures, 0)
        # 1 次 success 后 consecutive_failures=0，但 probation → active 需连续 2 次 success
        self.assertEqual(record.state, "probation")


# ═══════════════ 策略过滤测试 ═══════════════

class TestStrategyFiltering(unittest.TestCase):
    """测试策略过滤：app + activity_pattern + orientation。"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "strategies.json")

    def test_09_filter_by_app(self):
        """按 app 过滤策略。"""
        manager = RevealStrategyManager(storage_path=self.storage_path)
        r1 = RevealStrategyRecord(strategy_id="s1", app="com.app1")
        r2 = RevealStrategyRecord(strategy_id="s2", app="com.app2")
        manager.register(r1)
        manager.register(r2)

        strategies = manager.get_active_strategies(app="com.app1")
        self.assertEqual(len(strategies), 1)
        self.assertEqual(strategies[0].strategy_id, "s1")

    def test_10_filter_by_activity_pattern_match(self):
        """activity_pattern fnmatch 匹配。"""
        manager = RevealStrategyManager(storage_path=self.storage_path)
        r1 = RevealStrategyRecord(
            strategy_id="player",
            app="com.test",
            activity_pattern="*Player*"
        )
        manager.register(r1)

        strategies = manager.get_active_strategies(
            app="com.test", activity="VideoPlayerActivity"
        )
        self.assertEqual(len(strategies), 1)

    def test_11_filter_by_activity_pattern_no_match(self):
        """activity_pattern fnmatch 不匹配。"""
        manager = RevealStrategyManager(storage_path=self.storage_path)
        r1 = RevealStrategyRecord(
            strategy_id="player",
            app="com.test",
            activity_pattern="*Player*"
        )
        manager.register(r1)

        strategies = manager.get_active_strategies(
            app="com.test", activity="SettingsActivity"
        )
        self.assertEqual(len(strategies), 0)

    def test_12_filter_by_orientation_match(self):
        """orientation 匹配。"""
        manager = RevealStrategyManager(storage_path=self.storage_path)
        r1 = RevealStrategyRecord(
            strategy_id="landscape",
            app="com.test",
            orientation="landscape"
        )
        manager.register(r1)

        strategies = manager.get_active_strategies(
            app="com.test", orientation="landscape"
        )
        self.assertEqual(len(strategies), 1)

    def test_13_filter_by_orientation_no_match(self):
        """orientation 不匹配。"""
        manager = RevealStrategyManager(storage_path=self.storage_path)
        r1 = RevealStrategyRecord(
            strategy_id="landscape",
            app="com.test",
            orientation="landscape"
        )
        manager.register(r1)

        strategies = manager.get_active_strategies(
            app="com.test", orientation="portrait"
        )
        self.assertEqual(len(strategies), 0)

    def test_14_exclude_stale(self):
        """排除 stale 策略。"""
        manager = RevealStrategyManager(storage_path=self.storage_path)
        r1 = RevealStrategyRecord(strategy_id="s1", app="com.test")
        r2 = RevealStrategyRecord(strategy_id="s2", app="com.test")
        manager.register(r1)
        manager.register(r2)

        r2.record_semantic_failure()
        r2.record_semantic_failure()
        r2.record_semantic_failure()
        self.assertEqual(r2.state, "stale")

        strategies = manager.get_active_strategies(app="com.test")
        self.assertEqual(len(strategies), 1)
        self.assertEqual(strategies[0].strategy_id, "s1")


# ═══════════════ 完整字段 save/load 测试 ═══════════════

class TestSaveLoad(unittest.TestCase):
    """测试完整字段序列化/反序列化。"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "strategies.json")

    def test_15_full_fields_save_load(self):
        """所有字段都能正确保存和加载。"""
        manager1 = RevealStrategyManager(storage_path=self.storage_path)
        r = RevealStrategyRecord(
            strategy_id="test",
            app="com.test",
            activity_pattern="*Activity",
            orientation="landscape",
            actions=[{"type": "tap", "x": 0.5, "y": 0.5}],
            version=3,
            history=["success", "failure", "success"],
        )
        r.record_success(100.0)
        r.record_semantic_failure()
        manager1.register(r)

        # 新 manager 加载
        manager2 = RevealStrategyManager(storage_path=self.storage_path)
        loaded = manager2.get_strategy("test")

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.strategy_id, "test")
        self.assertEqual(loaded.app, "com.test")
        self.assertEqual(loaded.activity_pattern, "*Activity")
        self.assertEqual(loaded.orientation, "landscape")
        self.assertEqual(loaded.actions, [{"type": "tap", "x": 0.5, "y": 0.5}])
        self.assertEqual(loaded.version, 3)
        self.assertEqual(loaded.history, ["success", "failure", "success"])
        self.assertEqual(loaded.success_count, 1)
        self.assertEqual(loaded.failure_count, 1)

    def test_16_json_roundtrip(self):
        """JSON 文件 roundtrip 验证。"""
        manager = RevealStrategyManager(storage_path=self.storage_path)
        r = RevealStrategyRecord(
            strategy_id="roundtrip",
            app="com.test",
            activity_pattern="*Main",
            orientation="portrait",
            actions=[{"type": "remote_key", "key": "MENU"}],
            version=2,
            history=["failure", "failure"],
        )
        manager.register(r)

        self.assertTrue(os.path.exists(self.storage_path))
        with open(self.storage_path, "r") as f:
            data = json.load(f)
        self.assertIn("strategies", data)
        self.assertEqual(len(data["strategies"]), 1)
        item = data["strategies"][0]
        self.assertEqual(item["strategy_id"], "roundtrip")
        self.assertEqual(item["activity_pattern"], "*Main")
        self.assertEqual(item["orientation"], "portrait")
        self.assertEqual(item["version"], 2)


# ═══════════════ 新版本保留历史测试 ═══════════════

class TestNewVersionPreservesHistory(unittest.TestCase):
    """stale 后 register 新版本，旧版本 history 非空。"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "strategies.json")

    def test_17_new_version_preserves_old_history(self):
        """新版本保留旧版本历史。"""
        manager = RevealStrategyManager(storage_path=self.storage_path)

        # v1
        r1 = RevealStrategyRecord(strategy_id="tap_center", app="com.test")
        manager.register(r1)
        r1.record_semantic_failure()
        r1.record_semantic_failure()
        r1.record_semantic_failure()
        self.assertEqual(r1.state, "stale")
        self.assertEqual(r1.version, 1)

        # register v2
        r2 = RevealStrategyRecord(strategy_id="tap_center", app="com.test")
        manager.register(r2)

        # r1 的历史被保存
        self.assertIsNotNone(manager.get_strategy("tap_center"))
        # r2 是新版本
        self.assertEqual(r2.version, 2)
        self.assertEqual(r2.strategy_id, "tap_center_v2")
        self.assertEqual(r2.state, "active")

    def test_18_multiple_versions(self):
        """多版本共存。"""
        manager = RevealStrategyManager(storage_path=self.storage_path)

        # v1 → stale
        r1 = RevealStrategyRecord(strategy_id="swipe", app="com.test")
        manager.register(r1)
        r1.record_semantic_failure()
        r1.record_semantic_failure()
        r1.record_semantic_failure()

        # v2 → stale
        r2 = RevealStrategyRecord(strategy_id="swipe", app="com.test")
        manager.register(r2)
        r2.record_semantic_failure()
        r2.record_semantic_failure()
        r2.record_semantic_failure()

        # v3
        r3 = RevealStrategyRecord(strategy_id="swipe", app="com.test")
        manager.register(r3)

        self.assertEqual(r3.version, 3)
        self.assertEqual(r3.strategy_id, "swipe_v3")
        self.assertIsNotNone(manager.get_strategy("swipe"))
        self.assertIsNotNone(manager.get_strategy("swipe_v2"))
        self.assertIsNotNone(manager.get_strategy("swipe_v3"))


# ═══════════════ Stale Generic Fallback 测试 ═══════════════

class TestStaleGenericFallback(unittest.TestCase):
    """无匹配策略时使用 default。"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "strategies.json")

    def test_19_generic_fallback_when_no_strategy(self):
        """无匹配策略时 select_best 返回 None → ControlRevealer 使用 generic。"""
        manager = RevealStrategyManager(storage_path=self.storage_path)
        revealer = ControlRevealer(strategy_manager=manager)

        # 无注册策略
        best = manager.select_best(app="com.unknown")
        self.assertIsNone(best)

    def test_20_generic_fallback_used_in_plan(self):
        """plan() 中使用 generic fallback。"""
        manager = RevealStrategyManager(storage_path=self.storage_path)
        revealer = ControlRevealer(strategy_manager=manager)

        current_state = make_state(control_bar_visible=False)

        plan = revealer.plan(app="com.unknown", current_state=current_state)
        # 使用 generic 策略
        self.assertEqual(plan.strategy_id, "generic")
        self.assertIsInstance(plan, RevealPlan)
        self.assertGreater(len(plan.actions), 0)
        # 所有 actions 都是 ActionSpec
        for action in plan.actions:
            self.assertIsInstance(action, ActionSpec)


# ═══════════════ Plan 输出测试 ═══════════════

class TestRevealPlanOutput(unittest.TestCase):
    """验证 ControlRevealer.plan() 输出。"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "strategies.json")

    def test_21_plan_returns_actionspec_list(self):
        """plan() 返回 RevealPlan(strategy_id, list[ActionSpec])。"""
        manager = RevealStrategyManager(storage_path=self.storage_path)
        revealer = ControlRevealer(strategy_manager=manager)

        current_state = make_state(control_bar_visible=False)

        plan = revealer.plan(app="com.test", current_state=current_state)
        self.assertEqual(plan.strategy_id, "generic")
        self.assertIsInstance(plan.actions, list)
        for action in plan.actions:
            self.assertIsInstance(action, ActionSpec)
            # 每个 action 都必须是合法 action_type
            self.assertIn(action.action_type,
                          {"tap_visual", "remote_key", "media_key", "swipe", "back"})

    def test_22_plan_with_registered_strategy(self):
        """有注册策略时使用该策略。"""
        manager = RevealStrategyManager(storage_path=self.storage_path)
        r1 = RevealStrategyRecord(
            strategy_id="tap_center",
            app="com.test",
            actions=[{"type": "tap", "x": 0.5, "y": 0.5, "wait_ms": 100}],
        )
        manager.register(r1)
        revealer = ControlRevealer(strategy_manager=manager)

        current_state = make_state(control_bar_visible=False)

        plan = revealer.plan(app="com.test", current_state=current_state)
        self.assertEqual(plan.strategy_id, "tap_center")
        self.assertEqual(len(plan.actions), 1)
        self.assertEqual(plan.actions[0].action_type, "tap_visual")

    def test_23_plan_uses_policy_max_steps(self):
        """plan() 受 RevealPolicyConfig.max_recovery_steps 限制。"""
        from harness.schemas import RevealPolicyConfig
        policy = RevealPolicyConfig(max_recovery_steps=2)
        manager = RevealStrategyManager(storage_path=self.storage_path, policy=policy)
        r1 = RevealStrategyRecord(
            strategy_id="long_seq",
            app="com.test",
            actions=[
                {"type": "remote_key", "key": "MENU", "wait_ms": 100},
                {"type": "remote_key", "key": "BACK", "wait_ms": 100},
                {"type": "remote_key", "key": "ENTER", "wait_ms": 100},
                {"type": "remote_key", "key": "DPAD_CENTER", "wait_ms": 100},
            ],
            policy=policy,
        )
        manager.register(r1)
        revealer = ControlRevealer(strategy_manager=manager, policy=policy)

        current_state = make_state(control_bar_visible=False)

        plan = revealer.plan(app="com.test", current_state=current_state)
        # 受 policy.max_recovery_steps=2 限制
        self.assertLessEqual(len(plan.actions), 2)

    def test_24_record_success_updates_strategy(self):
        """record_success 更新策略状态。"""
        manager = RevealStrategyManager(storage_path=self.storage_path)
        r1 = RevealStrategyRecord(strategy_id="s1", app="com.test")
        manager.register(r1)
        revealer = ControlRevealer(strategy_manager=manager)

        revealer.record_success("s1", 100.0)
        updated = manager.get_strategy("s1")
        self.assertEqual(updated.success_count, 1)
        self.assertEqual(updated.consecutive_failures, 0)

    def test_25_record_semantic_failure_updates_strategy(self):
        """record_semantic_failure 更新策略状态。"""
        manager = RevealStrategyManager(storage_path=self.storage_path)
        r1 = RevealStrategyRecord(strategy_id="s1", app="com.test")
        manager.register(r1)
        revealer = ControlRevealer(strategy_manager=manager)

        revealer.record_semantic_failure("s1")
        updated = manager.get_strategy("s1")
        self.assertEqual(updated.failure_count, 1)
        self.assertEqual(updated.consecutive_failures, 1)

    def test_26_no_reveal_method(self):
        """ControlRevealer 不再有 reveal() 方法。"""
        manager = RevealStrategyManager(storage_path=self.storage_path)
        revealer = ControlRevealer(strategy_manager=manager)

        self.assertFalse(hasattr(revealer, 'reveal'))
        self.assertFalse(hasattr(revealer, 'set_action_executor'))
        self.assertTrue(hasattr(revealer, 'plan'))
        self.assertTrue(hasattr(revealer, 'record_success'))
        self.assertTrue(hasattr(revealer, 'record_semantic_failure'))
        self.assertTrue(hasattr(revealer, 'record_infrastructure_failure'))


if __name__ == "__main__":
    unittest.main()
