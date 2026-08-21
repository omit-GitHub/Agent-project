# -*- coding: utf-8 -*-
"""Benchmark Scenario Registry — 声明式场景注册表。

定义 BenchmarkScenario 数据结构和注册机制。
每个场景包含完整的输入、预期输出和配置。
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class ScenarioTimingConfig:
    """场景的模拟延迟配置。"""
    observe_ms: float = 0.0
    candidate_generate_ms: float = 0.0
    decision_ms: float = 0.0
    execute_ms: float = 0.0
    verify_ms: float = 0.0
    recovery_ms: float = 0.0


@dataclass
class BenchmarkScenario:
    """单个 benchmark 场景的完整定义。"""
    # 基本信息
    scenario_id: str
    category: str  # normal / invalid_action / sensitive_action / hidden_controls / recovery / budget_exhaustion
    dimension: str  # 具体安全语义或边界维度
    description: str

    # 初始状态
    initial_state: Any  # UiState

    # 行为定义
    decision_sequence: list  # Mock DecisionSource 的动作序列

    # 预期结果（必须在有默认值的字段之前）
    expected_outcome: str  # success / blocked / failed / timeout / needs_refinement / etc.

    # 可选配置
    executor_behavior: Optional[Callable] = None  # Mock Executor 的行为
    verifier_behavior: Optional[Callable] = None  # Mock Verifier 的行为
    timing_config: Optional[ScenarioTimingConfig] = None
    control_revealer_config: Optional[dict] = None  # ControlRevealer 配置
    recovery_planner_config: Optional[dict] = None  # RecoveryPlanner 配置
    max_steps: int = 8
    max_decision_calls: int = 4
    recovery_budget: int = 2
    deadline_ms: int = 20000

    # 预期结果细节
    expected_executor_calls: int = 0
    expected_failure_reason: Optional[str] = None
    expected_decision_calls: Optional[int] = None
    expected_atomic_action_count: Optional[int] = None
    expected_recovery_count: Optional[int] = None

    # 恢复与 reveal 标记
    recoverable: bool = False  # 是否为可恢复场景
    reveal_scenario: bool = False  # 是否为 reveal 场景

    # 对照实验标记
    baseline_should_execute: bool = False  # baseline 模式下是否应该执行错误动作


# 场景注册表
_SCENARIO_REGISTRY = {}


def register_scenario(scenario: BenchmarkScenario):
    """注册一个 benchmark 场景。"""
    if scenario.scenario_id in _SCENARIO_REGISTRY:
        raise ValueError(f"Scenario {scenario.scenario_id} already registered")
    _SCENARIO_REGISTRY[scenario.scenario_id] = scenario


def get_scenario(scenario_id: str) -> BenchmarkScenario:
    """获取指定场景。"""
    if scenario_id not in _SCENARIO_REGISTRY:
        raise KeyError(f"Scenario {scenario_id} not found")
    return _SCENARIO_REGISTRY[scenario_id]


def get_all_scenarios() -> list:
    """获取所有已注册场景。"""
    return list(_SCENARIO_REGISTRY.values())


def get_scenarios_by_category(category: str) -> list:
    """按类别获取场景。"""
    return [s for s in _SCENARIO_REGISTRY.values() if s.category == category]


def get_scenarios_by_dimension(dimension: str) -> list:
    """按维度获取场景。"""
    return [s for s in _SCENARIO_REGISTRY.values() if s.dimension == dimension]


def clear_registry():
    """清空注册表（用于测试）。"""
    _SCENARIO_REGISTRY.clear()
