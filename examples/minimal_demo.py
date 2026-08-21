#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Harness Framework — 最小可运行演示。

展示 run_action_loop 在纯 mock 环境下的完整闭环：
  1. 构造一个 UiState（带 CandidateMap）
  2. 用 MockDecisionSource 给出一个 tap_candidate 动作
  3. 用 FakeExecutor 执行（不连真实设备）
  4. 用 LocalVerifier 验证（不调 VLM）
  5. 得到 ActionLoopResult(ok=True, status="success")

运行：
  cd harness-framework
  python examples/minimal_demo.py
"""
import sys
import os

# 让示例能找到 harness 包
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
_SRC_ROOT = os.path.join(_PROJECT_ROOT, "src")
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)

# 让示例能找到 tests.mocks
_TESTS_ROOT = _PROJECT_ROOT
if _TESTS_ROOT not in sys.path:
    sys.path.insert(0, _TESTS_ROOT)

from harness import (
    ActionSpec, run_action_loop,
    LocalVerifier,
)
from tests.mocks import (
    MockDecisionSource, FakeExecutor,
    make_candidate, make_candidate_map, make_state,
)


def main():
    print("=" * 70)
    print("Harness Framework — 最小可运行演示")
    print("=" * 70)
    print()

    # 1. 构造初始 UI 状态
    candidate = make_candidate(
        candidate_id="speed_1_5x",
        text="1.5x",
    )
    candidate_map = make_candidate_map(
        candidates=[candidate],
        screen_version="screen_v1",
        package="com.example.videoplayer",
        activity="PlayerActivity",
    )
    initial_state = make_state(
        fingerprint="player_playing",
        package="com.example.videoplayer",
        activity="PlayerActivity",
        candidate_map=candidate_map,
        control_bar_visible=True,
        ocr_tokens={"playing", "1.0x", "episode 1"},
    )

    print("[1] 初始状态:")
    print(f"    fingerprint = {initial_state.fingerprint}")
    print(f"    package     = {initial_state.package}")
    print(f"    candidates  = {[c.candidate_id for c in initial_state.candidate_map.candidates]}")
    print(f"    ocr_tokens  = {sorted(initial_state.ocr_tokens)}")
    print()

    # 2. 构造动作：点击 "1.5x" 倍速按钮
    action = ActionSpec(
        action_type="tap_candidate",
        candidate_id="speed_1_5x",
        candidate_map_fingerprint="screen_v1",
        expected_screen_fingerprint="player_playing",
        target_role="1.5x",
    )
    decision_source = MockDecisionSource([action])

    print(f"[2] 决策源产出动作:")
    print(f"    action_type               = {action.action_type}")
    print(f"    candidate_id              = {action.candidate_id}")
    print(f"    candidate_map_fingerprint = {action.candidate_map_fingerprint}")
    print(f"    target_role               = {action.target_role}")
    print()

    # 3. 执行器：模拟执行后 OCR 出现 "1.5x" 选中态
    after_state = make_state(
        fingerprint="player_playing",
        package="com.example.videoplayer",
        activity="PlayerActivity",
        candidate_map=candidate_map,
        control_bar_visible=True,
        ocr_tokens={"playing", "1.0x", "1.5x", "episode 1"},
        selected_role="1.5x",
    )
    executor = FakeExecutor(after_state=after_state)

    # 4. 验证器：用本地信号验证（不调 VLM）
    verifier = LocalVerifier()

    # 5. 跑闭环
    result = run_action_loop(
        decision_source, executor, verifier,
        initial_state=initial_state,
        subgoal="切换到 1.5 倍速",
    )

    print("[3] Action Loop 结果:")
    print(f"    ok              = {result.ok}")
    print(f"    status          = {result.status}")
    print(f"    final_message   = {result.final_message}")
    print(f"    steps           = {len(result.steps)}")
    if result.verification:
        print(f"    verification    = {result.verification.verification.value}")
        print(f"    source          = {result.verification.source.value}")
        print(f"    reason          = {result.verification.reason}")
    print()

    print("=" * 70)
    if result.ok and result.status == "success":
        print("[OK] 成功：Harness 在纯 mock 环境下完成一次完整闭环。")
    else:
        print(f"[FAIL] 失败：{result.final_message}")
    print("=" * 70)

    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
