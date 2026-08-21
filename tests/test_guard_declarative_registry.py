# -*- coding: utf-8 -*-
"""Guard 声明式测试注册表 — 阶段 B。

测试维度：
  - category: unknown_action / candidate_unreachable / low_confidence / sensitive / candidate_map_mismatch
  - dimension: 具体维度（如 error_code, risk_level, requires_refinement）
  - expected_loop_status: action_loop 最终状态
  - expected_executor_calls: executor 调用次数
  - differential_scenario_count: 差异化场景数量
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
from harness.action_guard import validate_action
from tests.mocks import (
    MockDecisionSource, FakeExecutor, FakeVlmVerifier,
    make_candidate, make_candidate_map, make_state,
)


# ─────────────── 声明式 Case Registry ───────────────

def _make_state_with_candidate(**kwargs):
    """构造包含候选的 state。

    支持分离 candidate_map 和 state 参数：
      - cm_package/cm_activity/cm_width/cm_height: candidate_map 的值
      - package/activity/screen_size: state 的值
    """
    candidate_defaults = dict(confidence=0.9, clickable_likelihood=0.9,
                               source="ocr", kind="button")
    candidate_defaults.update(kwargs.pop("candidate_kwargs", {}))
    c = make_candidate("c1", **candidate_defaults)

    # candidate_map 参数
    cm_package = kwargs.pop("cm_package", kwargs.get("package", "com.test"))
    cm_activity = kwargs.pop("cm_activity", kwargs.get("activity", "Main"))
    cm_screen_size = kwargs.pop("cm_screen_size", kwargs.get("screen_size", (1280, 800)))
    cm_width = kwargs.pop("cm_width", cm_screen_size[0])
    cm_height = kwargs.pop("cm_height", cm_screen_size[1])

    # state 参数
    state_kwargs = dict(
        fingerprint=kwargs.pop("fingerprint", "fp1"),
        package=kwargs.pop("package", "com.test"),
        activity=kwargs.pop("activity", "Main"),
        screen_size=kwargs.pop("screen_size", (1280, 800)),
    )
    cm = make_candidate_map(
        candidates=[c],
        package=cm_package,
        activity=cm_activity,
        width=cm_width,
        height=cm_height,
    )
    state_kwargs["candidate_map"] = cm
    state_kwargs.update(kwargs)
    return make_state(**state_kwargs)


def _run_guard_case(case):
    """执行声明式 case 并返回 (guard_decision, loop_result, executor_calls_count)。"""
    action = case["action"]
    state = case["state"]
    config = case.get("config", ActionGuardConfig())
    guard = case.get("guard", ActionGuard())

    # Guard 直接校验
    g = validate_action(action, state, "test", guard.failed_candidates,
                        guard=guard, config=config)

    # action_loop 运行
    source = MockDecisionSource([action])
    executor = FakeExecutor(after_state=state)
    verifier = FakeVlmVerifier([])
    result = run_action_loop(
        source, executor, verifier,
        initial_state=state, subgoal="test",
        guard=guard, config=config,
        recovery_budget=case.get("recovery_budget", 0),
    )

    return g, result, len(executor.calls)


def _make_guard_with_failure(fingerprint, candidate_id):
    """创建已记录失败的 guard。"""
    guard = ActionGuard()
    guard.record_failure(fingerprint, candidate_id)
    return guard


# ─────────────── Case 定义 ───────────────

GUARD_CASES = [
    # ── unknown_action 类别 ──
    {
        "id": "unknown_001",
        "category": "unknown_action",
        "dimension": "action_type",
        "description": "无效 action_type → guard_reject",
        "action": ActionSpec(action_type="invalid_action"),
        "state": _make_state_with_candidate(),
        "expected_error_code": "UNKNOWN_ACTION",
        "expected_risk_level": "high",
        "expected_requires_refinement": False,
        "expected_loop_status": "guard_reject",
        "expected_executor_calls": 0,
    },
    {
        "id": "unknown_002",
        "category": "unknown_action",
        "dimension": "action_type",
        "description": "空 action_type → guard_reject",
        "action": ActionSpec(action_type=""),
        "state": _make_state_with_candidate(),
        "expected_error_code": "UNKNOWN_ACTION",
        "expected_risk_level": "high",
        "expected_requires_refinement": False,
        "expected_loop_status": "guard_reject",
        "expected_executor_calls": 0,
    },

    # ── candidate_unreachable 类别 ──
    {
        "id": "unreachable_001",
        "category": "candidate_unreachable",
        "dimension": "candidate_id",
        "description": "candidate_id 缺失 → guard_reject",
        "action": ActionSpec(action_type="tap_candidate",
                             candidate_map_fingerprint="v1",
                             expected_screen_fingerprint="fp1"),
        "state": _make_state_with_candidate(),
        "expected_error_code": "MISSING_CANDIDATE_ID",
        "expected_risk_level": "high",
        "expected_requires_refinement": False,
        "expected_loop_status": "guard_reject",
        "expected_executor_calls": 0,
    },
    {
        "id": "unreachable_002",
        "category": "candidate_unreachable",
        "dimension": "candidate_map",
        "description": "无 candidate_map → guard_reject",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="c1",
                             candidate_map_fingerprint="v1",
                             expected_screen_fingerprint="fp1"),
        "state": make_state(candidate_map=None),
        "expected_error_code": "NO_CANDIDATE_MAP",
        "expected_risk_level": "high",
        "expected_requires_refinement": False,
        "expected_loop_status": "guard_reject",
        "expected_executor_calls": 0,
    },
    {
        "id": "unreachable_003",
        "category": "candidate_unreachable",
        "dimension": "fingerprint",
        "description": "fingerprint 不匹配 → guard_reject",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="c1",
                             candidate_map_fingerprint="v_OLD",
                             expected_screen_fingerprint="fp1"),
        "state": _make_state_with_candidate(),
        "expected_error_code": "FINGERPRINT_MISMATCH",
        "expected_risk_level": "high",
        "expected_requires_refinement": False,
        "expected_loop_status": "guard_reject",
        "expected_executor_calls": 0,
    },
    {
        "id": "unreachable_004",
        "category": "candidate_unreachable",
        "dimension": "bbox",
        "description": "bbox 越界 → guard_reject",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="c1",
                             candidate_map_fingerprint="v1",
                             expected_screen_fingerprint="fp1"),
        "state": _make_state_with_candidate(
            candidate_kwargs={"bbox": BBox(1200, 100, 1400, 200)}),
        "expected_error_code": "BBOX_OUT_OF_SCREEN",
        "expected_risk_level": "high",
        "expected_requires_refinement": False,
        "expected_loop_status": "guard_reject",
        "expected_executor_calls": 0,
    },
    {
        "id": "unreachable_005",
        "category": "candidate_unreachable",
        "dimension": "previously_failed",
        "description": "候选已失败 → guard_reject",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="c1",
                             candidate_map_fingerprint="v1",
                             expected_screen_fingerprint="fp1"),
        "state": _make_state_with_candidate(),
        "guard": _make_guard_with_failure("fp1", "c1"),
        "expected_error_code": "PREVIOUSLY_FAILED",
        "expected_risk_level": "high",
        "expected_requires_refinement": False,
        "expected_loop_status": "guard_reject",
        "expected_executor_calls": 0,
    },

    # ── low_confidence 类别 ──
    {
        "id": "confidence_001",
        "category": "low_confidence",
        "dimension": "confidence",
        "description": "低 confidence → needs_refinement",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="c1",
                             candidate_map_fingerprint="v1",
                             expected_screen_fingerprint="fp1"),
        "state": _make_state_with_candidate(candidate_kwargs={"confidence": 0.1}),
        "expected_error_code": "LOW_CONFIDENCE",
        "expected_risk_level": "low",
        "expected_requires_refinement": True,
        "expected_loop_status": "needs_refinement",
        "expected_executor_calls": 0,  # recovery_budget=0
    },
    {
        "id": "confidence_002",
        "category": "low_confidence",
        "dimension": "clickable_likelihood",
        "description": "低 clickable_likelihood → needs_refinement",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="c1",
                             candidate_map_fingerprint="v1",
                             expected_screen_fingerprint="fp1"),
        "state": _make_state_with_candidate(
            candidate_kwargs={"clickable_likelihood": 0.1}),
        "expected_error_code": "LOW_CLICKABLE_LIKELIHOOD",
        "expected_risk_level": "low",
        "expected_requires_refinement": True,
        "expected_loop_status": "needs_refinement",
        "expected_executor_calls": 0,
    },
    {
        "id": "confidence_003",
        "category": "low_confidence",
        "dimension": "ocr_only",
        "description": "OCR-only 不允许 → needs_refinement",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="c1",
                             candidate_map_fingerprint="v1",
                             expected_screen_fingerprint="fp1"),
        "state": _make_state_with_candidate(
            candidate_kwargs={"source": "ocr", "kind": ""}),
        "config": ActionGuardConfig(allow_ocr_only_tap=False),
        "expected_error_code": "OCR_ONLY_NOT_ALLOWED",
        "expected_risk_level": "low",
        "expected_requires_refinement": True,
        "expected_loop_status": "needs_refinement",
        "expected_executor_calls": 0,
    },
    {
        "id": "confidence_004",
        "category": "low_confidence",
        "dimension": "threshold_epsilon",
        "description": "confidence 恰好等于阈值 → 通过（epsilon 测试）",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="c1",
                             candidate_map_fingerprint="v1",
                             expected_screen_fingerprint="fp1"),
        "state": _make_state_with_candidate(
            candidate_kwargs={"confidence": 0.5}),  # 恰好等于默认阈值
        "expected_error_code": None,
        "expected_risk_level": "low",
        "expected_requires_refinement": False,
        "expected_loop_status": None,  # 不检查 loop status
        "expected_executor_calls": None,  # 不检查 executor calls
    },

    # ── sensitive 类别 ──
    {
        "id": "sensitive_001",
        "category": "sensitive",
        "dimension": "risk_level_high",
        "description": "payment risk → guard_reject (high)",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="c1",
                             candidate_map_fingerprint="v1",
                             expected_screen_fingerprint="fp1"),
        "state": _make_state_with_candidate(
            candidate_kwargs={"risk_category": "payment"}),
        "expected_error_code": "SENSITIVE_TARGET",
        "expected_risk_level": "high",
        "expected_requires_refinement": False,
        "expected_loop_status": "guard_reject",
        "expected_executor_calls": 0,
    },
    {
        "id": "sensitive_002",
        "category": "sensitive",
        "dimension": "risk_level_high",
        "description": "delete risk → guard_reject (high)",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="c1",
                             candidate_map_fingerprint="v1",
                             expected_screen_fingerprint="fp1"),
        "state": _make_state_with_candidate(
            candidate_kwargs={"risk_category": "delete"}),
        "expected_error_code": "SENSITIVE_TARGET",
        "expected_risk_level": "high",
        "expected_requires_refinement": False,
        "expected_loop_status": "guard_reject",
        "expected_executor_calls": 0,
    },
    {
        "id": "sensitive_003",
        "category": "sensitive",
        "dimension": "risk_level_medium",
        "description": "logout risk → needs_user_confirmation (medium)",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="c1",
                             candidate_map_fingerprint="v1",
                             expected_screen_fingerprint="fp1"),
        "state": _make_state_with_candidate(
            candidate_kwargs={"risk_category": "logout"}),
        "expected_error_code": "SENSITIVE_TARGET",
        "expected_risk_level": "medium",
        "expected_requires_refinement": False,
        "expected_loop_status": "needs_user_confirmation",
        "expected_executor_calls": 0,
    },
    {
        "id": "sensitive_004",
        "category": "sensitive",
        "dimension": "risk_level_medium",
        "description": "password risk → needs_user_confirmation (medium)",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="c1",
                             candidate_map_fingerprint="v1",
                             expected_screen_fingerprint="fp1"),
        "state": _make_state_with_candidate(
            candidate_kwargs={"risk_category": "password"}),
        "expected_error_code": "SENSITIVE_TARGET",
        "expected_risk_level": "medium",
        "expected_requires_refinement": False,
        "expected_loop_status": "needs_user_confirmation",
        "expected_executor_calls": 0,
    },
    {
        "id": "sensitive_005",
        "category": "sensitive",
        "dimension": "sensitive_category",
        "description": "sensitive_category → needs_user_confirmation (medium)",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="c1",
                             candidate_map_fingerprint="v1",
                             expected_screen_fingerprint="fp1"),
        "state": _make_state_with_candidate(
            candidate_kwargs={"sensitive_category": "confirm_payment"}),
        "expected_error_code": "SENSITIVE_TARGET",
        "expected_risk_level": "medium",
        "expected_requires_refinement": False,
        "expected_loop_status": "needs_user_confirmation",
        "expected_executor_calls": 0,
    },
    {
        "id": "sensitive_006",
        "category": "sensitive",
        "dimension": "action_semantics",
        "description": "action_semantics 含敏感词 → needs_user_confirmation (medium)",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="c1",
                             candidate_map_fingerprint="v1",
                             expected_screen_fingerprint="fp1"),
        "state": _make_state_with_candidate(
            candidate_kwargs={"action_semantics": "确认支付"}),
        "expected_error_code": "SENSITIVE_TARGET",
        "expected_risk_level": "medium",
        "expected_requires_refinement": False,
        "expected_loop_status": "needs_user_confirmation",
        "expected_executor_calls": 0,
    },
    {
        "id": "sensitive_007",
        "category": "sensitive",
        "dimension": "sensitive_hint",
        "description": "sensitive_hint → needs_user_confirmation (medium)",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="c1",
                             candidate_map_fingerprint="v1",
                             expected_screen_fingerprint="fp1",
                             sensitive_hint="this is sensitive"),
        "state": _make_state_with_candidate(),
        "expected_error_code": "SENSITIVE_TARGET",
        "expected_risk_level": "medium",
        "expected_requires_refinement": False,
        "expected_loop_status": "needs_user_confirmation",
        "expected_executor_calls": 0,
    },

    # ── candidate_map_mismatch 类别 ──
    {
        "id": "mismatch_001",
        "category": "candidate_map_mismatch",
        "dimension": "package",
        "description": "package 不匹配 → guard_reject",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="c1",
                             candidate_map_fingerprint="v1",
                             expected_screen_fingerprint="fp1"),
        "state": _make_state_with_candidate(
            package="com.wrong", cm_package="com.test"),
        "expected_error_code": "CANDIDATE_MAP_PACKAGE_MISMATCH",
        "expected_risk_level": "high",
        "expected_requires_refinement": False,
        "expected_loop_status": "guard_reject",
        "expected_executor_calls": 0,
    },
    {
        "id": "mismatch_002",
        "category": "candidate_map_mismatch",
        "dimension": "activity",
        "description": "activity 不匹配 → guard_reject",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="c1",
                             candidate_map_fingerprint="v1",
                             expected_screen_fingerprint="fp1"),
        "state": _make_state_with_candidate(
            activity="Wrong", cm_activity="Main"),
        "expected_error_code": "CANDIDATE_MAP_ACTIVITY_MISMATCH",
        "expected_risk_level": "high",
        "expected_requires_refinement": False,
        "expected_loop_status": "guard_reject",
        "expected_executor_calls": 0,
    },
    {
        "id": "mismatch_003",
        "category": "candidate_map_mismatch",
        "dimension": "size",
        "description": "screen_size 不匹配 → guard_reject",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="c1",
                             candidate_map_fingerprint="v1",
                             expected_screen_fingerprint="fp1"),
        "state": _make_state_with_candidate(
            screen_size=(1920, 1080), cm_screen_size=(1280, 800)),
        "expected_error_code": "CANDIDATE_MAP_SIZE_MISMATCH",
        "expected_risk_level": "high",
        "expected_requires_refinement": False,
        "expected_loop_status": "guard_reject",
        "expected_executor_calls": 0,
    },
]


# ─────────────── 声明式测试执行 ───────────────

class TestGuardDeclarativeRegistry(unittest.TestCase):
    """执行声明式注册表中的所有 case。"""

    def test_all_cases(self):
        """执行所有 case 并验证。"""
        failed_cases = []

        for case in GUARD_CASES:
            try:
                g, result, executor_calls = _run_guard_case(case)

                # 验证 Guard 输出
                self.assertEqual(
                    g.error_code, case["expected_error_code"],
                    f"Case {case['id']}: error_code mismatch"
                )
                self.assertEqual(
                    g.risk_level, case["expected_risk_level"],
                    f"Case {case['id']}: risk_level mismatch"
                )
                self.assertEqual(
                    g.requires_refinement, case["expected_requires_refinement"],
                    f"Case {case['id']}: requires_refinement mismatch"
                )

                # 验证 action_loop 状态
                if case["expected_loop_status"] is not None:
                    self.assertEqual(
                        result.status, case["expected_loop_status"],
                        f"Case {case['id']}: loop status mismatch"
                    )

                # 验证 executor 调用次数
                if case["expected_executor_calls"] is not None:
                    self.assertEqual(
                        executor_calls, case["expected_executor_calls"],
                        f"Case {case['id']}: executor_calls mismatch"
                    )

                # 零副作用断言：被拒绝的 case executor 调用必须为 0
                if result.status in ("guard_reject", "needs_user_confirmation"):
                    self.assertEqual(
                        executor_calls, 0,
                        f"Case {case['id']}: rejected but executor called {executor_calls} times"
                    )

            except AssertionError as e:
                failed_cases.append(f"{case['id']}: {str(e)}")

        if failed_cases:
            self.fail(f"Failed cases:\n" + "\n".join(failed_cases))

    def test_registry_completeness(self):
        """验证注册表覆盖所有类别。"""
        categories = set(c["category"] for c in GUARD_CASES)
        expected_categories = {
            "unknown_action",
            "candidate_unreachable",
            "low_confidence",
            "sensitive",
            "candidate_map_mismatch",
        }
        self.assertEqual(categories, expected_categories)

    def test_registry_metrics(self):
        """验证注册表统计信息。"""
        total_cases = len(GUARD_CASES)
        differential_scenarios = sum(
            1 for c in GUARD_CASES
            if c["expected_loop_status"] in ("guard_reject", "needs_user_confirmation", "needs_refinement")
        )

        # 至少 20 个 case
        self.assertGreaterEqual(total_cases, 20)
        # 至少 15 个差异化场景
        self.assertGreaterEqual(differential_scenarios, 15)

        # 输出统计信息供 metrics 使用
        print(f"\n[Registry Stats]")
        print(f"  Total cases: {total_cases}")
        print(f"  Differential scenarios: {differential_scenarios}")
        print(f"  Categories: {len(set(c['category'] for c in GUARD_CASES))}")
        print(f"  Dimensions: {len(set(c['dimension'] for c in GUARD_CASES))}")


# ─────────────── 阈值 Epsilon 测试 ───────────────

class TestThresholdEpsilon(unittest.TestCase):
    """阈值边界测试（epsilon 精度）。"""

    def test_confidence_exactly_at_threshold(self):
        """confidence 恰好等于阈值 → 通过。"""
        state = _make_state_with_candidate(
            candidate_kwargs={"confidence": 0.5})  # 恰好等于默认阈值
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                           candidate_map_fingerprint="v1",
                           expected_screen_fingerprint="fp1")
        g = validate_action(action, state, "test", set())
        self.assertTrue(g.allowed)
        self.assertFalse(g.requires_refinement)

    def test_confidence_just_below_threshold(self):
        """confidence 略低于阈值 → requires_refinement。"""
        state = _make_state_with_candidate(
            candidate_kwargs={"confidence": 0.499})
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                           candidate_map_fingerprint="v1",
                           expected_screen_fingerprint="fp1")
        g = validate_action(action, state, "test", set())
        self.assertFalse(g.allowed)
        self.assertTrue(g.requires_refinement)

    def test_clickable_exactly_at_threshold(self):
        """clickable_likelihood 恰好等于阈值 → 通过。"""
        state = _make_state_with_candidate(
            candidate_kwargs={"clickable_likelihood": 0.3})
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                           candidate_map_fingerprint="v1",
                           expected_screen_fingerprint="fp1")
        g = validate_action(action, state, "test", set())
        self.assertTrue(g.allowed)
        self.assertFalse(g.requires_refinement)

    def test_clickable_just_below_threshold(self):
        """clickable_likelihood 略低于阈值 → requires_refinement。"""
        state = _make_state_with_candidate(
            candidate_kwargs={"clickable_likelihood": 0.299})
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                           candidate_map_fingerprint="v1",
                           expected_screen_fingerprint="fp1")
        g = validate_action(action, state, "test", set())
        self.assertFalse(g.allowed)
        self.assertTrue(g.requires_refinement)


# ─────────────── 零副作用全局断言 ───────────────

class TestZeroSideEffectAssertion(unittest.TestCase):
    """全局零副作用断言：所有被拒绝的 case executor 调用必须为 0。"""

    def test_all_rejected_cases_zero_executor_calls(self):
        """遍历所有 case，验证被拒绝的 case executor 调用为 0。"""
        for case in GUARD_CASES:
            g, result, executor_calls = _run_guard_case(case)

            # 被拒绝的 case
            if result.status in ("guard_reject", "needs_user_confirmation"):
                self.assertEqual(
                    executor_calls, 0,
                    f"Case {case['id']} ({case['description']}): "
                    f"rejected with status={result.status} but executor called {executor_calls} times"
                )


if __name__ == "__main__":
    unittest.main()
