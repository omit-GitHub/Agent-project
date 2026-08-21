# -*- coding: utf-8 -*-
"""Control Revealer — 隐藏控件唤出策略，带三态状态机。

状态：active / probation / stale
- active: 正常可用，优先选择
- probation: 连续 2 次语义失败，降低排序
- stale: 连续 3 次失败或 rolling window 中 5 次 ≥ 4 次失败，停用

区分语义失败（目标未出现）和基础设施失败（设备断连/超时），
避免网络抖动污染策略成功率统计。

关键约束：
  - reveal 不允许绕过 Harness 直接执行 raw action dict
  - 通过注入 ActionExecutor + StateVerifier 完成唤出
  - 成功只能由 control_bar_visible / 目标候选角色 / 指定 OCR token 证明
  - 策略按 app + activity_pattern + orientation 过滤
  - stale 后新版本保留历史

本模块无任何外部依赖（不依赖 VLM / ADB / 具体 App）。
"""
import fnmatch
import json
import os
import time
from dataclasses import dataclass, field
from typing import Literal, Optional, Set

from .schemas import ActionSpec, ActionResult, UiState
from .types import BBox


# ─────────────── 策略记录 ───────────────

@dataclass
class RevealStrategyRecord:
    """唤出策略记录。

    状态机：
      - active → probation: consecutive_failures >= 2
      - probation → active: rolling window 中最近 2 次均为 success
      - probation → stale: consecutive_failures >= 3
      - active → stale: consecutive_failures >= 3，或 rolling window 5 次中 ≥ 4 次 failure
      - record_infrastructure_failure(): 不修改任何计数器
    """
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

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.5
        return self.success_count / total

    def record_success(self, latency_ms: float):
        self.success_count += 1
        self.consecutive_failures = 0
        self.last_verified_at = time.time()

        if self.latency_ema_ms is None:
            self.latency_ema_ms = latency_ms
        else:
            self.latency_ema_ms = 0.7 * self.latency_ema_ms + 0.3 * latency_ms

        # 更新 rolling window
        self._recent_outcomes.append("success")
        self._recent_outcomes = self._recent_outcomes[-5:]

        # probation → active: 最近 2 次均为 success
        if self.state == "probation":
            if len(self._recent_outcomes) >= 2:
                last_two = self._recent_outcomes[-2:]
                if all(o == "success" for o in last_two):
                    self.state = "active"

    def record_semantic_failure(self):
        self.failure_count += 1
        self.consecutive_failures += 1

        # 更新 rolling window
        self._recent_outcomes.append("failure")
        self._recent_outcomes = self._recent_outcomes[-5:]

        # 状态转移
        if self.consecutive_failures >= 2 and self.state == "active":
            self.state = "probation"
        if self.consecutive_failures >= 3 and self.state in ("active", "probation"):
            self.state = "stale"

        # rolling-window stale: 最近 5 次中 ≥ 4 次 failure
        if len(self._recent_outcomes) >= 5:
            recent_failures = sum(1 for o in self._recent_outcomes[-5:] if o == "failure")
            if recent_failures >= 4 and self.state != "stale":
                self.state = "stale"

    def record_infrastructure_failure(self):
        """基础设施失败（设备断连/超时等，不污染统计）。"""
        pass


# ─────────────── 策略管理器 ───────────────

def _default_manager_path() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "data", "reveal_strategies.json")


class RevealStrategyManager:
    """唤出策略管理器（带持久化）。"""

    def __init__(self, storage_path: Optional[str] = None):
        self._strategies = {}
        self._storage_path = storage_path or _default_manager_path()

        if os.path.exists(self._storage_path):
            self._load()

    def register(self, record: RevealStrategyRecord):
        """注册策略。stale 后新版本保留历史。

        查找所有与 base_id 匹配的策略（含 _vN 后缀），
        取最高版本号 + 1。
        """
        base_id = record.strategy_id
        # 查找所有匹配 base_id 或 base_id_vN 的策略
        max_version = 0
        stale_found = False
        for sid, s in self._strategies.items():
            if sid == base_id or sid.startswith(f"{base_id}_v"):
                if s.version > max_version:
                    max_version = s.version
                if s.state == "stale":
                    stale_found = True

        if stale_found and max_version > 0:
            # 有 stale 版本 → 创建新版本
            record.version = max_version + 1
            record.strategy_id = f"{base_id}_v{record.version}"
        elif max_version > 0:
            # 有非 stale 版本 → 更新版本号
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
        """获取活跃策略，按 app + activity_pattern + orientation 过滤。"""
        candidates = []
        for s in self._strategies.values():
            if s.app != app or s.state == "stale":
                continue
            # activity_pattern 过滤（fnmatch）
            if s.activity_pattern and activity:
                if not fnmatch.fnmatch(activity, s.activity_pattern):
                    continue
            # orientation 过滤
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


# ─────────────── Control Revealer ───────────────

DEFAULT_REVEAL_SEQUENCE = [
    {"type": "tap", "x": 0.50, "y": 0.50, "wait_ms": 700},
    {"type": "remote_key", "key": "DPAD_CENTER", "wait_ms": 700},
    {"type": "remote_key", "key": "MENU", "wait_ms": 900},
]


def _action_dict_to_spec(action: dict, screen_size: tuple) -> ActionSpec:
    """将策略 action dict 转为 ActionSpec（不绕过 Harness）。"""
    t = action.get("type", "")
    if t == "tap":
        x = action.get("x", 0.5)
        y = action.get("y", 0.5)
        cx = int(x * screen_size[0])
        cy = int(y * screen_size[1])
        # 构造一个小 bbox（10x10 像素）
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
        return ActionSpec(
            action_type="remote_key",
            key=action.get("key", "DPAD_CENTER"),
        )
    elif t == "media_key":
        return ActionSpec(
            action_type="media_key",
            key=action.get("key", "MEDIA_PLAY_PAUSE"),
        )
    elif t == "swipe":
        return ActionSpec(
            action_type="swipe",
            direction=action.get("direction", "up"),
        )
    else:
        # 未知类型 → back（安全回退）
        return ActionSpec(action_type="back")


def _verify_reveal_success(
    before_state: UiState,
    after_state: UiState,
    target_role: Optional[str] = None,
    expected_ocr_tokens: Optional[set] = None,
) -> tuple:
    """验证唤出是否成功。

    成功条件（任一满足即可）：
      1. control_bar_visible: false → true
      2. after.selected_role == target_role
      3. expected_ocr_tokens ⊂ (after.ocr_tokens - before.ocr_tokens)

    Returns:
        (success: bool, reason: str)
    """
    # 1. control_bar_visible: false → true
    if not before_state.control_bar_visible and after_state.control_bar_visible:
        return True, "control_bar became visible"

    # 2. 目标候选角色出现
    if target_role and after_state.selected_role == target_role:
        return True, f"target role '{target_role}' appeared"

    # 3. 指定 OCR token 出现
    if expected_ocr_tokens:
        new_tokens = after_state.ocr_tokens - before_state.ocr_tokens
        matched = expected_ocr_tokens & new_tokens
        if matched:
            return True, f"expected OCR tokens appeared: {sorted(matched)}"

    return False, "no reveal success signal"


class ControlRevealer:
    """隐藏控件唤出器。

    关键约束：
      - 不允许绕过 Harness 直接执行 raw action dict
      - 通过注入 ActionExecutor + StateVerifier 完成唤出
      - executor 必须匹配 execute(ActionSpec, UiState) -> ActionResult
      - verifier 必须匹配 verify(UiState, UiState, ActionSpec) -> VerificationResult
    """

    def __init__(self, strategy_manager: Optional[RevealStrategyManager] = None):
        self._manager = strategy_manager or RevealStrategyManager()

    def reveal(
        self,
        app: str,
        executor,
        verifier,
        current_state: UiState,
        *,
        activity: str = "",
        orientation: str = "landscape",
        target_role: Optional[str] = None,
        expected_ocr_tokens: Optional[Set[str]] = None,
        max_steps: int = 5,
    ) -> tuple:
        """执行唤出。

        Args:
            app: 应用包名
            executor: ActionExecutor Protocol 实现（execute(ActionSpec, UiState) -> ActionResult）
            verifier: StateVerifier Protocol 实现（verify(before, after, action) -> VerificationResult）
            current_state: 当前 UI 状态
            activity: 当前 Activity（用于策略过滤）
            orientation: 屏幕方向（用于策略过滤）
            target_role: 目标控件角色
            expected_ocr_tokens: 期望出现的 OCR token 集合
            max_steps: 最大唤出步数

        Returns:
            (success: bool, candidate_map_or_None, strategy_id: str)
        """
        strategy = self._manager.select_best(app, activity, orientation)
        is_generic = False

        if strategy is None:
            # 无匹配策略 → 使用 generic default
            strategy = RevealStrategyRecord(
                strategy_id="generic",
                app=app,
                actions=DEFAULT_REVEAL_SEQUENCE,
            )
            is_generic = True

        strategy_id = strategy.strategy_id
        screen_size = current_state.screen_size

        for step_idx, action_dict in enumerate(strategy.actions):
            if step_idx >= max_steps:
                break

            wait_ms = action_dict.get("wait_ms", 500)

            # 将 action dict 转为 ActionSpec（不绕过 Harness）
            action_spec = _action_dict_to_spec(action_dict, screen_size)

            # 通过注入的 executor 执行
            before_state = current_state
            start = time.time()
            try:
                result = executor.execute(action_spec, current_state)
            except Exception:
                strategy.record_infrastructure_failure()
                continue

            if not result.ok:
                strategy.record_infrastructure_failure()
                continue

            after_state = result.after_state
            latency_ms = (time.time() - start) * 1000

            # 验证唤出成功（基于状态转移，不是 candidate 数量）
            success, reason = _verify_reveal_success(
                before_state, after_state,
                target_role=target_role,
                expected_ocr_tokens=expected_ocr_tokens,
            )

            if success:
                strategy.record_success(latency_ms)
                # 更新 current_state
                current_state = after_state
                return True, after_state.candidate_map, strategy_id

            # 更新 current_state 继续下一步
            current_state = after_state

        strategy.record_semantic_failure()
        return False, None, strategy_id
