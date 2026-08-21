# -*- coding: utf-8 -*-
"""Expected OCR Tokens Tests — 多 token 全集语义验证。

覆盖：
  - expected_ocr_tokens 字段的基本功能
  - 全集语义：所有 token 必须出现在 new_tokens 中
  - 部分出现 → not_yet
  - 全部出现 → success
  - 空集合 → 不触发此检查
  - 与 target_role OCR 检查的优先级关系

运行：
  cd harness-framework
  python -m unittest tests.test_expected_ocr_tokens -v
"""
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
_SRC_ROOT = os.path.join(_PROJECT_ROOT, "src")
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)

from harness import ActionSpec
from harness.verifier import LocalVerifier, VerificationStatus
from tests.mocks import make_state


class TestExpectedOCRTokens(unittest.TestCase):
    """expected_ocr_tokens 多 token 全集语义测试。"""

    def setUp(self):
        self.v = LocalVerifier()

    def test_01_all_tokens_appear_success(self):
        """所有期望 token 都出现 → success。"""
        before = make_state(
            fingerprint="fp1",
            ocr_tokens={"existing1", "existing2"}
        )
        after = make_state(
            fingerprint="fp2",
            ocr_tokens={"existing1", "existing2", "play", "pause", "stop"}
        )
        action = ActionSpec(
            action_type="tap_candidate",
            candidate_id="c1",
            expected_ocr_tokens={"play", "pause", "stop"}
        )

        result = self.v.verify(before, after, action)

        self.assertEqual(result.verification, VerificationStatus.success)
        self.assertIn("all expected OCR tokens appeared", result.reason)

    def test_02_partial_tokens_appear_not_yet(self):
        """部分 token 出现 → not_yet。"""
        before = make_state(
            fingerprint="fp1",
            ocr_tokens={"existing1"}
        )
        after = make_state(
            fingerprint="fp2",
            ocr_tokens={"existing1", "play"}  # 只出现了 "play"，缺少 "pause" 和 "stop"
        )
        action = ActionSpec(
            action_type="tap_candidate",
            candidate_id="c1",
            expected_ocr_tokens={"play", "pause", "stop"}
        )

        result = self.v.verify(before, after, action)

        self.assertEqual(result.verification, VerificationStatus.not_yet)

    def test_03_no_tokens_appear_not_yet(self):
        """没有任何期望 token 出现 → not_yet。"""
        before = make_state(
            fingerprint="fp1",
            ocr_tokens={"existing1"}
        )
        after = make_state(
            fingerprint="fp2",
            ocr_tokens={"existing1", "other"}  # 没有出现任何期望 token
        )
        action = ActionSpec(
            action_type="tap_candidate",
            candidate_id="c1",
            expected_ocr_tokens={"play", "pause"}
        )

        result = self.v.verify(before, after, action)

        self.assertEqual(result.verification, VerificationStatus.not_yet)

    def test_04_empty_set_no_trigger(self):
        """空集合 → 不触发此检查。"""
        before = make_state(
            fingerprint="fp1",
            ocr_tokens={"existing1"}
        )
        after = make_state(
            fingerprint="fp2",
            ocr_tokens={"existing1", "play"}
        )
        action = ActionSpec(
            action_type="tap_candidate",
            candidate_id="c1",
            expected_ocr_tokens=set()  # 空集合
        )

        result = self.v.verify(before, after, action)

        # 空集合不触发检查，应该走其他逻辑或返回 not_yet
        self.assertEqual(result.verification, VerificationStatus.not_yet)

    def test_05_none_no_trigger(self):
        """None → 不触发此检查。"""
        before = make_state(
            fingerprint="fp1",
            ocr_tokens={"existing1"}
        )
        after = make_state(
            fingerprint="fp2",
            ocr_tokens={"existing1", "play"}
        )
        action = ActionSpec(
            action_type="tap_candidate",
            candidate_id="c1",
            expected_ocr_tokens=None  # None
        )

        result = self.v.verify(before, after, action)

        # None 不触发检查，应该走其他逻辑或返回 not_yet
        self.assertEqual(result.verification, VerificationStatus.not_yet)

    def test_06_single_token_success(self):
        """单个 token 出现 → success。"""
        before = make_state(
            fingerprint="fp1",
            ocr_tokens={"existing1"}
        )
        after = make_state(
            fingerprint="fp2",
            ocr_tokens={"existing1", "play"}
        )
        action = ActionSpec(
            action_type="tap_candidate",
            candidate_id="c1",
            expected_ocr_tokens={"play"}
        )

        result = self.v.verify(before, after, action)

        self.assertEqual(result.verification, VerificationStatus.success)

    def test_07_extra_tokens_ok(self):
        """出现额外 token 也可以 → 只要期望的都出现就行。"""
        before = make_state(
            fingerprint="fp1",
            ocr_tokens={"existing1"}
        )
        after = make_state(
            fingerprint="fp2",
            ocr_tokens={"existing1", "play", "pause", "extra1", "extra2"}
        )
        action = ActionSpec(
            action_type="tap_candidate",
            candidate_id="c1",
            expected_ocr_tokens={"play", "pause"}  # 只期望这两个
        )

        result = self.v.verify(before, after, action)

        # 期望的都出现了，额外的不影响
        self.assertEqual(result.verification, VerificationStatus.success)

    def test_08_priority_target_role_first(self):
        """target_role OCR 检查优先于 expected_ocr_tokens。"""
        before = make_state(
            fingerprint="fp1",
            ocr_tokens={"existing1"},
            selected_role=None
        )
        after = make_state(
            fingerprint="fp2",
            ocr_tokens={"existing1", "play", "pause"},
            selected_role="play"  # target_role 出现
        )
        action = ActionSpec(
            action_type="tap_candidate",
            candidate_id="c1",
            target_role="play",  # 这个检查优先
            expected_ocr_tokens={"play", "pause"}  # 这个也会成功，但不会执行到
        )

        result = self.v.verify(before, after, action)

        # target_role 检查先执行，应该返回 selected_role 相关的成功
        self.assertEqual(result.verification, VerificationStatus.success)
        self.assertIn("selected_role", result.reason)

    def test_09_observed_state_includes_tokens(self):
        """observed_state 应该包含 expected_ocr_tokens 信息。"""
        before = make_state(
            fingerprint="fp1",
            ocr_tokens={"existing1"}
        )
        after = make_state(
            fingerprint="fp2",
            ocr_tokens={"existing1", "play", "pause"}
        )
        action = ActionSpec(
            action_type="tap_candidate",
            candidate_id="c1",
            expected_ocr_tokens={"play", "pause"}
        )

        result = self.v.verify(before, after, action)

        # observed_state 应该包含 expected_ocr_tokens
        self.assertIn("expected_ocr_tokens", result.observed_state)
        self.assertEqual(result.observed_state["expected_ocr_tokens"], ["pause", "play"])

    def test_10_tokens_already_exist_not_yet(self):
        """token 已经存在于 before 中 → 不算 new_tokens → not_yet。"""
        before = make_state(
            fingerprint="fp1",
            ocr_tokens={"play", "pause"}  # 已经存在
        )
        after = make_state(
            fingerprint="fp2",
            ocr_tokens={"play", "pause"}  # 没有新增
        )
        action = ActionSpec(
            action_type="tap_candidate",
            candidate_id="c1",
            expected_ocr_tokens={"play", "pause"}
        )

        result = self.v.verify(before, after, action)

        # token 已经存在，不算新出现
        self.assertEqual(result.verification, VerificationStatus.not_yet)


if __name__ == "__main__":
    unittest.main()
