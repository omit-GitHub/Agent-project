# -*- coding: utf-8 -*-
"""Action Guard Injection Tests — ≥50 条，五类异常 + 正常放行。

被拒绝样本 executor_calls 必须为 0。

运行：
  cd harness-framework
  python -m unittest tests.test_action_guard_injection -v
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
    ActionSpec, UiState, ActionGuard, ActionGuardConfig,
    run_action_loop, BBox,
)
from harness.types import Candidate, CandidateMap
from harness.action_guard import validate_action, GuardDecision
from tests.mocks import (
    MockDecisionSource, FakeExecutor, FakeVlmVerifier,
    make_candidate, make_candidate_map, make_state,
)


def _run_and_check(action, state, subgoal="test", guard=None, config=None):
    """运行 action_loop 并返回 (result, executor)。"""
    source = MockDecisionSource([action])
    executor = FakeExecutor(after_state=state)
    verifier = FakeVlmVerifier([])
    result = run_action_loop(
        source, executor, verifier,
        initial_state=state, subgoal=subgoal,
        guard=guard, config=config,
    )
    return result, executor


def _make_valid_candidate(cid="c1", **kwargs):
    """创建满足所有默认阈值的候选。"""
    defaults = dict(
        confidence=0.9,
        clickable_likelihood=0.9,
        source="ocr",
        kind="button",
    )
    defaults.update(kwargs)
    return make_candidate(cid, **defaults)


def _make_valid_state(candidate=None, **kwargs):
    """创建一致性完整的 state（CandidateMap 与 UiState 匹配）。"""
    if candidate is None:
        candidate = _make_valid_candidate()
    cm = make_candidate_map(
        candidates=[candidate],
        package=kwargs.get("package", "com.test"),
        activity=kwargs.get("activity", "Main"),
        width=kwargs.get("screen_size", (1280, 800))[0],
        height=kwargs.get("screen_size", (1280, 800))[1],
    )
    return make_state(candidate_map=cm, **kwargs)


# ═══════════════ 类别 1：未知动作类型 ═══════════════

class TestUnknownActionType(unittest.TestCase):
    """5 条：各种非法 action_type。"""

    def test_01_invalid_action_type(self):
        action = ActionSpec(action_type="invalid_action")
        result, executor = _run_and_check(action, _make_valid_state())
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

    def test_02_empty_action_type(self):
        action = ActionSpec(action_type="")
        result, executor = _run_and_check(action, _make_valid_state())
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

    def test_03_numeric_action_type(self):
        action = ActionSpec(action_type="12345")
        result, executor = _run_and_check(action, _make_valid_state())
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

    def test_04_long_action_type(self):
        action = ActionSpec(action_type="a" * 200)
        result, executor = _run_and_check(action, _make_valid_state())
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

    def test_05_spaces_action_type(self):
        action = ActionSpec(action_type="   ")
        result, executor = _run_and_check(action, _make_valid_state())
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)


# ═══════════════ 类别 2：候选不可达 ═══════════════

class TestCandidateUnreachable(unittest.TestCase):
    """10 条：candidate_id / map / fingerprint / bbox / 失败重放。"""

    def test_06_missing_candidate_id(self):
        state = _make_valid_state()
        action = ActionSpec(action_type="tap_candidate", candidate_id=None,
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

    def test_07_no_candidate_map(self):
        state = make_state(candidate_map=None)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

    def test_08_candidate_not_found(self):
        state = _make_valid_state()
        action = ActionSpec(action_type="tap_candidate", candidate_id="not_exist",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

    def test_09_stale_fingerprint(self):
        state = _make_valid_state()
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v_OLD",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

    def test_10_page_mismatch(self):
        state = _make_valid_state()
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp_WRONG")
        result, executor = _run_and_check(action, state)
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

    def test_11_bbox_out_right(self):
        c = _make_valid_candidate(bbox=BBox(1200, 100, 1400, 200))
        state = _make_valid_state(candidate=c)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

    def test_12_bbox_out_bottom(self):
        c = _make_valid_candidate(bbox=BBox(100, 750, 200, 900))
        state = _make_valid_state(candidate=c)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

    def test_13_bbox_out_left(self):
        # BBox 不允许负数坐标，验证 ValueError
        with self.assertRaises(ValueError):
            BBox(-50, 100, 50, 200)

    def test_14_bbox_out_top(self):
        # BBox 不允许负数坐标，验证 ValueError
        with self.assertRaises(ValueError):
            BBox(100, -50, 200, 50)

    def test_15_previously_failed_candidate(self):
        state = _make_valid_state()
        guard = ActionGuard()
        guard.record_failure("fp1", "c1")
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state, guard=guard)
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)


# ═══════════════ 类别 3：置信度不足 ═══════════════

class TestLowConfidence(unittest.TestCase):
    """7 条：confidence / clickable_likelihood / ocr_only。"""

    def test_16_low_confidence(self):
        c = _make_valid_candidate(confidence=0.1)
        state = _make_valid_state(candidate=c)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

    def test_17_low_clickable_likelihood(self):
        c = _make_valid_candidate(clickable_likelihood=0.1)
        state = _make_valid_state(candidate=c)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

    def test_18_both_low(self):
        c = _make_valid_candidate(confidence=0.1, clickable_likelihood=0.1)
        state = _make_valid_state(candidate=c)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

    def test_19_ocr_only_not_allowed(self):
        c = _make_valid_candidate(source="ocr", kind="")
        state = _make_valid_state(candidate=c)
        config = ActionGuardConfig(allow_ocr_only_tap=False)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state, config=config)
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

    def test_20_ocr_only_allowed(self):
        c = _make_valid_candidate(source="ocr", kind="")
        state = _make_valid_state(candidate=c)
        config = ActionGuardConfig(allow_ocr_only_tap=True)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state, config=config)
        # 应放行（但验证器可能 not_yet → timeout）
        self.assertNotIn(result.status, ("guard_reject", "guard_ask_user"))

    def test_21_confidence_edge_zero(self):
        c = _make_valid_candidate(confidence=0.0)
        state = _make_valid_state(candidate=c)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

    def test_22_clickable_edge_zero(self):
        c = _make_valid_candidate(clickable_likelihood=0.0)
        state = _make_valid_state(candidate=c)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)


# ═══════════════ 类别 4：敏感操作 ═══════════════

class TestSensitiveOperations(unittest.TestCase):
    """14 条：risk_category / sensitive_category / action_semantics / hint。"""

    def test_23_payment_risk_reject(self):
        c = _make_valid_candidate(risk_category="payment")
        state = _make_valid_state(candidate=c)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertEqual(result.status, "guard_reject")
        self.assertEqual(len(executor.calls), 0)

    def test_24_delete_risk_reject(self):
        c = _make_valid_candidate(risk_category="delete")
        state = _make_valid_state(candidate=c)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertEqual(result.status, "guard_reject")
        self.assertEqual(len(executor.calls), 0)

    def test_25_logout_risk_ask_user(self):
        c = _make_valid_candidate(risk_category="logout")
        state = _make_valid_state(candidate=c)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertEqual(result.status, "guard_ask_user")
        self.assertEqual(len(executor.calls), 0)

    def test_26_password_risk_ask_user(self):
        c = _make_valid_candidate(risk_category="password")
        state = _make_valid_state(candidate=c)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertEqual(result.status, "guard_ask_user")
        self.assertEqual(len(executor.calls), 0)

    def test_27_send_risk_ask_user(self):
        c = _make_valid_candidate(risk_category="send")
        state = _make_valid_state(candidate=c)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertEqual(result.status, "guard_ask_user")
        self.assertEqual(len(executor.calls), 0)

    def test_28_sensitive_category(self):
        c = _make_valid_candidate(sensitive_category="confirm_payment")
        state = _make_valid_state(candidate=c)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertEqual(result.status, "guard_ask_user")
        self.assertEqual(len(executor.calls), 0)

    def test_29_action_semantics_payment(self):
        c = _make_valid_candidate(action_semantics="确认支付")
        state = _make_valid_state(candidate=c)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertEqual(result.status, "guard_ask_user")
        self.assertEqual(len(executor.calls), 0)

    def test_30_action_semantics_delete(self):
        c = _make_valid_candidate(action_semantics="删除文件")
        state = _make_valid_state(candidate=c)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertEqual(result.status, "guard_ask_user")
        self.assertEqual(len(executor.calls), 0)

    def test_31_sensitive_hint(self):
        c = _make_valid_candidate()
        state = _make_valid_state(candidate=c)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1",
                            sensitive_hint="this is sensitive")
        result, executor = _run_and_check(action, state)
        self.assertEqual(result.status, "guard_ask_user")
        self.assertEqual(len(executor.calls), 0)

    def test_32_sensitive_target_role_visual(self):
        state = _make_valid_state()
        action = ActionSpec(action_type="tap_visual",
                            bbox_px=BBox(100, 100, 200, 150),
                            target_role="支付",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertEqual(result.status, "guard_ask_user")
        self.assertEqual(len(executor.calls), 0)

    def test_33_sensitive_text_input(self):
        state = _make_valid_state()
        action = ActionSpec(action_type="type_text",
                            text="my_password",
                            sensitive_hint="password_input")
        result, executor = _run_and_check(action, state)
        self.assertEqual(result.status, "guard_ask_user")
        self.assertEqual(len(executor.calls), 0)

    def test_34_sensitive_visual_hint(self):
        state = _make_valid_state()
        action = ActionSpec(action_type="tap_visual",
                            bbox_px=BBox(100, 100, 200, 150),
                            sensitive_hint="payment_button",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertEqual(result.status, "guard_ask_user")
        self.assertEqual(len(executor.calls), 0)

    def test_35_purchase_risk_reject(self):
        c = _make_valid_candidate(risk_category="purchase")
        state = _make_valid_state(candidate=c)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        # purchase 在 SENSITIVE_RISK_CATEGORIES 但不在 HIGH_RISK → ask_user
        self.assertEqual(result.status, "guard_ask_user")
        self.assertEqual(len(executor.calls), 0)

    def test_36_action_semantics_subscribe(self):
        c = _make_valid_candidate(action_semantics="订阅会员")
        state = _make_valid_state(candidate=c)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertEqual(result.status, "guard_ask_user")
        self.assertEqual(len(executor.calls), 0)


# ═══════════════ 类别 5：CandidateMap 不一致 ═══════════════

class TestCandidateMapMismatch(unittest.TestCase):
    """6 条：package / activity / width / height 不匹配。"""

    def test_37_package_mismatch(self):
        c = _make_valid_candidate()
        cm = make_candidate_map(candidates=[c], package="com.wrong")
        state = make_state(candidate_map=cm, package="com.test")
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

    def test_38_activity_mismatch(self):
        c = _make_valid_candidate()
        cm = make_candidate_map(candidates=[c], activity="WrongActivity")
        state = make_state(candidate_map=cm, activity="Main")
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

    def test_39_width_mismatch(self):
        c = _make_valid_candidate()
        cm = make_candidate_map(candidates=[c], width=1920, height=800)
        state = make_state(candidate_map=cm, screen_size=(1280, 800))
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

    def test_40_height_mismatch(self):
        c = _make_valid_candidate()
        cm = make_candidate_map(candidates=[c], width=1280, height=1080)
        state = make_state(candidate_map=cm, screen_size=(1280, 800))
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

    def test_41_both_size_mismatch(self):
        c = _make_valid_candidate()
        cm = make_candidate_map(candidates=[c], width=1920, height=1080)
        state = make_state(candidate_map=cm, screen_size=(1280, 800))
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

    def test_42_all_mismatch(self):
        c = _make_valid_candidate()
        cm = make_candidate_map(candidates=[c], package="com.wrong",
                                activity="Wrong", width=1920, height=1080)
        state = make_state(candidate_map=cm, package="com.test",
                           activity="Main", screen_size=(1280, 800))
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)


# ═══════════════ 正常放行 ═══════════════

class TestNormalPass(unittest.TestCase):
    """12 条：正常动作放行（executor 被调用）。"""

    def test_43_tap_candidate_ok(self):
        from harness.verifier import VerificationResult
        state = _make_valid_state()
        after = _make_valid_state()
        after_state = make_state(
            fingerprint="fp1", package="com.test", activity="Main",
            candidate_map=state.candidate_map,
            control_bar_visible=False,
            ocr_tokens={"hello", "world"},
            selected_role="c1",
        )
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1",
                            target_role="c1")
        source = MockDecisionSource([action])
        executor = FakeExecutor(after_state=after_state)
        verifier = FakeVlmVerifier([
            VerificationResult(verification="success", source="local", reason="ok"),
        ])
        result = run_action_loop(source, executor, verifier,
                                  initial_state=state, subgoal="test")
        self.assertEqual(result.status, "success")
        self.assertEqual(len(executor.calls), 1)

    def test_44_tap_visual_ok(self):
        state = _make_valid_state()
        action = ActionSpec(action_type="tap_visual",
                            bbox_px=BBox(100, 100, 200, 150),
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state)
        self.assertNotIn(result.status, ("guard_reject", "guard_ask_user", "blocked"))
        self.assertEqual(len(executor.calls), 1)

    def test_45_swipe_ok(self):
        state = _make_valid_state()
        action = ActionSpec(action_type="swipe", direction="up")
        result, executor = _run_and_check(action, state)
        self.assertNotIn(result.status, ("guard_reject", "guard_ask_user", "blocked"))
        self.assertEqual(len(executor.calls), 1)

    def test_46_remote_key_ok(self):
        state = _make_valid_state()
        action = ActionSpec(action_type="remote_key", key="ENTER")
        result, executor = _run_and_check(action, state)
        self.assertNotIn(result.status, ("guard_reject", "guard_ask_user", "blocked"))
        self.assertEqual(len(executor.calls), 1)

    def test_47_media_key_ok(self):
        state = _make_valid_state()
        action = ActionSpec(action_type="media_key", key="MEDIA_PLAY_PAUSE")
        result, executor = _run_and_check(action, state)
        self.assertNotIn(result.status, ("guard_reject", "guard_ask_user", "blocked"))
        self.assertEqual(len(executor.calls), 1)

    def test_48_type_text_ok(self):
        state = _make_valid_state()
        action = ActionSpec(action_type="type_text", text="hello")
        result, executor = _run_and_check(action, state)
        self.assertNotIn(result.status, ("guard_reject", "guard_ask_user", "blocked"))
        self.assertEqual(len(executor.calls), 1)

    def test_49_wait_ok(self):
        state = _make_valid_state()
        action = ActionSpec(action_type="wait", wait_ms=100)
        result, executor = _run_and_check(action, state)
        # wait 不进 executor，直接继续
        self.assertNotEqual(result.status, "guard_reject")

    def test_50_back_ok(self):
        state = _make_valid_state()
        action = ActionSpec(action_type="back")
        result, executor = _run_and_check(action, state)
        self.assertNotIn(result.status, ("guard_reject", "guard_ask_user", "blocked"))
        self.assertEqual(len(executor.calls), 1)

    def test_51_reveal_controls_ok(self):
        state = _make_valid_state()
        action = ActionSpec(action_type="reveal_controls")
        result, executor = _run_and_check(action, state)
        # reveal_controls 是 safe op，不进 executor
        self.assertNotEqual(result.status, "guard_reject")

    def test_52_done_ok(self):
        state = _make_valid_state()
        action = ActionSpec(action_type="done")
        result, executor = _run_and_check(action, state)
        self.assertEqual(result.status, "stopped_unverified")
        self.assertEqual(len(executor.calls), 0)

    def test_53_ask_user_ok(self):
        state = _make_valid_state()
        action = ActionSpec(action_type="ask_user")
        result, executor = _run_and_check(action, state)
        self.assertEqual(result.status, "needs_user_confirmation")
        self.assertEqual(len(executor.calls), 0)

    def test_54_tap_visual_fallback_disabled(self):
        state = _make_valid_state()
        config = ActionGuardConfig(allow_tap_visual_fallback=False)
        action = ActionSpec(action_type="tap_visual",
                            bbox_px=BBox(100, 100, 200, 150),
                            expected_screen_fingerprint="fp1")
        result, executor = _run_and_check(action, state, config=config)
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)


# ═══════════════ 综合安全断言 ═══════════════

class TestAllRejectionsZeroExecutorCalls(unittest.TestCase):
    """综合断言：所有被拒绝的样本 executor_calls 必须为 0。"""

    def _get_all_rejection_scenarios(self):
        """生成所有拒绝场景。"""
        scenarios = []
        state = _make_valid_state()

        # 未知动作类型
        for at in ["invalid", "", "123", "a" * 100, "   "]:
            scenarios.append(("unknown_action", ActionSpec(action_type=at), state))

        # 候选不可达
        scenarios.append(("no_id", ActionSpec(action_type="tap_candidate",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1"), state))
        scenarios.append(("no_map", ActionSpec(action_type="tap_candidate",
                            candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1"),
                          make_state(candidate_map=None)))
        scenarios.append(("not_found", ActionSpec(action_type="tap_candidate",
                            candidate_id="not_exist",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1"), state))
        scenarios.append(("stale_fp", ActionSpec(action_type="tap_candidate",
                            candidate_id="c1",
                            candidate_map_fingerprint="v_OLD",
                            expected_screen_fingerprint="fp1"), state))

        # 置信度
        c_low = _make_valid_candidate("c1", confidence=0.1)
        scenarios.append(("low_conf", ActionSpec(action_type="tap_candidate",
                            candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1"),
                          _make_valid_state(candidate=c_low)))

        # 敏感
        c_pay = _make_valid_candidate("c1", risk_category="payment")
        scenarios.append(("payment", ActionSpec(action_type="tap_candidate",
                            candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1"),
                          _make_valid_state(candidate=c_pay)))

        # CandidateMap 不一致
        c_ok = _make_valid_candidate()
        cm_wrong = make_candidate_map(candidates=[c_ok], package="com.wrong")
        scenarios.append(("cm_pkg", ActionSpec(action_type="tap_candidate",
                            candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1"),
                          make_state(candidate_map=cm_wrong)))

        return scenarios

    def test_all_rejections_have_zero_executor_calls(self):
        """所有被拒绝场景的 executor.calls 必须为空。"""
        scenarios = self._get_all_rejection_scenarios()
        for name, action, state in scenarios:
            result, executor = _run_and_check(action, state)
            self.assertFalse(result.ok, f"scenario '{name}' should not be ok")
            self.assertEqual(len(executor.calls), 0,
                             f"scenario '{name}' should have 0 executor calls, "
                             f"got {len(executor.calls)}")


if __name__ == "__main__":
    unittest.main()
