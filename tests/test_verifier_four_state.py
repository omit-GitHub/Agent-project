# -*- coding: utf-8 -*-
"""Verifier Four-State Tests — 四态、fallback、unknown 不得成功。

覆盖：
  - success: 5 条路径（package/activity/control_bar/role/OCR）
  - not_yet: 无目标信号、layout-only 变化
  - failed: VLM 显式返回 failed
  - unknown: VLM 不可用 + 观测耗尽
  - fallback: consecutive not_yet → VLM 被调用
  - unknown 不得成功: action_loop 中 unknown → 不 ok=True
  - VLM unknown 后允许有限重观察
  - expected_package/activity 无转移 → 不 success

运行：
  cd harness-framework
  python -m unittest tests.test_verifier_four_state -v
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
    ActionSpec, run_action_loop,
)
from harness.verifier import (
    LocalVerifier, VlmVerifier, LayeredVerifier,
    VerificationResult, VerificationStatus, VerificationSource,
)
from harness.action_guard import ActionGuard
from tests.mocks import (
    MockDecisionSource, FakeExecutor, FakeVlmVerifier,
    make_state, make_candidate, make_candidate_map,
)


# ═══════════════ Success 路径 ═══════════════

class TestVerifierSuccess(unittest.TestCase):
    """5 条 success 路径。"""

    def setUp(self):
        self.v = LocalVerifier()

    def test_01_expected_package_transition(self):
        """expected_package: before ≠ expected → after == expected → success。"""
        before = make_state(fingerprint="fp1", package="com.a", activity="A")
        after = make_state(fingerprint="fp2", package="com.b", activity="A")
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            expected_package="com.b")
        r = self.v.verify(before, after, action)
        self.assertEqual(r.verification, VerificationStatus.success)
        self.assertEqual(r.source, VerificationSource.local)

    def test_02_expected_activity_transition(self):
        """expected_activity: before ≠ expected → after == expected → success。"""
        before = make_state(fingerprint="fp1", package="com.a", activity="A")
        after = make_state(fingerprint="fp2", package="com.a", activity="B")
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            expected_activity="B")
        r = self.v.verify(before, after, action)
        self.assertEqual(r.verification, VerificationStatus.success)

    def test_03_control_bar_transition(self):
        """control_bar: false → true → success。"""
        before = make_state(fingerprint="fp1", control_bar_visible=False)
        after = make_state(fingerprint="fp2", control_bar_visible=True)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1")
        r = self.v.verify(before, after, action)
        self.assertEqual(r.verification, VerificationStatus.success)

    def test_04_target_role_selected(self):
        """target_role → selected_role match → success。"""
        before = make_state(fingerprint="fp1", selected_role=None)
        after = make_state(fingerprint="fp2", selected_role="play_button")
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            target_role="play_button")
        r = self.v.verify(before, after, action)
        self.assertEqual(r.verification, VerificationStatus.success)

    def test_05_target_role_ocr_token(self):
        """target_role → new OCR token → success。"""
        before = make_state(fingerprint="fp1", ocr_tokens={"hello"})
        after = make_state(fingerprint="fp2", ocr_tokens={"hello", "1.5x"})
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            target_role="1.5x")
        r = self.v.verify(before, after, action)
        self.assertEqual(r.verification, VerificationStatus.success)


# ═══════════════ not_yet ═══════════════

class TestVerifierNotYet(unittest.TestCase):
    """not_yet: 无目标信号 / layout-only 变化 / expected 无转移。"""

    def setUp(self):
        self.v = LocalVerifier()

    def test_06_no_target_signal(self):
        """无任何目标信号 → not_yet。"""
        before = make_state(fingerprint="fp1", package="com.a", activity="A",
                            ocr_tokens={"a"})
        after = make_state(fingerprint="fp2", package="com.a", activity="A",
                           ocr_tokens={"a"})
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1")
        r = self.v.verify(before, after, action)
        self.assertEqual(r.verification, VerificationStatus.not_yet)

    def test_07_layout_only_change(self):
        """layout-only 变化（fingerprint 不同，其他不变）→ not_yet。"""
        before = make_state(fingerprint="fp1", package="com.a", activity="A",
                            control_bar_visible=False, ocr_tokens={"a"})
        after = make_state(fingerprint="fp9", package="com.a", activity="A",
                           control_bar_visible=False, ocr_tokens={"a", "random"})
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1")
        r = self.v.verify(before, after, action)
        self.assertEqual(r.verification, VerificationStatus.not_yet)

    def test_08_expected_package_no_transition(self):
        """before.package == expected_package → 不 success（无转移）。"""
        before = make_state(fingerprint="fp1", package="com.b", activity="A")
        after = make_state(fingerprint="fp2", package="com.b", activity="A")
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            expected_package="com.b")
        r = self.v.verify(before, after, action)
        self.assertNotEqual(r.verification, VerificationStatus.success)
        self.assertEqual(r.verification, VerificationStatus.not_yet)

    def test_09_expected_activity_no_transition(self):
        """before.activity == expected_activity → 不 success（无转移）。"""
        before = make_state(fingerprint="fp1", package="com.a", activity="B")
        after = make_state(fingerprint="fp2", package="com.a", activity="B")
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            expected_activity="B")
        r = self.v.verify(before, after, action)
        self.assertNotEqual(r.verification, VerificationStatus.success)
        self.assertEqual(r.verification, VerificationStatus.not_yet)

    def test_10_non_target_ocr_change(self):
        """非目标 OCR token 出现 → not_yet（不是目标）。"""
        before = make_state(fingerprint="fp1", ocr_tokens={"a"})
        after = make_state(fingerprint="fp2", ocr_tokens={"a", "unrelated"})
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            target_role="target_text")
        r = self.v.verify(before, after, action)
        self.assertEqual(r.verification, VerificationStatus.not_yet)

    def test_11_control_bar_already_visible(self):
        """control_bar 已经可见 → 不触发 false→true → not_yet。"""
        before = make_state(fingerprint="fp1", control_bar_visible=True)
        after = make_state(fingerprint="fp2", control_bar_visible=True)
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1")
        r = self.v.verify(before, after, action)
        self.assertEqual(r.verification, VerificationStatus.not_yet)


# ═══════════════ failed ═══════════════

class TestVerifierFailed(unittest.TestCase):
    """failed: VLM 显式返回 failed。"""

    def test_12_vlm_explicit_failed(self):
        """VLM callable 返回 failed → verification=failed。"""
        def vlm_fn(before, after, action):
            return VerificationResult(
                verification=VerificationStatus.failed,
                source=VerificationSource.vlm,
                reason="VLM says: wrong screen",
            )

        v = VlmVerifier(vlm_fn)
        before = make_state(fingerprint="fp1")
        after = make_state(fingerprint="fp2")
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1")
        r = v.verify(before, after, action)
        self.assertEqual(r.verification, VerificationStatus.failed)
        self.assertEqual(r.source, VerificationSource.vlm)

    def test_13_vlm_exception_returns_unknown(self):
        """VLM callable 抛异常 → unknown。"""
        def vlm_fn(before, after, action):
            raise RuntimeError("network error")

        v = VlmVerifier(vlm_fn)
        before = make_state(fingerprint="fp1")
        after = make_state(fingerprint="fp2")
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1")
        r = v.verify(before, after, action)
        self.assertEqual(r.verification, VerificationStatus.unknown)

    def test_14_vlm_not_callable(self):
        """VLM callable=None → unknown。"""
        v = VlmVerifier(None)
        before = make_state(fingerprint="fp1")
        after = make_state(fingerprint="fp2")
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1")
        r = v.verify(before, after, action)
        self.assertEqual(r.verification, VerificationStatus.unknown)


# ═══════════════ unknown ═══════════════

class TestVerifierUnknown(unittest.TestCase):
    """unknown: VLM 不可用 + 观测耗尽 → unknown，不得视为 success。"""

    def test_15_unknown_not_success(self):
        """unknown 不得视为 success。"""
        r = VerificationResult(
            verification=VerificationStatus.unknown,
            source=VerificationSource.vlm,
            reason="uncertain",
        )
        self.assertNotEqual(r.verification, VerificationStatus.success)

    def test_16_vlm_unavailable_exhausted(self):
        """VLM 不可用 + 本地观测耗尽 → unknown。"""
        v = LayeredVerifier(vlm_callable=None, max_local_observations=2,
                            max_vlm_unknown=0)
        before = make_state(fingerprint="fp1", package="com.a")
        after = make_state(fingerprint="fp2", package="com.a")
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1")

        # 多次 not_yet → 最终耗尽 → unknown
        for _ in range(2):
            r = v.verify(before, after, action)
            self.assertEqual(r.verification, VerificationStatus.not_yet)

        r = v.verify(before, after, action)
        self.assertEqual(r.verification, VerificationStatus.unknown)

    def test_17_unknown_in_action_loop_not_ok(self):
        """action_loop 中 verifier 持续 unknown → 不 ok=True。"""
        candidate = make_candidate("c1")
        cm = make_candidate_map(candidates=[candidate])
        state = make_state(fingerprint="fp1", candidate_map=cm)
        after = make_state(fingerprint="fp2", candidate_map=cm)

        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        source = MockDecisionSource([action, action, action, action])
        executor = FakeExecutor(after_state=after)
        # verifier 持续返回 unknown
        verifier = FakeVlmVerifier([
            VerificationResult(verification="unknown", source="vlm", reason="uncertain"),
            VerificationResult(verification="unknown", source="vlm", reason="uncertain"),
            VerificationResult(verification="unknown", source="vlm", reason="uncertain"),
            VerificationResult(verification="unknown", source="vlm", reason="uncertain"),
        ])
        result = run_action_loop(
            source, executor, verifier,
            initial_state=state, subgoal="test",
            recovery_budget=2, max_decision_calls=4,
        )
        self.assertFalse(result.ok)
        self.assertNotEqual(result.status, "success")


# ═══════════════ Fallback ═══════════════

class TestVerifierFallback(unittest.TestCase):
    """fallback: consecutive not_yet → VLM 被调用。"""

    def test_18_fallback_triggers_vlm(self):
        """连续 not_yet 达 max_local_observations → VLM callable 被调用。"""
        call_count = [0]

        def vlm_fn(before, after, action):
            call_count[0] += 1
            return VerificationResult(
                verification=VerificationStatus.success,
                source=VerificationSource.vlm,
                reason="VLM says success",
            )

        v = LayeredVerifier(vlm_callable=vlm_fn, max_local_observations=3)
        before = make_state(fingerprint="fp1", package="com.a")
        after = make_state(fingerprint="fp2", package="com.a")
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1")

        # 前 2 次 → not_yet（未达阈值）
        r1 = v.verify(before, after, action)
        self.assertEqual(r1.verification, VerificationStatus.not_yet)
        r2 = v.verify(before, after, action)
        self.assertEqual(r2.verification, VerificationStatus.not_yet)
        self.assertEqual(call_count[0], 0)

        # 第 3 次 → 达到阈值 → 调 VLM → success
        r3 = v.verify(before, after, action)
        self.assertEqual(r3.verification, VerificationStatus.success)
        self.assertEqual(call_count[0], 1)
        self.assertEqual(r3.source, VerificationSource.vlm)

    def test_19_vlm_unknown_then_reobserve(self):
        """VLM 第 1 次返回 unknown → 返回 not_yet 允许继续观察。"""
        def vlm_fn(before, after, action):
            return VerificationResult(
                verification=VerificationStatus.unknown,
                source=VerificationSource.vlm,
                reason="VLM uncertain",
            )

        v = LayeredVerifier(vlm_callable=vlm_fn, max_local_observations=2,
                            max_vlm_unknown=1)
        before = make_state(fingerprint="fp1")
        after = make_state(fingerprint="fp2")
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1")

        # 第 1 次 not_yet
        r1 = v.verify(before, after, action)
        self.assertEqual(r1.verification, VerificationStatus.not_yet)
        # 第 2 次 → 达阈值 → VLM unknown → 返回 not_yet（允许继续观察）
        r2 = v.verify(before, after, action)
        self.assertEqual(r2.verification, VerificationStatus.not_yet)
        self.assertEqual(r2.source, VerificationSource.vlm)

    def test_20_vlm_unknown_exceeded_returns_unknown(self):
        """VLM unknown 超限 → 返回 unknown。"""
        def vlm_fn(before, after, action):
            return VerificationResult(
                verification=VerificationStatus.unknown,
                source=VerificationSource.vlm,
                reason="VLM uncertain",
            )

        v = LayeredVerifier(vlm_callable=vlm_fn, max_local_observations=2,
                            max_vlm_unknown=1)
        before = make_state(fingerprint="fp1")
        after = make_state(fingerprint="fp2")
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1")

        # 达到阈值后 VLM 返回 unknown → not_yet
        r1 = v.verify(before, after, action)  # not_yet (count=1)
        r2 = v.verify(before, after, action)  # not_yet (count=2) → VLM → unknown → not_yet
        self.assertEqual(r2.verification, VerificationStatus.not_yet)
        # 继续 not_yet → 再次达阈值 → VLM 第 2 次 unknown → 超限 → unknown
        r3 = v.verify(before, after, action)  # not_yet (count=3) → VLM → unknown → exceeded
        self.assertEqual(r3.verification, VerificationStatus.unknown)

    def test_21_success_resets_counter(self):
        """success 后重置计数器。"""
        v = LayeredVerifier(max_local_observations=2)
        before = make_state(fingerprint="fp1", package="com.a")
        after_ok = make_state(fingerprint="fp2", package="com.b")
        after_ny = make_state(fingerprint="fp3", package="com.a")
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            expected_package="com.b")

        # 1 次 not_yet
        r1 = v.verify(before, after_ny, action)
        self.assertEqual(r1.verification, VerificationStatus.not_yet)

        # 1 次 success → 重置
        r2 = v.verify(before, after_ok, action)
        self.assertEqual(r2.verification, VerificationStatus.success)

        # 计数器重置后，需要重新积累 not_yet
        r3 = v.verify(before, after_ny, action)
        self.assertEqual(r3.verification, VerificationStatus.not_yet)
        # 只有 1 次 not_yet，不应触发 VLM
        self.assertEqual(v._consecutive_not_yet, 1)


# ═══════════════ 综合断言 ═══════════════

class TestVerifierIntegration(unittest.TestCase):
    """综合集成测试。"""

    def test_22_layered_with_no_vlm_never_success_on_not_yet(self):
        """无 VLM 时，持续 not_yet 最终变 unknown，永远不 success。"""
        v = LayeredVerifier(vlm_callable=None, max_local_observations=2,
                            max_vlm_unknown=0)
        before = make_state(fingerprint="fp1")
        after = make_state(fingerprint="fp2")
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1")

        seen_statuses = set()
        for _ in range(10):
            r = v.verify(before, after, action)
            seen_statuses.add(r.verification)

        self.assertIn(VerificationStatus.not_yet, seen_statuses)
        self.assertIn(VerificationStatus.unknown, seen_statuses)
        self.assertNotIn(VerificationStatus.success, seen_statuses)

    def test_23_vlm_failed_stops_loop(self):
        """VLM 返回 failed → action_loop 应停止（非 success）。"""
        candidate = make_candidate("c1")
        cm = make_candidate_map(candidates=[candidate])
        state = make_state(fingerprint="fp1", candidate_map=cm)
        after = make_state(fingerprint="fp2", candidate_map=cm)

        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        source = MockDecisionSource([action, action])
        executor = FakeExecutor(after_state=after)
        verifier = FakeVlmVerifier([
            VerificationResult(verification="failed", source="vlm", reason="wrong"),
        ])
        result = run_action_loop(
            source, executor, verifier,
            initial_state=state, subgoal="test",
            recovery_budget=0,
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.status, "failed")


if __name__ == "__main__":
    unittest.main()
