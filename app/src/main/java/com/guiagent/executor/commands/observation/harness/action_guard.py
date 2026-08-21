# -*- coding: utf-8 -*-
"""Action Guard — VLM 输出的合法性校验层。

对每个 VLM 建议的动作进行多重前置检查，只有全部通过才允许执行。
防止误触发登录、支付、删除等不可逆操作。

校验维度：
  1. 动作类型合法性
  2. candidate_id 归属（属于当前 CandidateMap）
  3. bbox 合法性（越界、面积、位置）
  4. 页面版本兼容性（CandidateMap 未过期）
  5. 敏感操作拦截（登录/支付/删除/验证码）
  6. 重复失败候选排除（同一 screen_version 下不再点击已失败候选）
"""
import re
from dataclasses import dataclass, field
from typing import Literal, Optional

from ..candidates.schemas import CandidateMap, UiCandidate, PixelBBox
from .schemas import ActionSpec, UiState


# ─────────────── 敏感词库 ───────────────

SENSITIVE_KEYWORDS = [
    # 支付/购买
    "付款", "支付", "充值", "订阅", "购买", "扣费", "开通会员", "VIP",
    # 不可逆操作
    "删除", "卸载", "清除", "格式化", "注销", "退出登录",
    # 认证/安全
    "密码", "验证码", "授权", "登录", "注册", "短信",
    # 发送/提交
    "发送", "提交", "确认", "确定",
]

# 显式敏感 risk_category（来自候选字段，优先级高于 subgoal 关键词）
SENSITIVE_RISK_CATEGORIES = {
    "payment", "delete", "send", "logout",
    "password", "authorization", "unsubscribe",
    "purchase", "refund", "ban", "reset",
}

# 敏感页面类型（这些页面下的所有点击都应谨慎）
SENSITIVE_PAGE_PATTERNS = [
    "login", "auth", "payment", "subscribe", "confirm",
]


# ─────────────── Guard 决策 ───────────────

@dataclass
class GuardDecision:
    """Guard 校验结果。"""
    allowed: bool
    action_type: str = ""
    reason: str = ""
    error_code: Optional[str] = None
    requires_refinement: bool = False  # 需要局部定位细化
    refined_bbox: Optional[PixelBBox] = None

    def __bool__(self):
        return self.allowed


# ─────────────── 执行预算 ───────────────

@dataclass
class ExecutionBudget:
    """执行预算跟踪器。"""
    max_steps: int = 8
    max_vlm_calls: int = 4
    max_vlm_calls_with_recovery: int = 6
    max_recoveries: int = 2
    hard_timeout_seconds: int = 20

    step_count: int = field(default=0, init=False)
    vlm_call_count: int = field(default=0, init=False)
    recovery_count: int = field(default=0, init=False)

    @property
    def remaining_steps(self) -> int:
        return max(0, self.max_steps - self.step_count)

    @property
    def remaining_vlm_calls(self) -> int:
        limit = self.max_vlm_calls_with_recovery if self.recovery_count > 0 else self.max_vlm_calls
        return max(0, limit - self.vlm_call_count)

    @property
    def remaining_recoveries(self) -> int:
        return max(0, self.max_recoveries - self.recovery_count)

    def can_continue(self) -> bool:
        """是否还能继续执行。"""
        return (
            self.remaining_steps > 0
            and self.remaining_vlm_calls > 0
        )

    def record_step(self):
        self.step_count += 1

    def record_vlm_call(self):
        self.vlm_call_count += 1

    def record_recovery(self):
        self.recovery_count += 1


# ─────────────── Action Guard ───────────────

class ActionGuard:
    """动作合法性校验器。

    所有 VLM 输出的动作必须经过此 Guard 才能执行。
    """

    def __init__(self):
        self._failed_candidates = set()  # (screen_version, candidate_id) 已失败候选

    def validate(
        self,
        action_type: str,
        candidate_id: Optional[str] = None,
        target_label: Optional[str] = None,
        bbox_px: Optional[PixelBBox] = None,
        key: Optional[str] = None,
        text: Optional[str] = None,
        direction: Optional[str] = None,
        distance: Optional[float] = None,
        candidate_map: Optional[CandidateMap] = None,
        subgoal: Optional[str] = None,
        screen_width: int = 1280,
        screen_height: int = 800,
    ) -> GuardDecision:
        """校验动作合法性。

        Returns:
            GuardDecision
        """
        # 1. 检查动作类型
        allowed_types = {
            "tap_candidate", "tap_visual", "swipe", "type_text",
            "remote_key", "media_key", "wait", "back",
            "reveal_controls", "done", "ask_user",
        }
        if action_type not in allowed_types:
            return GuardDecision(
                False, action_type=action_type,
                reason=f"Unknown action type: {action_type}",
                error_code="UNKNOWN_ACTION",
            )

        # 2. 安全操作直接通过
        if action_type in ("wait", "back", "done", "ask_user", "reveal_controls"):
            return GuardDecision(True, action_type=action_type, reason="safe operation")

        # 3. tap_candidate 校验
        if action_type == "tap_candidate":
            return self._validate_tap_candidate(
                candidate_id, candidate_map, subgoal,
                screen_width, screen_height,
            )

        # 4. tap_visual 校验
        if action_type == "tap_visual":
            return self._validate_tap_visual(
                bbox_px, target_label, subgoal,
                screen_width, screen_height,
            )

        # 5. remote_key / media_key
        if action_type in ("remote_key", "media_key"):
            return self._validate_key(key)

        # 6. type_text
        if action_type == "type_text":
            return self._validate_type_text(text, subgoal)

        # 7. swipe
        if action_type == "swipe":
            return self._validate_swipe(direction, distance)

        return GuardDecision(False, reason="Unhandled action type", error_code="INTERNAL")

    def _validate_tap_candidate(
        self,
        candidate_id: Optional[str],
        candidate_map: Optional[CandidateMap],
        subgoal: Optional[str],
        screen_width: int,
        screen_height: int,
    ) -> GuardDecision:
        """校验 tap_candidate 动作。"""
        # 必须有 candidate_id
        if not candidate_id:
            return GuardDecision(
                False, action_type="tap_candidate",
                reason="tap_candidate requires candidate_id",
                error_code="MISSING_CANDIDATE_ID",
            )

        # candidate 必须存在于当前 CandidateMap
        if candidate_map is None:
            return GuardDecision(
                False, action_type="tap_candidate",
                reason="No candidate map available",
                error_code="NO_CANDIDATE_MAP",
            )

        candidate = None
        for c in candidate_map.candidates:
            if c.candidate_id == candidate_id:
                candidate = c
                break

        if candidate is None:
            return GuardDecision(
                False, action_type="tap_candidate",
                reason=f"Candidate {candidate_id} not found in current map",
                error_code="CANDIDATE_NOT_FOUND",
            )

        # 检查是否已失败过（同一 screen_version 下）
        fail_key = (candidate_map.screen_version, candidate_id)
        if fail_key in self._failed_candidates:
            return GuardDecision(
                False, action_type="tap_candidate",
                reason=f"Candidate {candidate_id} already failed in this screen version",
                error_code="PREVIOUSLY_FAILED",
            )

        # 检查 bbox 合法性
        bbox = candidate.bbox_px
        if bbox.x1 < 0 or bbox.y1 < 0 or bbox.x2 > screen_width or bbox.y2 > screen_height:
            return GuardDecision(
                False, action_type="tap_candidate",
                reason=f"bbox out of screen: ({bbox.x1},{bbox.y1})-({bbox.x2},{bbox.y2})",
                error_code="BBOX_OUT_OF_SCREEN",
            )

        # OCR-only 候选低于阈值时需要 refinement
        if candidate.source == "ocr" and candidate.clickable_likelihood < 0.55:
            return GuardDecision(
                False, action_type="tap_candidate",
                reason="OCR-only candidate needs refinement",
                error_code="NEEDS_REFINEMENT",
                requires_refinement=True,
            )

        # 敏感操作检查
        if self._is_sensitive(candidate.text, candidate.detector_label, subgoal):
            return GuardDecision(
                False, action_type="tap_candidate",
                reason="Sensitive target requires user confirmation",
                error_code="SENSITIVE_TARGET",
            )

        return GuardDecision(
            True, action_type="tap_candidate",
            reason=f"candidate {candidate_id} validated",
        )

    def _validate_tap_visual(
        self,
        bbox_px: Optional[PixelBBox],
        target_label: Optional[str],
        subgoal: Optional[str],
        screen_width: int,
        screen_height: int,
    ) -> GuardDecision:
        """校验 tap_visual 动作（兜底像素坐标点击）。"""
        if not bbox_px:
            return GuardDecision(
                False, action_type="tap_visual",
                reason="tap_visual requires bbox_px",
                error_code="MISSING_BBOX",
            )

        if not target_label:
            return GuardDecision(
                False, action_type="tap_visual",
                reason="tap_visual requires target_label",
                error_code="MISSING_LABEL",
            )

        # bbox 必须在屏幕内
        if (bbox_px.x1 < 0 or bbox_px.y1 < 0 or
                bbox_px.x2 > screen_width or bbox_px.y2 > screen_height):
            return GuardDecision(
                False, action_type="tap_visual",
                reason="bbox out of screen",
                error_code="BBOX_OUT_OF_SCREEN",
            )

        # bbox 面积合理性（不能太小也不能太大）
        area = (bbox_px.x2 - bbox_px.x1) * (bbox_px.y2 - bbox_px.y1)
        screen_area = screen_width * screen_height
        area_ratio = area / screen_area

        if area_ratio < 0.0003:
            return GuardDecision(
                False, action_type="tap_visual",
                reason=f"bbox too small: {area}px ({area_ratio:.4f} of screen)",
                error_code="BBOX_TOO_SMALL",
            )
        if area_ratio > 0.80:
            return GuardDecision(
                False, action_type="tap_visual",
                reason=f"bbox too large: {area_ratio:.2f} of screen",
                error_code="BBOX_TOO_LARGE",
            )

        # 敏感操作检查
        if self._is_sensitive(target_label, None, subgoal):
            return GuardDecision(
                False, action_type="tap_visual",
                reason="Sensitive target requires user confirmation",
                error_code="SENSITIVE_TARGET",
            )

        return GuardDecision(
            True, action_type="tap_visual",
            reason=f"visual target '{target_label}' validated",
        )

    def _validate_key(self, key: Optional[str]) -> GuardDecision:
        """校验 remote_key / media_key。"""
        if not key:
            return GuardDecision(
                False, action_type="remote_key",
                reason="key is required",
                error_code="MISSING_KEY",
            )

        allowed_keys = {
            "UP", "DOWN", "LEFT", "RIGHT",
            "ENTER", "DPAD_CENTER", "MENU", "BACK", "HOME",
            "VOLUME_UP", "VOLUME_DOWN", "VOLUME_MUTE",
            "MEDIA_PLAY_PAUSE", "MEDIA_PLAY", "MEDIA_PAUSE",
            "MEDIA_NEXT", "MEDIA_PREVIOUS", "FAST_FORWARD", "REWIND",
        }

        if key.upper() not in allowed_keys:
            return GuardDecision(
                False, action_type="remote_key",
                reason=f"Unsupported key: {key}",
                error_code="UNSUPPORTED_KEY",
            )

        return GuardDecision(True, action_type="remote_key", reason=f"key '{key}' allowed")

    def _validate_type_text(self, text: Optional[str], subgoal: Optional[str]) -> GuardDecision:
        """校验 type_text 动作。"""
        if not text:
            return GuardDecision(
                False, action_type="type_text",
                reason="text is required",
                error_code="MISSING_TEXT",
            )

        # 敏感文本检查（密码、验证码等）
        if self._is_sensitive(text, None, subgoal):
            return GuardDecision(
                False, action_type="type_text",
                reason="Sensitive text input blocked",
                error_code="SENSITIVE_TEXT",
            )

        return GuardDecision(True, action_type="type_text", reason="text allowed")

    def _validate_swipe(self, direction: Optional[str], distance: Optional[float]) -> GuardDecision:
        """校验 swipe 动作。"""
        if not direction:
            return GuardDecision(
                False, action_type="swipe",
                reason="direction is required",
                error_code="MISSING_DIRECTION",
            )
        if direction not in ("up", "down", "left", "right"):
            return GuardDecision(
                False, action_type="swipe",
                reason=f"Invalid direction: {direction}",
                error_code="INVALID_DIRECTION",
            )
        return GuardDecision(True, action_type="swipe", reason="swipe allowed")

    def _is_sensitive(
        self,
        text: Optional[str],
        detector_label: Optional[str],
        subgoal: Optional[str],
    ) -> bool:
        """判断是否涉及敏感操作。"""
        check_text = " ".join(filter(None, [text, detector_label, subgoal])).lower()

        for keyword in SENSITIVE_KEYWORDS:
            if keyword.lower() in check_text:
                return True

        return False

    @property
    def failed_candidates(self) -> set:
        """返回已失败候选集合，元素为 (fingerprint, candidate_id)。

        新代码通过 state.fingerprint 索引；旧 run_vlm_loop 兼容入口
        仍以 candidate_map.screen_version 索引（两者均为字符串，存储结构相同）。
        """
        return self._failed_candidates

    def record_failure(self, fingerprint: str, candidate_id: str):
        """记录候选失败。

        新 API：传 (state.fingerprint, candidate_id)。
        旧 API（旧 run_vlm_loop 兼容）：传 (screen_version, candidate_id)。
        二者共用同一存储结构，无行为差异。
        """
        self._failed_candidates.add((fingerprint, candidate_id))

    def clear_failures(self):
        """清除失败记录（新观察后调用）。"""
        self._failed_candidates.clear()


# ─────────────── 公开 API（供 action_loop 调用） ───────────────

class InvalidBBoxError(ValueError):
    """tap_to_pixel 收到非法 bbox 时抛出。"""


@dataclass
class ActionGuardConfig:
    """Action Guard 运行时配置。

    与 ActionGuard 本身解耦：
      - ActionGuard：状态机（记录失败候选），无配置
      - ActionGuardConfig：纯配置数据，可序列化
    """
    screen_width: int = 1280
    screen_height: int = 800
    sensitive_keywords: list = None  # 追加到 SENSITIVE_KEYWORDS
    allow_tap_visual_fallback: bool = True  # 是否允许 tap_visual 兜底

    def __post_init__(self):
        if self.sensitive_keywords is None:
            self.sensitive_keywords = []


def validate_action(
    action: ActionSpec,
    state: UiState,
    subgoal: str,
    failed_candidate_keys: set,
    *,
    guard: ActionGuard = None,
    config: ActionGuardConfig = None,
) -> GuardDecision:
    """v3 模块级校验入口：完整 action + state + subgoal + failed_keys。

    约束：
      - guard 必须被使用（若 None 则创建默认实例）
      - config 若 None 则创建默认实例
      - failed_candidate_keys 由调用方传入（通常来自 guard.failed_candidates）
      - 敏感性判定优先来自候选显式字段（risk_category / sensitive_category / action_semantics），
        sensitive_hint 仅追加拦截；不用 subgoal 关键词判定

    Returns:
        GuardDecision
    """
    config = config or ActionGuardConfig()
    guard = guard or ActionGuard()

    action_type = action.action_type

    # 1. action_type 白名单
    allowed_types = {
        "tap_candidate", "tap_visual", "swipe", "type_text",
        "remote_key", "media_key", "wait", "back",
        "reveal_controls", "done", "ask_user",
    }
    if action_type not in allowed_types:
        return GuardDecision(
            False, action_type=action_type,
            reason=f"Unknown action type: {action_type}",
            error_code="UNKNOWN_ACTION",
        )

    # 2. ask_user / done 由 run_action_loop 直接处理，此处视为允许（不拦截）
    if action_type in ("ask_user", "done"):
        return GuardDecision(True, action_type=action_type, reason="lifecycle action")

    # 3. safe actions
    if action_type in ("wait", "back", "reveal_controls"):
        return GuardDecision(True, action_type=action_type, reason="safe operation")

    # 4. tap_candidate
    if action_type == "tap_candidate":
        return _validate_tap_candidate(action, state, failed_candidate_keys, config)

    # 5. tap_visual
    if action_type == "tap_visual":
        return _validate_tap_visual(action, state, config)

    # 6. remote_key / media_key
    if action_type in ("remote_key", "media_key"):
        return _validate_key(action)

    # 7. type_text
    if action_type == "type_text":
        return _validate_type_text(action)

    # 8. swipe
    if action_type == "swipe":
        return _validate_swipe(action)

    return GuardDecision(False, reason="Unhandled action type", error_code="INTERNAL")


# ─────────────── tap_candidate 校验 ───────────────

def _validate_tap_candidate(
    action: ActionSpec,
    state: UiState,
    failed_candidate_keys: set,
    config: ActionGuardConfig,
) -> GuardDecision:
    if not action.candidate_id:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason="tap_candidate requires candidate_id",
            error_code="MISSING_CANDIDATE_ID",
        )

    if state.candidate_map is None:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason="No candidate map in state",
            error_code="NO_CANDIDATE_MAP",
        )

    # 在当前 CandidateMap 中查找候选
    candidate = None
    for c in state.candidate_map.candidates:
        if c.candidate_id == action.candidate_id:
            candidate = c
            break

    if candidate is None:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=f"Candidate {action.candidate_id} not found in current map",
            error_code="CANDIDATE_NOT_FOUND",
        )

    # candidate_map_fingerprint 必须与当前 candidate_map.screen_version 匹配
    if (action.candidate_map_fingerprint is not None
            and action.candidate_map_fingerprint != state.candidate_map.screen_version):
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=(f"candidate_map_fingerprint mismatch: "
                    f"action={action.candidate_map_fingerprint} vs "
                    f"state.candidate_map.screen_version={state.candidate_map.screen_version}"),
            error_code="FINGERPRINT_MISMATCH",
        )

    # expected_screen_fingerprint 必须与 state.fingerprint 匹配
    if (action.expected_screen_fingerprint is not None
            and action.expected_screen_fingerprint != state.fingerprint):
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=(f"expected_screen_fingerprint mismatch: "
                    f"action={action.expected_screen_fingerprint} vs state={state.fingerprint}"),
            error_code="PAGE_MISMATCH",
        )

    # bbox 必须在屏幕内
    screen_w, screen_h = state.screen_size
    bbox = candidate.bbox_px
    if bbox.x1 < 0 or bbox.y1 < 0 or bbox.x2 > screen_w or bbox.y2 > screen_h:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=f"bbox out of screen ({screen_w}x{screen_h}): {bbox}",
            error_code="BBOX_OUT_OF_SCREEN",
        )

    # 重复失败防护：(state.fingerprint, candidate_id)
    fail_key = (state.fingerprint, action.candidate_id)
    if fail_key in failed_candidate_keys:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=f"Candidate {action.candidate_id} already failed at fingerprint {state.fingerprint}",
            error_code="PREVIOUSLY_FAILED",
        )

    # 敏感性判定：优先来自候选显式字段，sensitive_hint 仅追加
    sensitive_reason = _check_candidate_sensitivity(candidate, action.sensitive_hint)
    if sensitive_reason:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=f"Sensitive target: {sensitive_reason}",
            error_code="SENSITIVE_TARGET",
        )

    return GuardDecision(
        True, action_type="tap_candidate",
        reason=f"candidate {action.candidate_id} validated",
    )


def _check_candidate_sensitivity(candidate: UiCandidate, sensitive_hint: Optional[str]) -> Optional[str]:
    """基于候选显式字段判定敏感性。

    优先级：
      1. candidate.risk_category ∈ SENSITIVE_RISK_CATEGORIES → reject
      2. candidate.sensitive_category 非空 → reject
      3. candidate.action_semantics 包含敏感动作语义 → reject
      4. action.sensitive_hint 提供 → reject（额外保守）

    Returns:
        敏感原因字符串，或 None（不敏感）
    """
    if candidate.risk_category and candidate.risk_category.lower() in SENSITIVE_RISK_CATEGORIES:
        return f"risk_category={candidate.risk_category}"
    if candidate.sensitive_category:
        return f"sensitive_category={candidate.sensitive_category}"
    if candidate.action_semantics:
        sem = candidate.action_semantics.lower()
        for kw in SENSITIVE_KEYWORDS:
            if kw.lower() in sem:
                return f"action_semantics='{candidate.action_semantics}' matches '{kw}'"
    if sensitive_hint:
        return f"sensitive_hint={sensitive_hint}"
    return None


# ─────────────── tap_visual 校验 ───────────────

def _validate_tap_visual(
    action: ActionSpec,
    state: UiState,
    config: ActionGuardConfig,
) -> GuardDecision:
    if not action.bbox_px:
        return GuardDecision(
            False, action_type="tap_visual",
            reason="tap_visual requires bbox_px",
            error_code="MISSING_BBOX",
        )

    screen_w, screen_h = state.screen_size
    bbox = action.bbox_px

    if bbox.x1 < 0 or bbox.y1 < 0 or bbox.x2 > screen_w or bbox.y2 > screen_h:
        return GuardDecision(
            False, action_type="tap_visual",
            reason=f"bbox out of screen ({screen_w}x{screen_h})",
            error_code="BBOX_OUT_OF_SCREEN",
        )

    area = (bbox.x2 - bbox.x1) * (bbox.y2 - bbox.y1)
    screen_area = screen_w * screen_h
    area_ratio = area / screen_area if screen_area > 0 else 0

    if area_ratio < 0.0003:
        return GuardDecision(
            False, action_type="tap_visual",
            reason=f"bbox too small: {area}px ({area_ratio:.4f} of screen)",
            error_code="BBOX_TOO_SMALL",
        )
    if area_ratio > 0.80:
        return GuardDecision(
            False, action_type="tap_visual",
            reason=f"bbox too large: {area_ratio:.2f} of screen",
            error_code="BBOX_TOO_LARGE",
        )

    # expected_screen_fingerprint 检查
    if (action.expected_screen_fingerprint is not None
            and action.expected_screen_fingerprint != state.fingerprint):
        return GuardDecision(
            False, action_type="tap_visual",
            reason=f"expected_screen_fingerprint mismatch: {action.expected_screen_fingerprint} vs {state.fingerprint}",
            error_code="PAGE_MISMATCH",
        )

    # 敏感检查：sensitive_hint + target_role，不查 subgoal
    if action.sensitive_hint:
        return GuardDecision(
            False, action_type="tap_visual",
            reason=f"Sensitive target: sensitive_hint={action.sensitive_hint}",
            error_code="SENSITIVE_TARGET",
        )
    if action.target_role and action.target_role.lower() in {k.lower() for k in SENSITIVE_KEYWORDS}:
        return GuardDecision(
            False, action_type="tap_visual",
            reason=f"Sensitive target_role: {action.target_role}",
            error_code="SENSITIVE_TARGET",
        )

    return GuardDecision(
        True, action_type="tap_visual",
        reason=f"visual target '{action.target_role}' validated",
    )


# ─────────────── 其他动作校验 ───────────────

def _validate_key(action: ActionSpec) -> GuardDecision:
    if not action.key:
        return GuardDecision(
            False, action_type="remote_key",
            reason="key is required",
            error_code="MISSING_KEY",
        )

    allowed_keys = {
        "UP", "DOWN", "LEFT", "RIGHT",
        "ENTER", "DPAD_CENTER", "MENU", "BACK", "HOME",
        "VOLUME_UP", "VOLUME_DOWN", "VOLUME_MUTE",
        "MEDIA_PLAY_PAUSE", "MEDIA_PLAY", "MEDIA_PAUSE",
        "MEDIA_NEXT", "MEDIA_PREVIOUS", "FAST_FORWARD", "REWIND",
    }

    if action.key.upper() not in allowed_keys:
        return GuardDecision(
            False, action_type="remote_key",
            reason=f"Unsupported key: {action.key}",
            error_code="UNSUPPORTED_KEY",
        )

    return GuardDecision(True, action_type="remote_key", reason=f"key '{action.key}' allowed")


def _validate_type_text(action: ActionSpec) -> GuardDecision:
    if not action.text:
        return GuardDecision(
            False, action_type="type_text",
            reason="text is required",
            error_code="MISSING_TEXT",
        )

    if action.sensitive_hint:
        return GuardDecision(
            False, action_type="type_text",
            reason=f"Sensitive text input: sensitive_hint={action.sensitive_hint}",
            error_code="SENSITIVE_TEXT",
        )

    return GuardDecision(True, action_type="type_text", reason="text allowed")


def _validate_swipe(action: ActionSpec) -> GuardDecision:
    if not action.direction:
        return GuardDecision(
            False, action_type="swipe",
            reason="direction is required",
            error_code="MISSING_DIRECTION",
        )
    if action.direction not in ("up", "down", "left", "right"):
        return GuardDecision(
            False, action_type="swipe",
            reason=f"Invalid direction: {action.direction}",
            error_code="INVALID_DIRECTION",
        )
    return GuardDecision(True, action_type="swipe", reason="swipe allowed")


def tap_to_pixel(
    bbox_px: PixelBBox,
    screen_width: int,
    screen_height: int,
) -> tuple:
    """把合法 bbox 转成屏幕点击坐标（中心点）。

    约束：
      - 输入必须是已经通过 Guard bbox 校验的 bbox
      - bbox 非法（越界、反向、退化）时抛出 InvalidBBoxError，绝不静默裁剪

    Returns:
        (cx, cy) 整数像素坐标
    """
    if bbox_px is None:
        raise InvalidBBoxError("bbox_px is None")
    if bbox_px.x1 < 0 or bbox_px.y1 < 0:
        raise InvalidBBoxError(f"bbox has negative origin: {bbox_px}")
    if bbox_px.x2 > screen_width or bbox_px.y2 > screen_height:
        raise InvalidBBoxError(
            f"bbox exceeds screen ({screen_width}x{screen_height}): {bbox_px}"
        )
    if bbox_px.x1 >= bbox_px.x2 or bbox_px.y1 >= bbox_px.y2:
        raise InvalidBBoxError(f"bbox is degenerate: {bbox_px}")
    cx = (bbox_px.x1 + bbox_px.x2) // 2
    cy = (bbox_px.y1 + bbox_px.y2) // 2
    return (cx, cy)
