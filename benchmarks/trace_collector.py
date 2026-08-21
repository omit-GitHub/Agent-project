# -*- coding: utf-8 -*-
"""Trace Collector — 跟踪收集器。

为 action_loop 提供可选的 trace collector / observer。
记录每个阶段的耗时、Guard 拒绝详情等信息。
"""
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PhaseTiming:
    """单个阶段的耗时记录。"""
    phase_name: str
    start_ms: float
    end_ms: float
    duration_ms: float
    deadline_remaining_ms: Optional[float] = None


@dataclass
class GuardRejectionDetail:
    """Guard 拒绝详情。"""
    step_idx: int
    action_type: str
    error_code: str
    risk_level: str
    requires_refinement: bool
    reason: str


@dataclass
class ScenarioTrace:
    """单个场景的完整 trace。"""
    scenario_id: str
    category: str
    dimension: str

    # 最终结果
    final_status: str
    failure_reason: Optional[str] = None

    # 预算统计
    decision_calls: int = 0
    atomic_action_count: int = 0
    recovery_count: int = 0
    executor_calls: int = 0

    # 时间统计
    total_elapsed_ms: float = 0.0
    phase_timings: list = field(default_factory=list)  # list[PhaseTiming]

    # Guard 拒绝详情
    guard_rejections: list = field(default_factory=list)  # list[GuardRejectionDetail]

    # 详细步骤
    steps: list = field(default_factory=list)

    # 恢复与 reveal 标记
    recoverable: bool = False
    reveal_scenario: bool = False

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "scenario_id": self.scenario_id,
            "category": self.category,
            "dimension": self.dimension,
            "final_status": self.final_status,
            "failure_reason": self.failure_reason,
            "decision_calls": self.decision_calls,
            "atomic_action_count": self.atomic_action_count,
            "recovery_count": self.recovery_count,
            "executor_calls": self.executor_calls,
            "total_elapsed_ms": self.total_elapsed_ms,
            "phase_timings": [
                {
                    "phase_name": pt.phase_name,
                    "start_ms": pt.start_ms,
                    "end_ms": pt.end_ms,
                    "duration_ms": pt.duration_ms,
                    "deadline_remaining_ms": pt.deadline_remaining_ms,
                }
                for pt in self.phase_timings
            ],
            "guard_rejections": [
                {
                    "step_idx": gr.step_idx,
                    "action_type": gr.action_type,
                    "error_code": gr.error_code,
                    "risk_level": gr.risk_level,
                    "requires_refinement": gr.requires_refinement,
                    "reason": gr.reason,
                }
                for gr in self.guard_rejections
            ],
            "steps": self.steps,
            "recoverable": self.recoverable,
            "reveal_scenario": self.reveal_scenario,
        }


class TraceCollector:
    """跟踪收集器。"""

    def __init__(self, deadline_ms: int = 20000):
        self.deadline_ms = deadline_ms
        self.start_time_ms = time.time() * 1000
        self.phase_timings = []
        self.guard_rejections = []
        self.current_phase_start = None

    def get_deadline_remaining_ms(self) -> float:
        """获取剩余 deadline。"""
        elapsed = time.time() * 1000 - self.start_time_ms
        return max(0, self.deadline_ms - elapsed)

    def start_phase(self, phase_name: str):
        """开始一个阶段。"""
        self.current_phase_start = time.time() * 1000

    def end_phase(self, phase_name: str):
        """结束一个阶段。"""
        if self.current_phase_start is None:
            return

        end_time = time.time() * 1000
        duration = end_time - self.current_phase_start

        self.phase_timings.append(PhaseTiming(
            phase_name=phase_name,
            start_ms=self.current_phase_start,
            end_ms=end_time,
            duration_ms=duration,
            deadline_remaining_ms=self.get_deadline_remaining_ms(),
        ))

        self.current_phase_start = None

    def record_guard_rejection(self, step_idx: int, action_type: str,
                                error_code: str, risk_level: str,
                                requires_refinement: bool, reason: str):
        """记录 Guard 拒绝详情。"""
        self.guard_rejections.append(GuardRejectionDetail(
            step_idx=step_idx,
            action_type=action_type,
            error_code=error_code,
            risk_level=risk_level,
            requires_refinement=requires_refinement,
            reason=reason,
        ))

    def is_deadline_exceeded(self) -> bool:
        """检查 deadline 是否已耗尽。"""
        return self.get_deadline_remaining_ms() <= 0


class MockClock:
    """模拟时钟，用于测试。"""

    def __init__(self, start_time: float = 0.0):
        self.current_time = start_time

    def time(self) -> float:
        """获取当前时间（秒）。"""
        return self.current_time

    def sleep(self, seconds: float):
        """模拟 sleep。"""
        self.current_time += seconds

    def advance(self, seconds: float):
        """前进时间。"""
        self.current_time += seconds
