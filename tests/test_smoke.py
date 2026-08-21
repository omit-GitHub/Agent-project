# -*- coding: utf-8 -*-
"""Harness smoke tests。

验证 Harness 三模块 + action_loop 的纯 Python 可导入 / 可测试能力，
不依赖真实设备 / VLM / ADB / OCR。

运行：
  cd harness-framework
  python -m unittest tests.test_smoke -v
"""
import os
import sys
import unittest

# 确保能导入 harness 包
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
_SRC_ROOT = os.path.join(_PROJECT_ROOT, "src")
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)


# ─────────────── 1. Import 检查 ───────────────

class TestImports(unittest.TestCase):

    def test_modules_import_cleanly(self):
        """所有 harness 模块可 import。"""
        from harness import action_guard
        from harness import verifier
        from harness import control_revealer
        from harness import action_loop
        from harness import schemas
        from harness import types

        from harness import (
            BBox, Candidate, CandidateMap,
            ActionSpec, UiState, ActionResult, ActionLoopResult,
            VerificationStatus, VerificationSource, VerificationResult,
            validate_action, tap_to_pixel, InvalidBBoxError,
            ActionGuard, ActionGuardConfig, GuardDecision,
            run_action_loop, DecisionSource, ActionExecutor, StateVerifier,
        )
        self.assertTrue(callable(validate_action))
        self.assertTrue(callable(run_action_loop))
        self.assertEqual(VerificationStatus.success.value, "success")
        self.assertEqual(VerificationSource.local.value, "local")


# ─────────────── 2. FakeExecutor 基础 ───────────────

class TestFakeExecutor(unittest.TestCase):

    def test_fake_executor_no_device(self):
        """FakeExecutor 无设备环境下可实例化并记录调用；after_state 是新对象。"""
        from tests.mocks import FakeExecutor, make_state
        from harness.schemas import ActionSpec

        state = make_state(fingerprint="fp1")
        after = make_state(fingerprint="fp2")
        executor = FakeExecutor(after_state=after)

        action = ActionSpec(action_type="tap_candidate", candidate_id="c1")
        result = executor.execute(action, state)

        self.assertTrue(result.ok)
        self.assertEqual(len(executor.calls), 1)
        self.assertIs(executor.calls[0], action)
        self.assertIsNot(result.after_state, state)
        self.assertEqual(result.after_state.fingerprint, "fp2")


# ─────────────── 3. run_action_loop 完整 happy path ───────────────

class TestRunActionLoop(unittest.TestCase):

    def test_action_loop_tap_candidate_success(self):
        """MockDecisionSource + FakeExecutor + FakeVlmVerifier → ok=True, status=success。"""
        from tests.mocks import (
            MockDecisionSource, FakeExecutor, FakeVlmVerifier,
            make_state, make_candidate, make_candidate_map,
        )
        from harness.schemas import ActionSpec
        from harness.verifier import VerificationResult

        candidate = make_candidate("c1")
        candidate_map = make_candidate_map(candidates=[candidate], screen_version="v1")
        state = make_state(
            fingerprint="fp1", package="com.test",
            candidate_map=candidate_map, ocr_tokens={"hello"},
        )
        after_state = make_state(
            fingerprint="fp2", package="com.test",
            candidate_map=candidate_map, ocr_tokens={"hello", "world"},
        )

        action = ActionSpec(
            action_type="tap_candidate",
            candidate_id="c1",
            candidate_map_fingerprint="v1",
            expected_screen_fingerprint="fp1",
        )
        source = MockDecisionSource([action])
        executor = FakeExecutor(after_state=after_state)
        verifier = FakeVlmVerifier([
            VerificationResult(
                verification="success", source="vlm",
                reason="mock verified",
            ),
        ])

        from harness import run_action_loop
        result = run_action_loop(
            source, executor, verifier,
            initial_state=state, subgoal="tap c1",
        )

        self.assertTrue(result.ok, f"expected ok=True, got: {result}")
        self.assertEqual(result.status, "success")
        self.assertEqual(len(executor.calls), 1)
        self.assertEqual(result.verification.verification.value, "success")


# ─────────────── 4. Local Verifier 严格 success 条件 ───────────────

class TestLocalVerifier(unittest.TestCase):

    def test_local_verifier_success_on_explicit_signals(self):
        """四种 success 路径 + layout-only 变化应返回 not_yet。"""
        from harness.verifier import LocalVerifier, VerificationStatus
        from tests.mocks import make_state
        from harness.schemas import ActionSpec

        v = LocalVerifier()
        before = make_state(fingerprint="fp1", package="com.a", activity="A",
                            control_bar_visible=False, ocr_tokens={"a"})

        # 1. expected_package 命中
        after = make_state(fingerprint="fp1", package="com.b", activity="A",
                           control_bar_visible=False, ocr_tokens={"a"})
        action = ActionSpec(action_type="tap_candidate", candidate_id="x",
                            expected_package="com.b")
        r = v.verify(before, after, action)
        self.assertEqual(r.verification, VerificationStatus.success)
        self.assertEqual(r.source.value, "local")

        # 2. expected_activity 命中（package 一致）
        after = make_state(fingerprint="fp1", package="com.a", activity="B",
                           control_bar_visible=False, ocr_tokens={"a"})
        action = ActionSpec(action_type="tap_candidate", candidate_id="x",
                            expected_activity="B")
        r = v.verify(before, after, action)
        self.assertEqual(r.verification, VerificationStatus.success)

        # 3. control_bar false → true
        after = make_state(fingerprint="fp1", package="com.a", activity="A",
                           control_bar_visible=True, ocr_tokens={"a"})
        action = ActionSpec(action_type="tap_candidate", candidate_id="x")
        r = v.verify(before, after, action)
        self.assertEqual(r.verification, VerificationStatus.success)

        # 4. target_role 命中 selected_role
        after = make_state(fingerprint="fp1", package="com.a", activity="A",
                           control_bar_visible=False, ocr_tokens={"a"},
                           selected_role="play_button")
        action = ActionSpec(action_type="tap_candidate", candidate_id="x",
                            target_role="play_button")
        r = v.verify(before, after, action)
        self.assertEqual(r.verification, VerificationStatus.success)

        # 5. target_role 命中新 OCR token
        after = make_state(fingerprint="fp1", package="com.a", activity="A",
                           control_bar_visible=False, ocr_tokens={"a", "1.5x"})
        action = ActionSpec(action_type="tap_candidate", candidate_id="x",
                            target_role="1.5x")
        r = v.verify(before, after, action)
        self.assertEqual(r.verification, VerificationStatus.success)

        # 6. 单纯 layout 变化 → not_yet
        after = make_state(fingerprint="fp9", package="com.a", activity="A",
                           control_bar_visible=False, ocr_tokens={"a", "random"})
        action = ActionSpec(action_type="tap_candidate", candidate_id="x")
        r = v.verify(before, after, action)
        self.assertEqual(r.verification, VerificationStatus.not_yet)


# ─────────────── 5. Guard 拒绝 → executor 不被调用 ───────────────

class TestGuardRejection(unittest.TestCase):

    def test_guard_rejection_blocks_executor(self):
        """candidate_id 不在 map / fingerprint 不匹配 / 失败重放 → blocked。"""
        from tests.mocks import (
            MockDecisionSource, FakeExecutor, FakeVlmVerifier,
            make_state, make_candidate, make_candidate_map,
        )
        from harness.schemas import ActionSpec
        from harness import run_action_loop, ActionGuard

        candidate = make_candidate("c1")
        candidate_map = make_candidate_map(candidates=[candidate], screen_version="v1")
        state = make_state(fingerprint="fp1", candidate_map=candidate_map)

        # Case A: candidate_id 不在 map
        action = ActionSpec(action_type="tap_candidate", candidate_id="not_exist",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        source = MockDecisionSource([action])
        executor = FakeExecutor()
        result = run_action_loop(source, executor, FakeVlmVerifier([]),
                                  initial_state=state, subgoal="x")
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

        # Case B: fingerprint 不匹配
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v_OLD",
                            expected_screen_fingerprint="fp1")
        source = MockDecisionSource([action])
        executor = FakeExecutor()
        result = run_action_loop(source, executor, FakeVlmVerifier([]),
                                  initial_state=state, subgoal="x")
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)

        # Case C: 失败重放
        guard = ActionGuard()
        guard.record_failure("fp1", "c1")
        action = ActionSpec(action_type="tap_candidate", candidate_id="c1",
                            candidate_map_fingerprint="v1",
                            expected_screen_fingerprint="fp1")
        source = MockDecisionSource([action])
        executor = FakeExecutor()
        result = run_action_loop(source, executor, FakeVlmVerifier([]),
                                  initial_state=state, subgoal="x", guard=guard)
        self.assertIn(result.status, ("blocked", "guard_reject"))
        self.assertEqual(len(executor.calls), 0)


# ─────────────── 6. done / ask_user 特殊处理 ───────────────

class TestDoneAndAskUser(unittest.TestCase):

    def test_done_without_verification_is_unverified(self):
        """done 无 prior success → stopped_unverified。"""
        from tests.mocks import MockDecisionSource, FakeExecutor, FakeVlmVerifier, make_state
        from harness.schemas import ActionSpec
        from harness import run_action_loop

        state = make_state()
        source = MockDecisionSource([ActionSpec(action_type="done")])
        executor = FakeExecutor()
        result = run_action_loop(source, executor, FakeVlmVerifier([]),
                                  initial_state=state, subgoal="x")

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "stopped_unverified")
        self.assertEqual(len(executor.calls), 0)

    def test_ask_user_returns_needs_confirmation(self):
        """ask_user → needs_user_confirmation。"""
        from tests.mocks import MockDecisionSource, FakeExecutor, FakeVlmVerifier, make_state
        from harness.schemas import ActionSpec
        from harness import run_action_loop

        state = make_state()
        source = MockDecisionSource([ActionSpec(action_type="ask_user")])
        executor = FakeExecutor()
        result = run_action_loop(source, executor, FakeVlmVerifier([]),
                                  initial_state=state, subgoal="x")

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "needs_user_confirmation")
        self.assertEqual(len(executor.calls), 0)


if __name__ == "__main__":
    unittest.main()
