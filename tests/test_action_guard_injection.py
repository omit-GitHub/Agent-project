# -*- coding: utf-8 -*-
"""Action Guard Injection Tests — ≥50 条，五类异常 + 正常放行。

新接口：Guard 纯校验，risk_level 驱动 action_loop 流转：
  - risk_level=high → guard_reject（executor 不调用）
  - risk_level=medium → needs_user_confirmation（executor 不调用）
  - requires_refinement=True → needs_refinement（recovery 调 executor）

被拒绝（guard_reject/needs_user_confirmation）样本 executor_calls 必须为 0。

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
    run_action_loop, BBox, GuardDecision,
)
from harness.action_guard import validate_action
from harness.types import Candidate, CandidateMap
from tests.mocks import (
    MockDecisionSource, FakeExecutor, FakeVlmVerifier,
    make_candidate, make_candidate_map, make_state,
)


def _run_and_check(action, state, subgoal="test", guard=None, config=None,
                   recovery_budget=0):
    """运行 action_loop 并返回 (result, executor)。默认关闭恢复以验证 Guard 拒绝。"""
    source = MockDecisionSource([action])
    executor = FakeExecutor(after_state=state)
    verifier = FakeVlmVerifier([])
    result = run_action_loop(
        source, executor, verifier,
        initial_state=state, subgoal=subgoal,
        guard=guard, config=config,
        recovery_budget=recovery_budget,
    )
    return result, executor


def _direct_guard_check(action, state, config=None):
    """直接调用 Guard 返回 GuardDecision。"""
    return validate_action(
        action, state, "test",
        set(),
        config=config or ActionGuardConfig(),
    )


def _make_valid_candidate(cid="c1", **kwargs):
    defaults = dict(confidence=0.9, clickable_likelihood=0.9,
                    source="ocr", kind="button")
    defaults.update(kwargs)
    return make_candidate(cid, **defaults)


def _make_valid_state(candidate=None, **kwargs):
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
    def test_01_invalid(self):
        r, ex = _run_and_check(ActionSpec(action_type="invalid_action"), _make_valid_state())
        self.assertEqual(r.status, "guard_reject")
        self.assertEqual(len(ex.calls), 0)

    def test_02_empty(self):
        r, ex = _run_and_check(ActionSpec(action_type=""), _make_valid_state())
        self.assertEqual(r.status, "guard_reject")
        self.assertEqual(len(ex.calls), 0)

    def test_03_numeric(self):
        r, ex = _run_and_check(ActionSpec(action_type="12345"), _make_valid_state())
        self.assertEqual(r.status, "guard_reject")
        self.assertEqual(len(ex.calls), 0)

    def test_04_long(self):
        r, ex = _run_and_check(ActionSpec(action_type="a" * 200), _make_valid_state())
        self.assertEqual(r.status, "guard_reject")
        self.assertEqual(len(ex.calls), 0)

    def test_05_spaces(self):
        r, ex = _run_and_check(ActionSpec(action_type="   "), _make_valid_state())
        self.assertEqual(r.status, "guard_reject")
        self.assertEqual(len(ex.calls), 0)


# ═══════════════ 类别 2：候选不可达 ═══════════════

class TestCandidateUnreachable(unittest.TestCase):
    def test_06_missing_id(self):
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"), _make_valid_state())
        self.assertEqual(r.status, "guard_reject")
        self.assertEqual(len(ex.calls), 0)

    def test_07_no_map(self):
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            make_state(candidate_map=None))
        self.assertEqual(r.status, "guard_reject")
        self.assertEqual(len(ex.calls), 0)

    def test_08_not_found(self):
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="not_exist",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"), _make_valid_state())
        self.assertEqual(r.status, "guard_reject")
        self.assertEqual(len(ex.calls), 0)

    def test_09_stale_fp(self):
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v_OLD",
                       expected_screen_fingerprint="fp1"), _make_valid_state())
        self.assertEqual(r.status, "guard_reject")
        self.assertEqual(len(ex.calls), 0)

    def test_10_page_mismatch(self):
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp_WRONG"), _make_valid_state())
        self.assertEqual(r.status, "guard_reject")
        self.assertEqual(len(ex.calls), 0)

    def test_11_bbox_out_right(self):
        c = _make_valid_candidate(bbox=BBox(1200, 100, 1400, 200))
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(candidate=c))
        self.assertEqual(r.status, "guard_reject")
        self.assertEqual(len(ex.calls), 0)

    def test_12_bbox_out_bottom(self):
        c = _make_valid_candidate(bbox=BBox(100, 750, 200, 900))
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(candidate=c))
        self.assertEqual(r.status, "guard_reject")
        self.assertEqual(len(ex.calls), 0)

    def test_13_bbox_negative(self):
        with self.assertRaises(ValueError):
            BBox(-50, 100, 50, 200)

    def test_14_bbox_negative_y(self):
        with self.assertRaises(ValueError):
            BBox(100, -50, 200, 50)

    def test_15_previously_failed(self):
        guard = ActionGuard()
        guard.record_failure("fp1", "c1")
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(), guard=guard)
        self.assertEqual(r.status, "guard_reject")
        self.assertEqual(len(ex.calls), 0)


# ═══════════════ 类别 3：置信度不足（requires_refinement）═══════════════

class TestLowConfidence(unittest.TestCase):
    """requires_refinement → recovery；recovery_budget=0 → needs_refinement。"""

    def test_16_low_confidence(self):
        c = _make_valid_candidate(confidence=0.1)
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(candidate=c))
        self.assertEqual(r.status, "needs_refinement")

    def test_17_low_clickable(self):
        c = _make_valid_candidate(clickable_likelihood=0.1)
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(candidate=c))
        self.assertEqual(r.status, "needs_refinement")

    def test_18_both_low(self):
        c = _make_valid_candidate(confidence=0.1, clickable_likelihood=0.1)
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(candidate=c))
        self.assertEqual(r.status, "needs_refinement")

    def test_19_ocr_only_not_allowed(self):
        c = _make_valid_candidate(source="ocr", kind="")
        config = ActionGuardConfig(allow_ocr_only_tap=False)
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(candidate=c), config=config)
        self.assertEqual(r.status, "needs_refinement")

    def test_20_ocr_only_allowed(self):
        c = _make_valid_candidate(source="ocr", kind="")
        config = ActionGuardConfig(allow_ocr_only_tap=True)
        g = _direct_guard_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(candidate=c), config=config)
        self.assertTrue(g.allowed)
        self.assertEqual(g.risk_level, "low")
        self.assertFalse(g.requires_refinement)

    def test_21_confidence_zero(self):
        c = _make_valid_candidate(confidence=0.0)
        g = _direct_guard_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(candidate=c))
        self.assertFalse(g.allowed)
        self.assertEqual(g.error_code, "LOW_CONFIDENCE")
        self.assertTrue(g.requires_refinement)

    def test_22_clickable_zero(self):
        c = _make_valid_candidate(clickable_likelihood=0.0)
        g = _direct_guard_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(candidate=c))
        self.assertFalse(g.allowed)
        self.assertEqual(g.error_code, "LOW_CLICKABLE_LIKELIHOOD")
        self.assertTrue(g.requires_refinement)


# ═══════════════ 类别 4：敏感操作（risk_level 驱动）═══════════════

class TestSensitiveOperations(unittest.TestCase):
    """risk_level=high → guard_reject；medium → needs_user_confirmation。"""

    def test_23_payment_high(self):
        c = _make_valid_candidate(risk_category="payment")
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(candidate=c))
        self.assertEqual(r.status, "guard_reject")
        self.assertEqual(len(ex.calls), 0)

    def test_24_delete_high(self):
        c = _make_valid_candidate(risk_category="delete")
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(candidate=c))
        self.assertEqual(r.status, "guard_reject")
        self.assertEqual(len(ex.calls), 0)

    def test_25_logout_medium(self):
        c = _make_valid_candidate(risk_category="logout")
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(candidate=c))
        self.assertEqual(r.status, "needs_user_confirmation")
        self.assertEqual(len(ex.calls), 0)

    def test_26_password_medium(self):
        c = _make_valid_candidate(risk_category="password")
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(candidate=c))
        self.assertEqual(r.status, "needs_user_confirmation")
        self.assertEqual(len(ex.calls), 0)

    def test_27_send_medium(self):
        c = _make_valid_candidate(risk_category="send")
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(candidate=c))
        self.assertEqual(r.status, "needs_user_confirmation")
        self.assertEqual(len(ex.calls), 0)

    def test_28_sensitive_category_medium(self):
        c = _make_valid_candidate(sensitive_category="confirm_payment")
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(candidate=c))
        self.assertEqual(r.status, "needs_user_confirmation")
        self.assertEqual(len(ex.calls), 0)

    def test_29_action_semantics_payment(self):
        c = _make_valid_candidate(action_semantics="确认支付")
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(candidate=c))
        self.assertEqual(r.status, "needs_user_confirmation")
        self.assertEqual(len(ex.calls), 0)

    def test_30_action_semantics_delete(self):
        c = _make_valid_candidate(action_semantics="删除文件")
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(candidate=c))
        self.assertEqual(r.status, "needs_user_confirmation")
        self.assertEqual(len(ex.calls), 0)

    def test_31_sensitive_hint(self):
        c = _make_valid_candidate()
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1",
                       sensitive_hint="this is sensitive"),
            _make_valid_state(candidate=c))
        self.assertEqual(r.status, "needs_user_confirmation")
        self.assertEqual(len(ex.calls), 0)

    def test_32_visual_sensitive_role(self):
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_visual",
                       bbox_px=BBox(100, 100, 200, 150),
                       target_role="支付",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state())
        self.assertEqual(r.status, "needs_user_confirmation")
        self.assertEqual(len(ex.calls), 0)

    def test_33_text_sensitive(self):
        r, ex = _run_and_check(
            ActionSpec(action_type="type_text", text="pw",
                       sensitive_hint="password_input"),
            _make_valid_state())
        self.assertEqual(r.status, "needs_user_confirmation")
        self.assertEqual(len(ex.calls), 0)

    def test_34_visual_sensitive_hint(self):
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_visual",
                       bbox_px=BBox(100, 100, 200, 150),
                       sensitive_hint="payment_button",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state())
        self.assertEqual(r.status, "needs_user_confirmation")
        self.assertEqual(len(ex.calls), 0)

    def test_35_purchase_medium(self):
        c = _make_valid_candidate(risk_category="purchase")
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(candidate=c))
        self.assertEqual(r.status, "needs_user_confirmation")
        self.assertEqual(len(ex.calls), 0)

    def test_36_subscribe_semantics(self):
        c = _make_valid_candidate(action_semantics="订阅会员")
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(candidate=c))
        self.assertEqual(r.status, "needs_user_confirmation")
        self.assertEqual(len(ex.calls), 0)


# ═══════════════ 类别 5：CandidateMap 不一致 ═══════════════

class TestCandidateMapMismatch(unittest.TestCase):
    def test_37_package(self):
        c = _make_valid_candidate()
        cm = make_candidate_map(candidates=[c], package="com.wrong")
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            make_state(candidate_map=cm, package="com.test"))
        self.assertEqual(r.status, "guard_reject")
        self.assertEqual(len(ex.calls), 0)

    def test_38_activity(self):
        c = _make_valid_candidate()
        cm = make_candidate_map(candidates=[c], activity="Wrong")
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            make_state(candidate_map=cm, activity="Main"))
        self.assertEqual(r.status, "guard_reject")
        self.assertEqual(len(ex.calls), 0)

    def test_39_width(self):
        c = _make_valid_candidate()
        cm = make_candidate_map(candidates=[c], width=1920, height=800)
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            make_state(candidate_map=cm, screen_size=(1280, 800)))
        self.assertEqual(r.status, "guard_reject")
        self.assertEqual(len(ex.calls), 0)

    def test_40_height(self):
        c = _make_valid_candidate()
        cm = make_candidate_map(candidates=[c], width=1280, height=1080)
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            make_state(candidate_map=cm, screen_size=(1280, 800)))
        self.assertEqual(r.status, "guard_reject")
        self.assertEqual(len(ex.calls), 0)

    def test_41_both_size(self):
        c = _make_valid_candidate()
        cm = make_candidate_map(candidates=[c], width=1920, height=1080)
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            make_state(candidate_map=cm, screen_size=(1280, 800)))
        self.assertEqual(r.status, "guard_reject")
        self.assertEqual(len(ex.calls), 0)

    def test_42_all(self):
        c = _make_valid_candidate()
        cm = make_candidate_map(candidates=[c], package="com.wrong",
                                activity="Wrong", width=1920, height=1080)
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            make_state(candidate_map=cm, package="com.test",
                       activity="Main", screen_size=(1280, 800)))
        self.assertEqual(r.status, "guard_reject")
        self.assertEqual(len(ex.calls), 0)


# ═══════════════ 正常放行 ═══════════════

class TestNormalPass(unittest.TestCase):
    def test_43_tap_candidate_ok(self):
        from harness.verifier import VerificationResult
        state = _make_valid_state()
        after = make_state(fingerprint="fp1", package="com.test", activity="Main",
                           candidate_map=state.candidate_map, control_bar_visible=False,
                           ocr_tokens={"hello", "world"}, selected_role="c1")
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1", target_role="c1"),
            state)
        # Guard passes → executor called → verifier → not_yet → timeout
        self.assertNotIn(r.status, ("guard_reject", "needs_user_confirmation"))
        self.assertEqual(len(ex.calls), 1)

    def test_44_tap_visual_ok(self):
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_visual",
                       bbox_px=BBox(100, 100, 200, 150),
                       expected_screen_fingerprint="fp1"),
            _make_valid_state())
        self.assertNotIn(r.status, ("guard_reject", "needs_user_confirmation", "blocked"))
        self.assertEqual(len(ex.calls), 1)

    def test_45_swipe_ok(self):
        r, ex = _run_and_check(
            ActionSpec(action_type="swipe", direction="up"), _make_valid_state())
        self.assertEqual(len(ex.calls), 1)

    def test_46_remote_key_ok(self):
        r, ex = _run_and_check(
            ActionSpec(action_type="remote_key", key="ENTER"), _make_valid_state())
        self.assertEqual(len(ex.calls), 1)

    def test_47_media_key_ok(self):
        r, ex = _run_and_check(
            ActionSpec(action_type="media_key", key="MEDIA_PLAY_PAUSE"), _make_valid_state())
        self.assertEqual(len(ex.calls), 1)

    def test_48_type_text_ok(self):
        r, ex = _run_and_check(
            ActionSpec(action_type="type_text", text="hello"), _make_valid_state())
        self.assertEqual(len(ex.calls), 1)

    def test_49_wait_ok(self):
        r, ex = _run_and_check(
            ActionSpec(action_type="wait", wait_ms=100), _make_valid_state())
        self.assertNotEqual(r.status, "guard_reject")

    def test_50_back_ok(self):
        r, ex = _run_and_check(ActionSpec(action_type="back"), _make_valid_state())
        self.assertEqual(len(ex.calls), 1)

    def test_51_reveal_controls_ok(self):
        r, ex = _run_and_check(
            ActionSpec(action_type="reveal_controls"), _make_valid_state())
        self.assertNotEqual(r.status, "guard_reject")

    def test_52_done(self):
        r, ex = _run_and_check(ActionSpec(action_type="done"), _make_valid_state())
        self.assertEqual(r.status, "stopped_unverified")
        self.assertEqual(len(ex.calls), 0)

    def test_53_ask_user(self):
        r, ex = _run_and_check(ActionSpec(action_type="ask_user"), _make_valid_state())
        self.assertEqual(r.status, "needs_user_confirmation")
        self.assertEqual(len(ex.calls), 0)

    def test_54_tap_visual_disabled(self):
        config = ActionGuardConfig(allow_tap_visual_fallback=False)
        r, ex = _run_and_check(
            ActionSpec(action_type="tap_visual",
                       bbox_px=BBox(100, 100, 200, 150),
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(), config=config)
        self.assertEqual(r.status, "guard_reject")
        self.assertEqual(len(ex.calls), 0)


# ═══════════════ Guard 直接校验 + risk_level 断言 ═══════════════

class TestGuardRiskLevel(unittest.TestCase):
    """直接测试 Guard 的 risk_level 输出。"""

    def test_55_unknown_action_high_risk(self):
        g = _direct_guard_check(ActionSpec(action_type="foo"), _make_valid_state())
        self.assertFalse(g.allowed)
        self.assertEqual(g.risk_level, "high")
        self.assertEqual(g.error_code, "UNKNOWN_ACTION")

    def test_56_payment_high_risk(self):
        c = _make_valid_candidate(risk_category="payment")
        g = _direct_guard_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(candidate=c))
        self.assertFalse(g.allowed)
        self.assertEqual(g.risk_level, "high")
        self.assertEqual(g.error_code, "SENSITIVE_TARGET")

    def test_57_logout_medium_risk(self):
        c = _make_valid_candidate(risk_category="logout")
        g = _direct_guard_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(candidate=c))
        self.assertFalse(g.allowed)
        self.assertEqual(g.risk_level, "medium")

    def test_58_low_confidence_requires_refinement(self):
        c = _make_valid_candidate(confidence=0.1)
        g = _direct_guard_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state(candidate=c))
        self.assertFalse(g.allowed)
        self.assertEqual(g.risk_level, "low")
        self.assertTrue(g.requires_refinement)

    def test_59_normal_candidate_low_risk(self):
        g = _direct_guard_check(
            ActionSpec(action_type="tap_candidate", candidate_id="c1",
                       candidate_map_fingerprint="v1",
                       expected_screen_fingerprint="fp1"),
            _make_valid_state())
        self.assertTrue(g.allowed)
        self.assertEqual(g.risk_level, "low")
        self.assertFalse(g.requires_refinement)


# ═══════════════ 综合安全断言 ═══════════════

class TestAllRejectionsZeroExecutorCalls(unittest.TestCase):
    """所有被拒绝（guard_reject/needs_user_confirmation）样本 executor_calls == 0。"""

    def test_60_all_rejections_zero_calls(self):
        scenarios = []
        state = _make_valid_state()

        # 未知动作类型
        for at in ["invalid", "", "123"]:
            scenarios.append(("unknown", ActionSpec(action_type=at), state, None, None))

        # 候选不可达
        scenarios.append(("no_map",
                          ActionSpec(action_type="tap_candidate", candidate_id="c1",
                                     candidate_map_fingerprint="v1",
                                     expected_screen_fingerprint="fp1"),
                          make_state(candidate_map=None), None, None))
        scenarios.append(("not_found",
                          ActionSpec(action_type="tap_candidate", candidate_id="not_exist",
                                     candidate_map_fingerprint="v1",
                                     expected_screen_fingerprint="fp1"),
                          state, None, None))

        # 高敏感
        for rc in ["payment", "delete"]:
            c = _make_valid_candidate("c1", risk_category=rc)
            scenarios.append((f"high_{rc}",
                              ActionSpec(action_type="tap_candidate", candidate_id="c1",
                                         candidate_map_fingerprint="v1",
                                         expected_screen_fingerprint="fp1"),
                              _make_valid_state(candidate=c), None, None))

        # 中敏感
        for rc in ["logout", "password"]:
            c = _make_valid_candidate("c1", risk_category=rc)
            scenarios.append((f"medium_{rc}",
                              ActionSpec(action_type="tap_candidate", candidate_id="c1",
                                         candidate_map_fingerprint="v1",
                                         expected_screen_fingerprint="fp1"),
                              _make_valid_state(candidate=c), None, None))

        # CandidateMap 不一致
        c_ok = _make_valid_candidate()
        cm_wrong = make_candidate_map(candidates=[c_ok], package="com.wrong")
        scenarios.append(("cm_pkg",
                          ActionSpec(action_type="tap_candidate", candidate_id="c1",
                                     candidate_map_fingerprint="v1",
                                     expected_screen_fingerprint="fp1"),
                          make_state(candidate_map=cm_wrong), None, None))

        for name, action, st, guard, config in scenarios:
            r, ex = _run_and_check(action, st, guard=guard, config=config)
            self.assertFalse(r.ok, f"scenario '{name}' should not be ok")
            if r.status in ("guard_reject", "needs_user_confirmation"):
                self.assertEqual(len(ex.calls), 0,
                                 f"scenario '{name}' rejected but executor called {len(ex.calls)} times")


if __name__ == "__main__":
    unittest.main()
