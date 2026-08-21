# -*- coding: utf-8 -*-
"""Control Revealer — 隐藏控件唤出策略规划器。

职责边界（P0）：
  - ControlRevealer 不直接执行动作，不持有 Executor/Verifier
  - 它仅输出 RevealPlan(strategy_id, list[ActionSpec])
  - action_loop 逐条执行 plan.actions，每条走完整 guard→execute→verify
  - 所有 reveal 动作计入 atomic_action_count 和全局 max_steps

状态机：active / probation / stale
  - 所有阈值由 RevealPolicyConfig 管理，不散落硬编码
  - 基础设施失败不污染统计

策略过滤：app + activity_pattern(fnmatch) + orientation

本模块无任何外部依赖（不依赖 VLM / ADB / 具体 App）。
"""
import fnmatch
import json
import os
import time
from dataclasses import dataclass, field
from typing import Literal, Optional, Set

from .schemas import ActionSpec, RevealPlan, RevealPolicyConfig, UiState
from .types import BBox


# ─────────────── 策略记录 ───────────────

@dataclass
class RevealStrategyRecord:
    """唤出策略记录。所有阈值由 RevealPolicyConfig 注入。"""
    strategy_id: str
    app: str
    activity_pattern: Optional[str] = None
    orientation: Optional[str] = None
    actions: list = field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    latency_ema_ms: Optional[float] = None
    last_verified_at: Optional[float] = None
    state: Literal["active", "probation", "stale"] = "active"
    version: int = 1
    history: list = field(default_factory=list)
    _recent_outcomes: list = field(default_factory=list, repr=False)
    policy: Optional[RevealPolicyConfig] = field(default=None, repr=False)

    def _policy(self) -> RevealPolicyConfig:
        return self.policy or RevealPolicyConfig()

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.5
        return self.success_count / total

    def record_success(self, latency_ms: float):
        p = self._policy()
        self.success_count += 1
        self.consecutive_failures = 0
        self.last_verified_at = time.time()

        if self.latency_ema_ms is None:
            self.latency_ema_ms = latency_ms
        else:
            self.latency_ema_ms = 0.7 * self.latency_ema_ms + 0.3 * latency_ms

        self._recent_outcomes.append("success")
        self._recent_outcomes = self._recent_outcomes[-p.stale_window_size:]

        # probation → active: 连续 recovery_success_threshold 次 success
        if self.state == "probation":
            threshold = p.recovery_success_threshold
            if len(self._recent_outcomes) >= threshold:
                last_n = self._recent_outcomes[-threshold:]
                if all(o == "success" for o in last_n):
                    self.state = "active"

    def record_semantic_failure(self):
        p = self._policy()
        self.failure_count += 1
        self.consecutive_failures += 1

        self._recent_outcomes.append("failure")
        self._recent_outcomes = self._recent_outcomes[-p.stale_window_size:]

        # 状态转移
        if self.consecutive_failures >= p.probation_threshold and self.state == "active":
            self.state = "probation"
        if self.consecutive_failures >= p.stale_consecutive_threshold and self.state in ("active", "probation"):
            self.state = "stale"

        # rolling-window stale
        if len(self._recent_outcomes) >= p.stale_window_size:
            recent_failures = sum(
                1 for o in self._recent_outcomes[-p.stale_window_size:]
                if o == "failure"
            )
            if recent_failures >= p.stale_window_failure_threshold and self.state != "stale":
                self.state = "stale"

    def record_infrastructure_failure(self):
        """基础设施失败（设备断连/超时等），不污染统计。"""
        pass


# ─────────────── 策略管理器 ───────────────

def _default_manager_path() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "data", "reveal_strategies.json")


class RevealStrategyManager:
    """唤出策略管理器（带持久化）。"""

    def __init__(self, storage_path: Optional[str] = None,
                 policy: Optional[RevealPolicyConfig] = None):
        self._strategies = {}
        self._storage_path = storage_path or _default_manager_path()
        self._policy = policy or RevealPolicyConfig()
        if os.path.exists(self._storage_path):
            self._load()

    def register(self, record: RevealStrategyRecord):
        """注册策略。stale 后新版本保留历史。"""
        record.policy = self._policy
        base_id = record.strategy_id
        max_version = 0
        stale_found = False
        for sid, s in self._strategies.items():
            if sid == base_id or sid.startswith(f"{base_id}_v"):
                if s.version > max_version:
                    max_version = s.version
                if s.state == "stale":
                    stale_found = True
        if stale_found and max_version > 0:
            record.version = max_version + 1
            record.strategy_id = f"{base_id}_v{record.version}"
        elif max_version > 0:
            record.version = max_version
        self._strategies[record.strategy_id] = record
        self._save()

    def get_strategy(self, strategy_id: str) -> Optional[RevealStrategyRecord]:
        return self._strategies.get(strategy_id)

    def get_active_strategies(
        self,
        app: str,
        activity: Optional[str] = None,
        orientation: Optional[str] = None,
    ) -> list:
        candidates = []
        for s in self._strategies.values():
            if s.app != app or s.state == "stale":
                continue
            if s.activity_pattern and activity:
                if not fnmatch.fnmatch(activity, s.activity_pattern):
                    continue
            if s.orientation and orientation and s.orientation != orientation:
                continue
            candidates.append(s)
        candidates.sort(key=lambda s: (
            0 if s.state == "active" else 1,
            -s.success_rate,
            s.latency_ema_ms or 9999,
        ))
        return candidates

    def select_best(
        self,
        app: str,
        activity: Optional[str] = None,
        orientation: Optional[str] = None,
    ) -> Optional[RevealStrategyRecord]:
        strategies = self.get_active_strategies(app, activity, orientation)
        return strategies[0] if strategies else None

    def _load(self):
        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("strategies", []):
                record = RevealStrategyRecord(
                    strategy_id=item["strategy_id"],
                    app=item["app"],
                    activity_pattern=item.get("activity_pattern"),
                    orientation=item.get("orientation"),
                    actions=item.get("actions", []),
                    success_count=item.get("success_count", 0),
                    failure_count=item.get("failure_count", 0),
                    consecutive_failures=item.get("consecutive_failures", 0),
                    latency_ema_ms=item.get("latency_ema_ms"),
                    last_verified_at=item.get("last_verified_at"),
                    state=item.get("state", "active"),
                    version=item.get("version", 1),
                    history=item.get("history", []),
                    _recent_outcomes=item.get("_recent_outcomes", []),
                    policy=self._policy,
                )
                self._strategies[record.strategy_id] = record
        except Exception:
            pass

    def _save(self):
        try:
            data = {
                "strategies": [
                    {
                        "strategy_id": s.strategy_id,
                        "app": s.app,
                        "activity_pattern": s.activity_pattern,
                        "orientation": s.orientation,
                        "actions": s.actions,
                        "success_count": s.success_count,
                        "failure_count": s.failure_count,
                        "consecutive_failures": s.consecutive_failures,
                        "latency_ema_ms": s.latency_ema_ms,
                        "last_verified_at": s.last_verified_at,
                        "state": s.state,
                        "version": s.version,
                        "history": s.history,
                        "_recent_outcomes": s._recent_outcomes,
                    }
                    for s in self._strategies.values()
                ]
            }
            os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


# ─────────────── Action dict → ActionSpec ───────────────

def _action_dict_to_spec(action: dict, screen_size: tuple) -> ActionSpec:
    """将策略 action dict 转为 ActionSpec。"""
    t = action.get("type", "")
    if t == "tap":
        x = action.get("x", 0.5)
        y = action.get("y", 0.5)
        cx = int(x * screen_size[0])
        cy = int(y * screen_size[1])
        half = 5
        bbox = BBox(
            x1=max(0, cx - half),
            y1=max(0, cy - half),
            x2=min(screen_size[0], cx + half),
            y2=min(screen_size[1], cy + half),
        )
        return ActionSpec(
            action_type="tap_visual",
            bbox_px=bbox,
            target_role="reveal_tap",
        )
    elif t == "remote_key":
        return ActionSpec(action_type="remote_key", key=action.get("key", "DPAD_CENTER"))
    elif t == "media_key":
        return ActionSpec(action_type="media_key", key=action.get("key", "MEDIA_PLAY_PAUSE"))
    elif t == "swipe":
        return ActionSpec(action_type="swipe", direction=action.get("direction", "up"))
    else:
        return ActionSpec(action_type="back")


# ─────────────── Control Revealer ───────────────

class ControlRevealer:
    """唤出策略规划器。

    P0 约束：
      - 不直接执行动作
      - 不持有 Executor/Verifier
      - 仅输出 RevealPlan(strategy_id, list[ActionSpec])
    """

    def __init__(self,
                 strategy_manager: Optional[RevealStrategyManager] = None,
                 policy: Optional[RevealPolicyConfig] = None):
        self._policy = policy or RevealPolicyConfig()
        self._manager = strategy_manager or RevealStrategyManager(policy=self._policy)

    def plan(
        self,
        app: str,
        current_state: UiState,
        *,
        activity: str = "",
        orientation: str = "landscape",
    ) -> RevealPlan:
        """生成唤出计划。

        Returns:
            RevealPlan(strategy_id, list[ActionSpec])

        action_loop 负责逐条执行 plan.actions。
        """
        strategy = self._manager.select_best(app, activity, orientation)
        is_generic = False

        if strategy is None:
            strategy = type('_FallbackStrategy', (), {
                'strategy_id': 'generic',
                'actions': self._policy.default_reveal_actions,
            })()
            is_generic = True

        strategy_id = strategy.strategy_id
        screen_size = current_state.screen_size

        actions = []
        for action_dict in strategy.actions[:self._policy.max_recovery_steps]:
            spec = _action_dict_to_spec(action_dict, screen_size)
            actions.append(spec)

        return RevealPlan(strategy_id=strategy_id, actions=actions)

    def record_success(self, strategy_id: str, latency_ms: float):
        """记录策略成功。由 action_loop 在 verify success 后调用。"""
        record = self._manager.get_strategy(strategy_id)
        if record:
            record.record_success(latency_ms)

    def record_semantic_failure(self, strategy_id: str):
        """记录策略语义失败。由 action_loop 在 plan 执行完毕但未 verify success 后调用。"""
        record = self._manager.get_strategy(strategy_id)
        if record:
            record.record_semantic_failure()

    def record_infrastructure_failure(self, strategy_id: str):
        """记录基础设施失败。不污染统计。"""
        record = self._manager.get_strategy(strategy_id)
        if record:
            record.record_infrastructure_failure()
