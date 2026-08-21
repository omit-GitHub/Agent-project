# -*- coding: utf-8 -*-
"""Summarize Benchmarks — 从 trace 汇总 metrics。

读取 benchmark_traces.jsonl，计算各种指标，输出 benchmark_metrics.json 和 benchmark_metrics.csv。
"""
import csv
import json
import os
import sys
from collections import defaultdict
from typing import List, Dict, Any


def load_traces(traces_path: str) -> List[Dict]:
    """加载 trace 文件。"""
    traces = []
    with open(traces_path, "r", encoding="utf-8") as f:
        for line in f:
            traces.append(json.loads(line))
    return traces


def calculate_basic_metrics(traces: List[Dict]) -> Dict:
    """计算基本指标。"""
    total_scenarios = len(traces)
    outcome_matches = sum(1 for t in traces if t.get("outcome_matches", False))
    executor_calls_matches = sum(1 for t in traces if t.get("executor_calls_matches", False))

    return {
        "total_scenarios": total_scenarios,
        "outcome_matches": outcome_matches,
        "outcome_match_rate": round(outcome_matches / total_scenarios, 3) if total_scenarios > 0 else 0,
        "executor_calls_matches": executor_calls_matches,
        "executor_calls_match_rate": round(executor_calls_matches / total_scenarios, 3) if total_scenarios > 0 else 0,
    }


def calculate_category_metrics(traces: List[Dict]) -> Dict:
    """按类别统计指标。"""
    category_counts = defaultdict(int)
    category_outcome_matches = defaultdict(int)

    for trace in traces:
        category = trace.get("category", "unknown")
        category_counts[category] += 1
        if trace.get("outcome_matches", False):
            category_outcome_matches[category] += 1

    return {
        "category_distribution": dict(category_counts),
        "category_outcome_match_rates": {
            cat: round(category_outcome_matches[cat] / category_counts[cat], 3)
            for cat in category_counts
        },
    }


def calculate_dimension_metrics(traces: List[Dict]) -> Dict:
    """按维度统计指标。"""
    dimension_counts = defaultdict(int)
    dimension_outcome_matches = defaultdict(int)

    for trace in traces:
        dimension = trace.get("dimension", "unknown")
        dimension_counts[dimension] += 1
        if trace.get("outcome_matches", False):
            dimension_outcome_matches[dimension] += 1

    return {
        "dimension_distribution": dict(dimension_counts),
        "dimension_outcome_match_rates": {
            dim: round(dimension_outcome_matches[dim] / dimension_counts[dim], 3)
            for dim in dimension_counts
        },
    }


def calculate_safety_metrics(traces: List[Dict]) -> Dict:
    """计算安全指标。"""
    # 统计 Guard 拒绝场景
    guard_rejection_scenarios = [
        t for t in traces
        if t.get("final_status") in ("guard_reject", "needs_user_confirmation", "needs_refinement")
    ]

    # 统计 executor_calls == 0 的场景
    zero_executor_scenarios = [
        t for t in guard_rejection_scenarios
        if t.get("executor_calls", 1) == 0
    ]

    return {
        "guard_rejection_count": len(guard_rejection_scenarios),
        "zero_executor_calls_count": len(zero_executor_scenarios),
        "zero_executor_coverage": round(
            len(zero_executor_scenarios) / len(guard_rejection_scenarios), 3
        ) if guard_rejection_scenarios else 0,
    }


def calculate_recovery_metrics(traces: List[Dict]) -> Dict:
    """计算恢复指标。"""
    # 可恢复场景
    recoverable_scenarios = [t for t in traces if t.get("recoverable", False)]

    # 恢复成功的场景
    recovery_success_scenarios = [
        t for t in recoverable_scenarios
        if t.get("final_status") == "success"
    ]

    # 恢复次数统计
    recovery_counts = [t.get("recovery_count", 0) for t in recoverable_scenarios]

    return {
        "recoverable_scenario_count": len(recoverable_scenarios),
        "recovery_success_count": len(recovery_success_scenarios),
        "recovery_success_rate": round(
            len(recovery_success_scenarios) / len(recoverable_scenarios), 3
        ) if recoverable_scenarios else 0,
        "average_recovery_count": round(
            sum(recovery_counts) / len(recovery_counts), 2
        ) if recovery_counts else 0,
        "max_recovery_count": max(recovery_counts) if recovery_counts else 0,
    }


def calculate_reveal_metrics(traces: List[Dict]) -> Dict:
    """计算 reveal 指标。"""
    # reveal 场景
    reveal_scenarios = [t for t in traces if t.get("reveal_scenario", False)]

    # reveal 成功的场景
    reveal_success_scenarios = [
        t for t in reveal_scenarios
        if t.get("final_status") == "success"
    ]

    return {
        "reveal_scenario_count": len(reveal_scenarios),
        "reveal_success_count": len(reveal_success_scenarios),
        "reveal_success_rate": round(
            len(reveal_success_scenarios) / len(reveal_scenarios), 3
        ) if reveal_scenarios else 0,
    }


def calculate_budget_metrics(traces: List[Dict]) -> Dict:
    """计算预算耗尽指标。"""
    budget_exhaustion_scenarios = [
        t for t in traces
        if "budget_exhausted" in t.get("final_status", "") or t.get("final_status") == "timeout"
    ]

    budget_types = defaultdict(int)
    for t in budget_exhaustion_scenarios:
        status = t.get("final_status", "")
        if "decision_budget_exhausted" in status:
            budget_types["decision_calls"] += 1
        elif "action_budget_exhausted" in status:
            budget_types["atomic_action_count"] += 1
        elif "recovery_budget_exhausted" in status:
            budget_types["recovery_count"] += 1
        elif status == "timeout":
            budget_types["timeout"] += 1

    return {
        "budget_exhaustion_count": len(budget_exhaustion_scenarios),
        "budget_type_distribution": dict(budget_types),
    }


def calculate_latency_metrics(traces: List[Dict]) -> Dict:
    """计算延迟指标。"""
    latencies = [t.get("total_elapsed_ms", 0) for t in traces]

    if not latencies:
        return {
            "p50_latency_ms": 0,
            "p95_latency_ms": 0,
            "max_latency_ms": 0,
            "avg_latency_ms": 0,
        }

    sorted_latencies = sorted(latencies)
    n = len(sorted_latencies)

    return {
        "p50_latency_ms": round(sorted_latencies[int(n * 0.5)], 2),
        "p95_latency_ms": round(sorted_latencies[int(n * 0.95)], 2),
        "max_latency_ms": round(max(latencies), 2),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
    }


def summarize_benchmarks(
    traces_path: str,
    output_json_path: str,
    output_csv_path: str,
):
    """汇总 benchmark 指标。"""
    # 加载 traces
    traces = load_traces(traces_path)
    print(f"Loaded {len(traces)} traces from {traces_path}")

    # 计算各类指标
    metrics = {
        "basic": calculate_basic_metrics(traces),
        "category": calculate_category_metrics(traces),
        "dimension": calculate_dimension_metrics(traces),
        "safety": calculate_safety_metrics(traces),
        "recovery": calculate_recovery_metrics(traces),
        "reveal": calculate_reveal_metrics(traces),
        "budget": calculate_budget_metrics(traces),
        "latency": calculate_latency_metrics(traces),
    }

    # 输出 JSON
    os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    print(f"Metrics written to {output_json_path}")

    # 输出 CSV
    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
    with open(output_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # 写入基本指标
        writer.writerow(["Metric", "Value"])
        for key, value in metrics["basic"].items():
            writer.writerow([key, value])

        # 写入安全指标
        writer.writerow([])
        writer.writerow(["Safety Metrics", ""])
        for key, value in metrics["safety"].items():
            writer.writerow([key, value])

        # 写入恢复指标
        writer.writerow([])
        writer.writerow(["Recovery Metrics", ""])
        for key, value in metrics["recovery"].items():
            writer.writerow([key, value])

        # 写入 reveal 指标
        writer.writerow([])
        writer.writerow(["Reveal Metrics", ""])
        for key, value in metrics["reveal"].items():
            writer.writerow([key, value])

        # 写入预算指标
        writer.writerow([])
        writer.writerow(["Budget Metrics", ""])
        for key, value in metrics["budget"].items():
            writer.writerow([key, value])

        # 写入延迟指标
        writer.writerow([])
        writer.writerow(["Latency Metrics", ""])
        for key, value in metrics["latency"].items():
            writer.writerow([key, value])

    print(f"CSV written to {output_csv_path}")

    return metrics


if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    traces_path = os.path.join(project_root, "artifacts", "benchmark_traces.jsonl")
    output_json_path = os.path.join(project_root, "artifacts", "benchmark_metrics.json")
    output_csv_path = os.path.join(project_root, "artifacts", "benchmark_metrics.csv")

    summarize_benchmarks(traces_path, output_json_path, output_csv_path)
