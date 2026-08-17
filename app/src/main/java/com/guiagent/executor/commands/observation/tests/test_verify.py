# -*- coding: utf-8 -*-
"""Verification Framework 单元测试。

覆盖:
  - predicates.py: PredicateResult + 8 个谓词（mock state）
  - verifier.py: verify() + verify_after_action()
  - recovery.py: noop / wait_and_retry / chain

运行:
  cd app/src/main/java/com/guiagent/executor/commands
  python -m unittest observation.tests.test_verify -v
"""
import os
import sys
import time
import unittest
from unittest.mock import patch, MagicMock

_HERE = os.path.dirname(os.path.abspath(__file__))
_COMMANDS_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _COMMANDS_ROOT not in sys.path:
    sys.path.insert(0, _COMMANDS_ROOT)

from observation.verify.predicates import (
    PredicateResult,
    bar_visible,
    playing_state_changed,
    speed_changed,
    quality_changed,
    overlay_appeared,
    text_present,
)
from observation.verify.verifier import (
    verify,
    verify_after_action,
    VerificationResult,
    AfterActionResult,
)
from observation.verify.recovery import (
    noop,
    wait_and_retry,
    chain,
)


# ─────────────── 测试辅助 ───────────────

def _make_state(**overrides):
    """构造一个 mock StateSnapshot。"""
    from observation.state.schema import StateSnapshot, PlayerState
    s = StateSnapshot(
        pkg=overrides.get("pkg", "com.qiyi.video.speaker"),
        page_type=overrides.get("page_type", "player"),
        summary=overrides.get("summary", ["暂停", "选集"]),
    )
    if "player" in overrides:
        s.player = overrides["player"]
    elif s.page_type == "player":
        s.player = PlayerState(
            control_bar_visible=overrides.get("bar_visible", True),
            is_playing=overrides.get("is_playing", True),
            current_speed=overrides.get("speed", "1.0"),
            current_quality=overrides.get("quality", "1080P"),
        )
    if "overlay" in overrides:
        s.overlay = overrides["overlay"]
    return s


# ═══════════════ PredicateResult Tests ═══════════════

class TestPredicateResult(unittest.TestCase):

    def test_bool_true(self):
        r = PredicateResult(True, {"x": 1})
        self.assertTrue(bool(r))
        self.assertTrue(r)

    def test_bool_false(self):
        r = PredicateResult(False)
        self.assertFalse(bool(r))

    def test_defaults(self):
        r = PredicateResult(True)
        self.assertEqual(r.evidence, {})
        self.assertEqual(r.confidence, "high")
        self.assertEqual(r.message, "")


# ═══════════════ Predicate Tests (with mocked resolve_state) ═══════════════

class TestBarVisiblePredicate(unittest.TestCase):

    @patch("observation.verify.predicates.resolve_state")
    def test_visible(self, mock_resolve):
        mock_resolve.return_value = _make_state(bar_visible=True)
        pred = bar_visible()
        result = pred()
        self.assertTrue(result.verified)
        self.assertEqual(result.confidence, "high")

    @patch("observation.verify.predicates.resolve_state")
    def test_hidden(self, mock_resolve):
        mock_resolve.return_value = _make_state(bar_visible=False)
        pred = bar_visible()
        result = pred()
        self.assertFalse(result.verified)

    @patch("observation.verify.predicates.resolve_state")
    def test_not_player_page(self, mock_resolve):
        mock_resolve.return_value = _make_state(page_type="structured")
        pred = bar_visible()
        result = pred()
        self.assertFalse(result.verified)
        self.assertIn("not on player page", result.message)


class TestPlayingStateChangedPredicate(unittest.TestCase):

    @patch("observation.verify.predicates.resolve_state")
    def test_matches(self, mock_resolve):
        mock_resolve.return_value = _make_state(is_playing=True)
        pred = playing_state_changed(expected=True)
        self.assertTrue(pred().verified)

    @patch("observation.verify.predicates.resolve_state")
    def test_mismatch(self, mock_resolve):
        mock_resolve.return_value = _make_state(is_playing=False)
        pred = playing_state_changed(expected=True)
        self.assertFalse(pred().verified)

    @patch("observation.verify.predicates.resolve_state")
    def test_unknown_state(self, mock_resolve):
        from observation.state.schema import StateSnapshot, PlayerState
        s = StateSnapshot(page_type="player", player=PlayerState(is_playing=None))
        mock_resolve.return_value = s
        pred = playing_state_changed(expected=True)
        result = pred()
        self.assertFalse(result.verified)
        self.assertEqual(result.confidence, "low")


class TestSpeedChangedPredicate(unittest.TestCase):

    @patch("observation.verify.predicates.resolve_state")
    def test_matches(self, mock_resolve):
        mock_resolve.return_value = _make_state(speed="1.5")
        pred = speed_changed("1.5")
        self.assertTrue(pred().verified)

    @patch("observation.verify.predicates.resolve_state")
    def test_mismatch(self, mock_resolve):
        mock_resolve.return_value = _make_state(speed="1.0")
        pred = speed_changed("1.5")
        self.assertFalse(pred().verified)


class TestQualityChangedPredicate(unittest.TestCase):

    @patch("observation.verify.predicates.resolve_state")
    def test_matches_with_p(self, mock_resolve):
        mock_resolve.return_value = _make_state(quality="720P")
        pred = quality_changed("720P")
        self.assertTrue(pred().verified)

    @patch("observation.verify.predicates.resolve_state")
    def test_matches_without_p(self, mock_resolve):
        # 用户传 "720"，state 是 "720P"，应该匹配
        mock_resolve.return_value = _make_state(quality="720P")
        pred = quality_changed("720")
        self.assertTrue(pred().verified)


class TestOverlayAppearedPredicate(unittest.TestCase):

    @patch("observation.verify.predicates.resolve_state")
    def test_matches(self, mock_resolve):
        mock_resolve.return_value = _make_state(overlay="speed_panel")
        pred = overlay_appeared("speed_panel")
        self.assertTrue(pred().verified)

    @patch("observation.verify.predicates.resolve_state")
    def test_mismatch(self, mock_resolve):
        mock_resolve.return_value = _make_state(overlay=None)
        pred = overlay_appeared("speed_panel")
        self.assertFalse(pred().verified)


class TestTextPresentPredicate(unittest.TestCase):

    @patch("observation.verify.predicates.resolve_state")
    def test_found(self, mock_resolve):
        mock_resolve.return_value = _make_state(summary=["暂停", "选集", "第3集"])
        pred = text_present("第3集")
        self.assertTrue(pred().verified)

    @patch("observation.verify.predicates.resolve_state")
    def test_not_found(self, mock_resolve):
        mock_resolve.return_value = _make_state(summary=["暂停", "选集"])
        pred = text_present("第3集")
        self.assertFalse(pred().verified)


# ═══════════════ Verifier Tests ═══════════════

class TestVerifyFunction(unittest.TestCase):

    def test_immediate_success(self):
        counter = {"n": 0}
        def pred():
            counter["n"] += 1
            return PredicateResult(True, {"attempt": counter["n"]})
        result = verify(pred, timeout_ms=1000, poll_interval_ms=50)
        self.assertTrue(result.verified)
        self.assertEqual(result.attempts, 1)
        self.assertFalse(result.timed_out)

    def test_success_after_retries(self):
        counter = {"n": 0}
        def pred():
            counter["n"] += 1
            return PredicateResult(counter["n"] >= 3)
        result = verify(pred, timeout_ms=2000, poll_interval_ms=50)
        self.assertTrue(result.verified)
        self.assertEqual(counter["n"], 3)

    def test_timeout(self):
        def pred():
            return PredicateResult(False)
        result = verify(pred, timeout_ms=200, poll_interval_ms=50)
        self.assertFalse(result.verified)
        self.assertTrue(result.timed_out)
        self.assertGreater(result.attempts, 1)

    def test_predicate_exception_continues(self):
        counter = {"n": 0}
        def pred():
            counter["n"] += 1
            if counter["n"] < 3:
                raise RuntimeError("transient error")
            return PredicateResult(True)
        result = verify(pred, timeout_ms=2000, poll_interval_ms=50)
        self.assertTrue(result.verified)
        self.assertEqual(counter["n"], 3)


class TestVerifyAfterAction(unittest.TestCase):

    def test_success_no_recovery(self):
        action_calls = {"n": 0}
        def action():
            action_calls["n"] += 1
            return {"ok": True, "data": {"actioned": True}}
        def pred():
            return PredicateResult(True)
        result = verify_after_action(
            action_fn=action,
            predicate=pred,
            max_retries=1,
            verify_timeout_ms=500,
        )
        self.assertTrue(result.ok)
        self.assertFalse(result.recovered)
        self.assertEqual(action_calls["n"], 1)

    def test_failure_then_recovery_success(self):
        """第一次失败 → recover → 第二次成功。

        通过 shared flag 模拟"恢复动作改变了外部状态"：
        在 recover 被调用前，predicate 一直返回 False；
        recover 被调用后，predicate 改为返回 True。
        """
        action_calls = {"n": 0}
        def action():
            action_calls["n"] += 1
            return {"ok": True}

        # 共享状态：recover 调用前 False，调用后 True
        state = {"recovered": False}
        def pred():
            return PredicateResult(state["recovered"])

        recover_calls = {"n": 0}
        def recover():
            recover_calls["n"] += 1
            state["recovered"] = True  # 模拟恢复改变了外部状态
            return {"ok": True}

        result = verify_after_action(
            action_fn=action,
            predicate=pred,
            recover_fn=recover,
            max_retries=1,
            verify_timeout_ms=100,
            verify_poll_ms=30,
        )
        self.assertTrue(result.ok)
        self.assertTrue(result.recovered)
        self.assertEqual(action_calls["n"], 2)   # 初次 + 重试
        self.assertEqual(recover_calls["n"], 1)  # 恢复被调用一次

    def test_failure_no_recover_fn(self):
        def action():
            return {"ok": True}
        def pred():
            return PredicateResult(False)
        result = verify_after_action(
            action_fn=action,
            predicate=pred,
            max_retries=1,
            verify_timeout_ms=100,
        )
        self.assertFalse(result.ok)
        self.assertFalse(result.recovered)

    def test_action_raises(self):
        def action():
            raise RuntimeError("boom")
        def pred():
            return PredicateResult(True)
        result = verify_after_action(
            action_fn=action,
            predicate=pred,
            max_retries=1,
            verify_timeout_ms=100,
        )
        self.assertFalse(result.ok)
        self.assertIn("boom", result.error)


# ═══════════════ Recovery Tests ═══════════════

class TestRecovery(unittest.TestCase):

    def test_noop(self):
        fn = noop()
        result = fn()
        self.assertTrue(result["ok"])
        self.assertTrue(result["data"]["noop"])

    def test_wait_and_retry(self):
        fn = wait_and_retry(seconds=0.1)
        start = time.time()
        result = fn()
        elapsed = time.time() - start
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(elapsed, 0.09)

    def test_chain(self):
        fn = chain(noop(), noop())
        result = fn()
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["data"]["chain_results"]), 2)

    def test_chain_stops_on_failure(self):
        def failing():
            return {"ok": False, "error": "boom"}
        fn = chain(failing, noop)
        result = fn()
        self.assertFalse(result["ok"])
        # 第二个不应该被调用
        self.assertEqual(len(result["data"]["chain_results"]), 1)


if __name__ == "__main__":
    unittest.main()
