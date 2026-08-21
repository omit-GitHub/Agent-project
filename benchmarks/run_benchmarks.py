# -*- coding: utf-8 -*-
"""Run Benchmarks — 执行全部 benchmark 场景。

加载所有场景，运行 action_loop，收集 trace，输出到 jsonl 文件。
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

from harness import (
    ActionSpec, UiState, BBox,
    ActionGuard, ActionGuardConfig,
    run_action_loop,
)
from harness.verifier import VerificationResult, VerificationStatus
from scenario_registry import get_all_scenarios, BenchmarkScenario
from benchmark_mocks import (
    MockDecisionSource, MockExecutor, MockVerifier,
    create_default_after_state, create_success_verification,
    create_not_yet_verification, create_unknown_verification,
)
from trace_collector import TraceCollector

# 导入综合场景定义以触发注册
import comprehensive_scenarios


def setup_mocks_for_scenario(scenario: BenchmarkScenario):
    """为场景设置 mock。"""
    # DecisionSource
    decision_source = MockDecisionSource(actions=scenario.decision_sequence)

    # Executor
    after_state = create_default_after_state(scenario.initial_state)
    executor = MockExecutor(after_state=after_state)

    # Verifier - 默认返回 success
    verifier = MockVerifier(results=[create_success_verification()])

    return decision_source, executor, verifier


def run_single_scenario(scenario: BenchmarkScenario) -> dict:
    """运行单个场景并返回 trace。"""
    start_time = time.time()

    # 设置 mock
    decision_source, executor, verifier = setup_mocks_for_scenario(scenario)

    # 创建 TraceCollector
    trace_collector = TraceCollector(deadline_ms=scenario.deadline_ms)

    # 运行 action_loop
    try:
        result = run_action_loop(
            decision_source=decision_source,
            executor=executor,
            verifier=verifier,
            initial_state=scenario.initial_state,
            subgoal="benchmark_scenario",
            guard=ActionGuard(),
            config=ActionGuardConfig(),
            max_steps=scenario.max_steps,
            max_decision_calls=scenario.max_decision_calls,
            recovery_budget=scenario.recovery_budget,
        )

        end_time = time.time()
        total_elapsed_ms = (end_time - start_time) * 1000

        # 构建 trace
        trace = {
            "scenario_id": scenario.scenario_id,
            "category": scenario.category,
            "dimension": scenario.dimension,
            "description": scenario.description,
            "final_status": result.status,
            "failure_reason": result.final_message,
            "decision_calls": result.decision_calls,
            "atomic_action_count": result.atomic_action_count,
            "recovery_count": result.recovery_count,
            "executor_calls": len(executor.calls),
            "total_elapsed_ms": round(total_elapsed_ms, 2),
            "steps": result.steps,
            "trace": result.trace,
            "expected_outcome": scenario.expected_outcome,
            "expected_executor_calls": scenario.expected_executor_calls,
            "expected_failure_reason": scenario.expected_failure_reason,
            "outcome_matches": result.status == scenario.expected_outcome,
            "executor_calls_matches": len(executor.calls) == scenario.expected_executor_calls,
            "recoverable": scenario.recoverable,
            "reveal_scenario": scenario.reveal_scenario,
        }

        return trace

    except Exception as e:
        end_time = time.time()
        total_elapsed_ms = (end_time - start_time) * 1000

        return {
            "scenario_id": scenario.scenario_id,
            "category": scenario.category,
            "dimension": scenario.dimension,
            "description": scenario.description,
            "final_status": "error",
            "failure_reason": str(e),
            "decision_calls": 0,
            "atomic_action_count": 0,
            "recovery_count": 0,
            "executor_calls": 0,
            "total_elapsed_ms": round(total_elapsed_ms, 2),
            "error": True,
        }


def run_all_benchmarks(output_path: Optional[str] = None):
    """运行所有 benchmark 场景。"""
    if output_path is None:
        output_path = os.path.join(_PROJECT_ROOT, "artifacts", "benchmark_traces.jsonl")

    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 获取所有场景
    scenarios = get_all_scenarios()
    print(f"Loaded {len(scenarios)} benchmark scenarios")

    # 运行所有场景
    traces = []
    for i, scenario in enumerate(scenarios, 1):
        print(f"[{i}/{len(scenarios)}] Running {scenario.scenario_id}...")
        trace = run_single_scenario(scenario)
        traces.append(trace)

        # 检查预期结果
        if not trace.get("outcome_matches", False):
            print(f"  [WARN] Outcome mismatch: expected {scenario.expected_outcome}, got {trace['final_status']}")
        if not trace.get("executor_calls_matches", False):
            print(f"  [WARN] Executor calls mismatch: expected {scenario.expected_executor_calls}, got {trace['executor_calls']}")

    # 写入 jsonl
    with open(output_path, "w", encoding="utf-8") as f:
        for trace in traces:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")

    print(f"\nCompleted! Traces written to {output_path}")
    print(f"Total scenarios: {len(traces)}")
    print(f"Outcome matches: {sum(1 for t in traces if t.get('outcome_matches', False))}/{len(traces)}")
    print(f"Executor calls matches: {sum(1 for t in traces if t.get('executor_calls_matches', False))}/{len(traces)}")

    return traces


if __name__ == "__main__":
    run_all_benchmarks()
