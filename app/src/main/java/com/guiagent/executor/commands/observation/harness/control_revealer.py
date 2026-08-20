# -*- coding: utf-8 -*-
"""Control Revealer — 隐藏控件唤出策略，带三态状态机。

状态：active / probation / stale
- active: 正常可用，优先选择
- probation: 连续 2 次语义失败，降低排序
- stale: 连续 3 次失败或成功率过低，停用

区分语义失败（目标未出现）和基础设施失败（设备断连/超时），
避免网络抖动污染策略成功率统计。
"""
import json
import os
import time
from dataclasses import dataclass, field
from typing import Literal, Optional

from ..candidates.schemas import CandidateMap


# ─────────────── 策略记录 ───────────────

@dataclass
class RevealStrategyRecord:
    """唤出策略记录。"""
    strategy_id: str
    app: str
    activity_pattern: Optional[str] = None
    orientation: Optional[str] = None  # portrait / landscape
    actions: list = field(default_factory=list)  # [{"type": "tap", "x": 0.5, "y": 0.5, "wait_ms": 700}, ...]
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    latency_ema_ms: Optional[float] = None  # 指数移动平均延迟
    last_verified_at: Optional[float] = None
    state: Literal["active", "probation", "stale"] = "active"

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.5  # 先验概率
        return self.success_count / total

    def record_success(self, latency_ms: float):
        """记录成功。"""
        self.success_count += 1
        self.consecutive_failures = 0
        self.last_verified_at = time.time()

        # 更新 EMA 延迟
        if self.latency_ema_ms is None:
            self.latency_ema_ms = latency_ms
        else:
            self.latency_ema_ms = 0.7 * self.latency_ema_ms + 0.3 * latency_ms

        # 状态恢复
        if self.state == "probation" and self.consecutive_failures == 0:
            self.state = "active"

    def record_semantic_failure(self):
        """记录语义失败（动作正常但目标未出现）。"""
        self.failure_count += 1
        self.consecutive_failures += 1

        # 状态降级
        if self.consecutive_failures >= 2 and self.state == "active":
            self.state = "probation"
        if self.consecutive_failures >= 3 and self.state in ("active", "probation"):
            self.state = "stale"

    def record_infrastructure_failure(self):
        """记录基础设施失败（设备断连/超时等，不污染统计）。"""
        # 不计入 success/failure 统计
        pass


# ─────────────── 策略管理器 ───────────────

class RevealStrategyManager:
    """唤出策略管理器。"""

    def __init__(self, storage_path: Optional[str] = None):
        self._strategies = {}  # strategy_id -> RevealStrategyRecord
        self._storage_path = storage_path

        # 加载已有策略
        if storage_path and os.path.exists(storage_path):
            self._load()

    def register(self, record: RevealStrategyRecord):
        """注册新策略。"""
        self._strategies[record.strategy_id] = record
        self._save()

    def get_strategy(self, strategy_id: str) -> Optional[RevealStrategyRecord]:
        """获取策略。"""
        return self._strategies.get(strategy_id)

    def get_active_strategies(self, app: str) -> list:
        """获取 App 的活跃策略（按成功率排序）。"""
        candidates = []
        for s in self._strategies.values():
            if s.app == app and s.state != "stale":
                candidates.append(s)

        # 排序：active > probation，然后按成功率降序，延迟升序
        candidates.sort(key=lambda s: (
            0 if s.state == "active" else 1,
            -s.success_rate,
            s.latency_ema_ms or 9999,
        ))

        return candidates

    def select_best(self, app: str) -> Optional[RevealStrategyRecord]:
        """选择最佳策略。"""
        strategies = self.get_active_strategies(app)
        return strategies[0] if strategies else None


# ─────────────── Control Revealer ───────────────

# 默认唤出序列
DEFAULT_REVEAL_SEQUENCE = [
    {"type": "tap", "x": 0.50, "y": 0.50, "wait_ms": 700},
    {"type": "remote_key", "key": "DPAD_CENTER", "wait_ms": 700},
    {"type": "remote_key", "key": "MENU", "wait_ms": 900},
]


class ControlRevealer:
    """隐藏控件唤出器。"""

    def __init__(self, strategy_manager: Optional[RevealStrategyManager] = None):
        self._manager = strategy_manager or RevealStrategyManager()
        self._action_executor = None  # 外部注入的动作执行器

    def set_action_executor(self, executor):
        """设置动作执行器（外部注入）。"""
        self._action_executor = executor

    async def reveal(
        self,
        app: str,
        screenshot_provider=None,
        candidate_builder=None,
    ) -> tuple[bool, Optional[CandidateMap]]:
        """执行唤出。

        Args:
            app: App 名称（aiqiyi/tencent/quark）
            screenshot_provider: 截图提供者
            candidate_builder: 候选构建器

        Returns:
            (success: bool, candidate_map: Optional[CandidateMap])
        """
        # 选择策略
        strategy = self._manager.select_best(app)
        if strategy is None:
            # 使用默认序列
            strategy = RevealStrategyRecord(
                strategy_id="default",
                app=app,
                actions=DEFAULT_REVEAL_SEQUENCE,
            )

        # 执行唤出序列
        for step_idx, action in enumerate(strategy.actions):
            action_type = action.get("type")
            wait_ms = action.get("wait_ms", 500)

            # 执行动作
            start = time.time()
            try:
                if action_type == "tap":
                    x = int(action["x"] * 1280)
                    y = int(action["y"] * 800)
                    if self._action_executor:
                        self._action_executor.tap(x, y)
                elif action_type == "remote_key":
                    if self._action_executor:
                        self._action_executor.remote_key(action["key"])
                else:
                    continue
            except Exception as e:
                # 基础设施失败，不污染统计
                strategy.record_infrastructure_failure()
                continue

            # 等待动画
            time.sleep(wait_ms / 1000.0)
            latency_ms = (time.time() - start) * 1000

            # 验证控制条是否出现
            try:
                if screenshot_provider and candidate_builder:
                    frame = screenshot_provider.capture()
                    candidate_map = candidate_builder.build(
                        frame=frame,
                        package=app,
                    )

                    # 检查候选数是否显著增加（控制条出现的信号）
                    if len(candidate_map.candidates) > 5:
                        strategy.record_success(latency_ms)
                        return True, candidate_map
            except Exception:
                pass

        # 全部失败
        strategy.record_semantic_failure()
        return False, None


# ─────────────── 持久化 ───────────────

def _default_manager_path() -> str:
    """默认策略存储路径。"""
    return os.path.join(os.path.dirname(__file__), "..", "data", "reveal_strategies.json")


class RevealStrategyManager:
    """唤出策略管理器（带持久化）。"""

    def __init__(self, storage_path: Optional[str] = None):
        self._strategies = {}
        self._storage_path = storage_path or _default_manager_path()

        if os.path.exists(self._storage_path):
            self._load()

    def register(self, record: RevealStrategyRecord):
        """注册策略。"""
        self._strategies[record.strategy_id] = record
        self._save()

    def get_strategy(self, strategy_id: str) -> Optional[RevealStrategyRecord]:
        return self._strategies.get(strategy_id)

    def get_active_strategies(self, app: str) -> list:
        """获取活跃策略（按成功率排序）。"""
        candidates = [
            s for s in self._strategies.values()
            if s.app == app and s.state != "stale"
        ]
        candidates.sort(key=lambda s: (
            0 if s.state == "active" else 1,
            -s.success_rate,
            s.latency_ema_ms or 9999,
        ))
        return candidates

    def select_best(self, app: str) -> Optional[RevealStrategyRecord]:
        strategies = self.get_active_strategies(app)
        return strategies[0] if strategies else None

    def _load(self):
        """从文件加载策略。"""
        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("strategies", []):
                record = RevealStrategyRecord(
                    strategy_id=item["strategy_id"],
                    app=item["app"],
                    actions=item.get("actions", []),
                    success_count=item.get("success_count", 0),
                    failure_count=item.get("failure_count", 0),
                    consecutive_failures=item.get("consecutive_failures", 0),
                    latency_ema_ms=item.get("latency_ema_ms"),
                    last_verified_at=item.get("last_verified_at"),
                    state=item.get("state", "active"),
                )
                self._strategies[record.strategy_id] = record
        except Exception:
            pass

    def _save(self):
        """保存到文件。"""
        try:
            data = {
                "strategies": [
                    {
                        "strategy_id": s.strategy_id,
                        "app": s.app,
                        "actions": s.actions,
                        "success_count": s.success_count,
                        "failure_count": s.failure_count,
                        "consecutive_failures": s.consecutive_failures,
                        "latency_ema_ms": s.latency_ema_ms,
                        "last_verified_at": s.last_verified_at,
                        "state": s.state,
                    }
                    for s in self._strategies.values()
                ]
            }
            os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
