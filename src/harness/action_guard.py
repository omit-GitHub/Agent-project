# -*- coding: utf-8 -*-
"""Action Guard — 纯校验层。

Guard 只负责验证动作合法性并输出结构化结果：
  - allowed: bool
  - error_code: str | None
  - risk_level: "low" | "medium" | "high"
  - requires_refinement: bool
  - reason: str

action_loop 根据这些字段决定：
  - allowed=True, risk_level=low → 执行
  - allowed=False, risk_level=high → guard_reject
  - allowed=False, risk_level=medium → needs_user_confirmation
  - requires_refinement=True → needs_refinement → 受限恢复

本模块不决定最终流转方向，不含任何 decision/reject/ask_user 逻辑。
"""
from dataclasses import dataclass
from typing import Optional

from .schemas import ActionSpec, UiState
from .types import BBox, Candidate


# ─────────────── 敏感词库 ───────────────

SENSITIVE_KEYWORDS = [
    "付款", "支付", "充值", "订阅", "购买", "扣费", "开通会员", "VIP",
    "删除", "卸载", "清除", "格式化", "注销", "退出登录",
    "密码", "验证码", "授权", "登录", "注册", "短信",
    "发送", "提交", "确认", "确定",
]

SENSITIVE_RISK_CATEGORIES = {
    "payment", "delete", "send", "logout",
    "password", "authorization", "unsubscribe",
    "purchase", "refund", "ban", "reset",
}

HIGH_RISK_CATEGORIES = {"payment", "delete"}


# ─────────────── Guard 校验结果 ───────────────

@dataclass
class GuardDecision:
    """Guard 纯校验结果。

    action_loop 根据 risk_level + allowed 决定流转方向。
    """
    allowed: bool
    action_type: str = ""
    reason: str = ""
    error_code: Optional[str] = None
    risk_level: str = "low"              # "low" | "medium" | "high"
    requires_refinement: bool = False
    refined_bbox: Optional[BBox] = None

    def __bool__(self):
        return self.allowed


# ─────────────── 异常 ───────────────

class InvalidBBoxError(ValueError):
    """tap_to_pixel 收到非法 bbox 时抛出。"""


# ─────────────── 配置 ───────────────

@dataclass
class ActionGuardConfig:
    """Action Guard 运行时配置。"""
    screen_width: int = 1280
    screen_height: int = 800
    sensitive_keywords: list = None
    allow_tap_visual_fallback: bool = True
    min_candidate_confidence: float = 0.5
    min_clickable_likelihood: float = 0.3
    allow_ocr_only_tap: bool = True

    def __post_init__(self):
        if self.sensitive_keywords is None:
            self.sensitive_keywords = []


# ─────────────── Action Guard 类 ───────────────

class ActionGuard:
    """动作合法性校验器（有状态：跟踪失败候选）。"""

    def __init__(self):
        self._failed_candidates: set = set()

    @property
    def failed_candidates(self) -> set:
        return self._failed_candidates

    def record_failure(self, fingerprint: str, candidate_id: str):
        self._failed_candidates.add((fingerprint, candidate_id))

    def clear_failures(self):
        self._failed_candidates.clear()


# ─────────────── 公开 API ───────────────

def validate_action(
    action: ActionSpec,
    state: UiState,
    subgoal: str,
    failed_candidate_keys: set,
    *,
    guard: Optional[ActionGuard] = None,
    config: Optional[ActionGuardConfig] = None,
) -> GuardDecision:
    """模块级校验入口。纯校验，不含决策流转逻辑。"""
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
            risk_level="high",
        )

    # 2. ask_user / done 生命周期动作
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

    return GuardDecision(False, reason="Unhandled action type", error_code="INTERNAL",
                         risk_level="high")


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
            risk_level="high",
        )

    if state.candidate_map is None:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason="No candidate map in state",
            error_code="NO_CANDIDATE_MAP",
            risk_level="high",
        )

    # CandidateMap 与 UiState 一致性
    cm = state.candidate_map
    if cm.package != state.package:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=f"CandidateMap package '{cm.package}' != UiState package '{state.package}'",
            error_code="CANDIDATE_MAP_PACKAGE_MISMATCH",
            risk_level="high",
        )
    if cm.activity != state.activity:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=f"CandidateMap activity '{cm.activity}' != UiState activity '{state.activity}'",
            error_code="CANDIDATE_MAP_ACTIVITY_MISMATCH",
            risk_level="high",
        )
    if cm.width != state.screen_size[0] or cm.height != state.screen_size[1]:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=f"CandidateMap size ({cm.width}x{cm.height}) != screen_size {state.screen_size}",
            error_code="CANDIDATE_MAP_SIZE_MISMATCH",
            risk_level="high",
        )

    # 查找候选
    candidate = None
    for c in cm.candidates:
        if c.candidate_id == action.candidate_id:
            candidate = c
            break

    if candidate is None:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=f"Candidate {action.candidate_id} not found in current map",
            error_code="CANDIDATE_NOT_FOUND",
            risk_level="high",
        )

    # fingerprint 匹配
    if (action.candidate_map_fingerprint is not None
            and action.candidate_map_fingerprint != cm.screen_version):
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=f"candidate_map_fingerprint mismatch: "
                   f"action={action.candidate_map_fingerprint} vs "
                   f"state={cm.screen_version}",
            error_code="FINGERPRINT_MISMATCH",
            risk_level="high",
        )

    if (action.expected_screen_fingerprint is not None
            and action.expected_screen_fingerprint != state.fingerprint):
        return GuardDecision(
            False, action_type="tap_candidate",
            reason="expected_screen_fingerprint mismatch",
            error_code="PAGE_MISMATCH",
            risk_level="high",
        )

    # bbox 屏幕内
    screen_w, screen_h = state.screen_size
    bbox = candidate.bbox_px
    if not bbox.fits_in(screen_w, screen_h):
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=f"bbox out of screen ({screen_w}x{screen_h}): {bbox}",
            error_code="BBOX_OUT_OF_SCREEN",
            risk_level="high",
        )

    # 重复失败
    fail_key = (state.fingerprint, action.candidate_id)
    if fail_key in failed_candidate_keys:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=f"Candidate {action.candidate_id} already failed at {state.fingerprint}",
            error_code="PREVIOUSLY_FAILED",
            risk_level="high",
        )

    # confidence / clickable_likelihood 阈值
    if candidate.confidence < config.min_candidate_confidence:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=f"confidence {candidate.confidence} < {config.min_candidate_confidence}",
            error_code="LOW_CONFIDENCE",
            risk_level="low",
            requires_refinement=True,
        )
    if candidate.clickable_likelihood < config.min_clickable_likelihood:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=f"clickable_likelihood {candidate.clickable_likelihood} < "
                   f"{config.min_clickable_likelihood}",
            error_code="LOW_CLICKABLE_LIKELIHOOD",
            risk_level="low",
            requires_refinement=True,
        )
    if not config.allow_ocr_only_tap and candidate.source == "ocr" and not candidate.kind:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason="OCR-only tap not allowed",
            error_code="OCR_ONLY_NOT_ALLOWED",
            risk_level="low",
            requires_refinement=True,
        )

    # 敏感性 → risk_level
    sensitive_reason = _check_candidate_sensitivity(candidate, action.sensitive_hint)
    if sensitive_reason:
        if candidate.risk_category and candidate.risk_category.lower() in HIGH_RISK_CATEGORIES:
            risk_level = "high"
        else:
            risk_level = "medium"
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=f"Sensitive target: {sensitive_reason}",
            error_code="SENSITIVE_TARGET",
            risk_level=risk_level,
        )

    return GuardDecision(
        True, action_type="tap_candidate",
        reason=f"candidate {action.candidate_id} validated",
        risk_level="low",
    )


def _check_candidate_sensitivity(
    candidate: Candidate,
    sensitive_hint: Optional[str],
) -> Optional[str]:
    """判定敏感性。返回原因字符串或 None。"""
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
            risk_level="high",
        )

    screen_w, screen_h = state.screen_size
    bbox = action.bbox_px

    if not bbox.fits_in(screen_w, screen_h):
        return GuardDecision(
            False, action_type="tap_visual",
            reason=f"bbox out of screen ({screen_w}x{screen_h})",
            error_code="BBOX_OUT_OF_SCREEN",
            risk_level="high",
        )

    area = bbox.area()
    screen_area = screen_w * screen_h
    area_ratio = area / screen_area if screen_area > 0 else 0

    if area_ratio < 0.0003:
        return GuardDecision(
            False, action_type="tap_visual",
            reason=f"bbox too small: {area}px ({area_ratio:.4f} of screen)",
            error_code="BBOX_TOO_SMALL",
            risk_level="high",
        )
    if area_ratio > 0.80:
        return GuardDecision(
            False, action_type="tap_visual",
            reason=f"bbox too large: {area_ratio:.2f} of screen",
            error_code="BBOX_TOO_LARGE",
            risk_level="high",
        )

    if (action.expected_screen_fingerprint is not None
            and action.expected_screen_fingerprint != state.fingerprint):
        return GuardDecision(
            False, action_type="tap_visual",
            reason="expected_screen_fingerprint mismatch",
            error_code="PAGE_MISMATCH",
            risk_level="high",
        )

    # allow_tap_visual_fallback
    if not config.allow_tap_visual_fallback:
        return GuardDecision(
            False, action_type="tap_visual",
            reason="tap_visual fallback not allowed",
            error_code="TAP_VISUAL_NOT_ALLOWED",
            risk_level="high",
        )

    # 敏感性
    if action.sensitive_hint:
        return GuardDecision(
            False, action_type="tap_visual",
            reason=f"Sensitive: sensitive_hint={action.sensitive_hint}",
            error_code="SENSITIVE_TARGET",
            risk_level="medium",
        )
    if action.target_role and action.target_role.lower() in {k.lower() for k in SENSITIVE_KEYWORDS}:
        return GuardDecision(
            False, action_type="tap_visual",
            reason=f"Sensitive target_role: {action.target_role}",
            error_code="SENSITIVE_TARGET",
            risk_level="medium",
        )

    # 低置信 → requires_refinement
    requires_refinement = area < 500

    return GuardDecision(
        True, action_type="tap_visual",
        reason=f"visual target '{action.target_role}' validated",
        risk_level="low",
        requires_refinement=requires_refinement,
    )


# ─────────────── 其他动作校验 ───────────────

def _validate_key(action: ActionSpec) -> GuardDecision:
    if not action.key:
        return GuardDecision(
            False, action_type="remote_key",
            reason="key is required",
            error_code="MISSING_KEY",
            risk_level="high",
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
            risk_level="high",
        )

    return GuardDecision(True, action_type="remote_key", reason=f"key '{action.key}' allowed",
                         risk_level="low")


def _validate_type_text(action: ActionSpec) -> GuardDecision:
    if not action.text:
        return GuardDecision(
            False, action_type="type_text",
            reason="text is required",
            error_code="MISSING_TEXT",
            risk_level="high",
        )

    if action.sensitive_hint:
        return GuardDecision(
            False, action_type="type_text",
            reason=f"Sensitive text input: {action.sensitive_hint}",
            error_code="SENSITIVE_TEXT",
            risk_level="medium",
        )

    return GuardDecision(True, action_type="type_text", reason="text allowed", risk_level="low")


def _validate_swipe(action: ActionSpec) -> GuardDecision:
    if not action.direction:
        return GuardDecision(
            False, action_type="swipe",
            reason="direction is required",
            error_code="MISSING_DIRECTION",
            risk_level="high",
        )
    if action.direction not in ("up", "down", "left", "right"):
        return GuardDecision(
            False, action_type="swipe",
            reason=f"Invalid direction: {action.direction}",
            error_code="INVALID_DIRECTION",
            risk_level="high",
        )
    return GuardDecision(True, action_type="swipe", reason="swipe allowed", risk_level="low")


# ─────────────── tap_to_pixel ───────────────

def tap_to_pixel(
    bbox_px: BBox,
    screen_width: int,
    screen_height: int,
) -> tuple:
    """把合法 bbox 转成屏幕点击坐标（中心点）。"""
    if bbox_px is None:
        raise InvalidBBoxError("bbox_px is None")
    if not bbox_px.fits_in(screen_width, screen_height):
        raise InvalidBBoxError(
            f"bbox exceeds screen ({screen_width}x{screen_height}): {bbox_px}"
        )
    return bbox_px.center()
