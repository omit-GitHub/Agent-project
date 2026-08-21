# -*- coding: utf-8 -*-
"""Run Baseline Benchmarks — 运行 baseline 对照实验。

Baseline 模式：Mock 决策动作直接交 Executor，不经过 Guard。
对比 harness 模式，统计错误动作执行率。
"""
import json
import os
import sys
import time
from typing import Optional

# 添加项目根目录到路径
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
_SRC_ROOT = os.path.join(_PROJECT_ROOT, "src")
_BENCH_ROOT = _HERE
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)
if _BENCH_ROOT not in sys.path:
    sys.path.insert(0, _BENCH_ROOT)

from harness import ActionSpec, UiState
from benchmark_mocks import MockDecisionSource, MockExecutor, create_default_after_state
from scenario_registry import get_all_scenarios
import comprehensive_scenarios


def run_baseline_scenario(scenario) -> dict:
    """运行单个场景的 baseline 模式。"""
    start_time = time.time()

    # 创建 mock
    decision_source = MockDecisionSource(actions=scenario.decision_sequence)
    after_state = create_default_after_state(scenario.initial_state)
    executor = MockExecutor(after_state=after_state)

    # Baseline 模式：直接执行所有动作，不经过 Guard
    executor_calls = 0
    for action in scenario.decision_sequence:
        if action.action_type == "done":
            break
        result = executor.execute(action, scenario.initial_state)
        executor_calls += 1

    end_time = time.time()
    total_elapsed_ms = (end_time - start_time) * 1000

    return {
        "scenario_id": scenario.scenario_id,
        "category": scenario.category,
        "dimension": scenario.dimension,
        "executor_calls": executor_calls,
        "total_elapsed_ms": round(total_elapsed_ms, 2),
    }


def run_baseline_benchmarks(output_path: Optional[str] = None):
    """运行所有场景的 baseline 模式。"""
    if output_path is None:
        output_path = os.path.join(_PROJECT_ROOT, "artifacts", "baseline_traces.jsonl")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 获取所有场景
    scenarios = get_all_scenarios()
    print(f"Loaded {len(scenarios)} benchmark scenarios for baseline")

    # 运行所有场景
    traces = []
    for i, scenario in enumerate(scenarios, 1):
        print(f"[{i}/{len(scenarios)}] Running baseline for {scenario.scenario_id}...")
        trace = run_baseline_scenario(scenario)
        traces.append(trace)

    # 写入 jsonl
    with open(output_path, "w", encoding="utf-8") as f:
        for trace in traces:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")

    print(f"\nCompleted! Baseline traces written to {output_path}")
    return traces


def compare_baseline_vs_harness(
    baseline_path: str,
    harness_path: str,
    output_path: str,
):
    """对比 baseline 和 harness 结果。"""
    # 加载 traces
    baseline_traces = {}
    with open(baseline_path, "r", encoding="utf-8") as f:
        for line in f:
            trace = json.loads(line)
            baseline_traces[trace["scenario_id"]] = trace

    harness_traces = {}
    with open(harness_path, "r", encoding="utf-8") as f:
        for line in f:
            trace = json.loads(line)
            harness_traces[trace["scenario_id"]] = trace

    # 仅针对 invalid_action + sensitive_action 场景统计
    target_categories = {"invalid_action", "sensitive_action"}

    # 统计错误动作执行
    error_action_injected = 0
    error_action_executed_baseline = 0
    error_action_executed_harness = 0

    guard_blocked = 0
    blocked_with_zero_executor = 0
    requires_refinement_zero_executor = 0

    for scenario_id, baseline_trace in baseline_traces.items():
        harness_trace = harness_traces.get(scenario_id)
        if not harness_trace:
            continue

        category = baseline_trace.get("category")
        if category not in target_categories:
            continue

        # 错误动作注入
        error_action_injected += 1

        # Baseline 执行
        if baseline_trace.get("executor_calls", 0) > 0:
            error_action_executed_baseline += 1

        # Harness 执行
        if harness_trace.get("executor_calls", 0) > 0:
            error_action_executed_harness += 1

        # Guard 阻断
        if harness_trace.get("final_status") in ("guard_reject", "needs_user_confirmation"):
            guard_blocked += 1
            if harness_trace.get("executor_calls", 1) == 0:
                blocked_with_zero_executor += 1

        # requires_refinement 零执行
        if harness_trace.get("final_status") == "needs_refinement":
            if harness_trace.get("executor_calls", 1) == 0:
                requires_refinement_zero_executor += 1

    # 计算指标
    comparison = {
        "target_categories": list(target_categories),
        "error_action_injected": error_action_injected,
        "error_action_executed_baseline": error_action_executed_baseline,
        "error_action_executed_harness": error_action_executed_harness,
        "error_action_execution_rate_baseline": round(
            error_action_executed_baseline / error_action_injected, 3
        ) if error_action_injected > 0 else 0,
        "error_action_execution_rate_harness": round(
            error_action_executed_harness / error_action_injected, 3
        ) if error_action_injected > 0 else 0,
        "error_action_reduction": round(
            (error_action_executed_baseline - error_action_executed_harness) / error_action_injected, 3
        ) if error_action_injected > 0 else 0,
        "guard_block_rate": round(
            guard_blocked / error_action_injected, 3
        ) if error_action_injected > 0 else 0,
        "blocked_cases_with_zero_executor_calls": blocked_with_zero_executor,
        "requires_refinement_zero_executor_calls": requires_refinement_zero_executor,
    }

    # 输出 JSON
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2, ensure_ascii=False)

    print(f"\nBaseline vs Harness comparison written to {output_path}")
    print(f"\nKey Metrics:")
    print(f"  Error actions injected: {error_action_injected}")
    print(f"  Error actions executed (baseline): {error_action_executed_baseline}")
    print(f"  Error actions executed (harness): {error_action_executed_harness}")
    print(f"  Error action execution rate (baseline): {comparison['error_action_execution_rate_baseline']}")
    print(f"  Error action execution rate (harness): {comparison['error_action_execution_rate_harness']}")
    print(f"  Error action reduction: {comparison['error_action_reduction']}")
    print(f"  Guard block rate: {comparison['guard_block_rate']}")
    print(f"  Blocked cases with zero executor calls: {blocked_with_zero_executor}")
    print(f"  Requires refinement with zero executor calls: {requires_refinement_zero_executor}")

    return comparison


if __name__ == "__main__":
    # 运行 baseline
    baseline_traces_path = os.path.join(_PROJECT_ROOT, "artifacts", "baseline_traces.jsonl")
    run_baseline_benchmarks(baseline_traces_path)

    # 对比 baseline vs harness
    harness_traces_path = os.path.join(_PROJECT_ROOT, "artifacts", "benchmark_traces.jsonl")
    comparison_path = os.path.join(_PROJECT_ROOT, "artifacts", "baseline_vs_harness.json")

    if os.path.exists(harness_traces_path):
        compare_baseline_vs_harness(baseline_traces_path, harness_traces_path, comparison_path)
    else:
        print(f"\nHarness traces not found at {harness_traces_path}")
        print("Please run run_benchmarks.py first.")
