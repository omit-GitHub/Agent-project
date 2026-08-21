# -*- coding: utf-8 -*-
"""Action Guard — VLM / 任意决策源输出的合法性校验层。

对每个建议动作进行多重前置检查，只有全部通过才允许执行。
防止误触发登录、支付、删除等不可逆操作。

校验维度：
  1. 动作类型合法性（白名单）
  2. CandidateMap 与 UiState 一致性（package/activity/width/height）
  3. candidate_id 归属（属于当前 CandidateMap）
  4. bbox 合法性（越界、面积、位置）
  5. 候选地图指纹兼容（candidate_map_fingerprint vs state.candidate_map.screen_version）
  6. UI 指纹兼容（expected_screen_fingerprint vs state.fingerprint，防跨页点击）
  7. confidence / clickable_likelihood 阈值
  8. 敏感操作拦截（结构化 decision: reject / ask_user）
  9. 重复失败候选排除（同一 UI fingerprint 下不再点击已失败候选）

本模块无任何外部依赖（不依赖 VLM / ADB / 具体 App）。
"""
from dataclasses import dataclass, field
from typing import Optional

from .schemas import ActionSpec, UiState
from .types import BBox, Candidate


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

# 高危 risk_category：直接 reject（绝不进 executor）
HIGH_RISK_CATEGORIES = {"payment", "delete"}


# ─────────────── Guard 决策 ───────────────

@dataclass
class GuardDecision:
    """Guard 校验结果。

    decision 取值：
      - "allow": 允许执行
      - "ask_user": 敏感操作需用户确认（不进 executor）
      - "reject": 直接拒绝（高危操作，绝不进 executor）
    """
    allowed: bool
    action_type: str = ""
    reason: str = ""
    error_code: Optional[str] = None
    requires_refinement: bool = False
    refined_bbox: Optional[BBox] = None
    decision: str = "allow"

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
    sensitive_keywords: list = None  # 追加到 SENSITIVE_KEYWORDS
    allow_tap_visual_fallback: bool = True
    min_candidate_confidence: float = 0.5
    min_clickable_likelihood: float = 0.3
    allow_ocr_only_tap: bool = True

    def __post_init__(self):
        if self.sensitive_keywords is None:
            self.sensitive_keywords = []


# ─────────────── Action Guard 类 ───────────────

class ActionGuard:
    """动作合法性校验器（有状态：跟踪失败候选）。

    所有决策源输出的动作必须经过此 Guard 才能执行。
    """

    def __init__(self):
        self._failed_candidates: set = set()  # (fingerprint, candidate_id)

    @property
    def failed_candidates(self) -> set:
        """已失败候选集合，元素为 (fingerprint, candidate_id)。"""
        return self._failed_candidates

    def record_failure(self, fingerprint: str, candidate_id: str):
        """记录候选失败。"""
        self._failed_candidates.add((fingerprint, candidate_id))

    def clear_failures(self):
        """清除失败记录（新观察后调用）。"""
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
    """模块级校验入口：完整 action + state + subgoal + failed_keys。

    - guard 必须被使用（若 None 则创建默认实例）
    - failed_candidate_keys 由调用方传入（通常来自 guard.failed_candidates）
    - 敏感性判定优先来自候选显式字段；sensitive_hint 仅追加拦截
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
            decision="reject",
        )

    # 2. ask_user / done 由 run_action_loop 直接处理
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
                         decision="reject")


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
            decision="reject",
        )

    if state.candidate_map is None:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason="No candidate map in state",
            error_code="NO_CANDIDATE_MAP",
            decision="reject",
        )

    # ── CandidateMap 与 UiState 一致性 ──
    cm = state.candidate_map
    if cm.package != state.package:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=f"CandidateMap package '{cm.package}' != UiState package '{state.package}'",
            error_code="CANDIDATE_MAP_PACKAGE_MISMATCH",
            decision="reject",
        )
    if cm.activity != state.activity:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=f"CandidateMap activity '{cm.activity}' != UiState activity '{state.activity}'",
            error_code="CANDIDATE_MAP_ACTIVITY_MISMATCH",
            decision="reject",
        )
    if cm.width != state.screen_size[0] or cm.height != state.screen_size[1]:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=f"CandidateMap size ({cm.width}x{cm.height}) != screen_size {state.screen_size}",
            error_code="CANDIDATE_MAP_SIZE_MISMATCH",
            decision="reject",
        )

    # 在当前 CandidateMap 中查找候选
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
            decision="reject",
        )

    # candidate_map_fingerprint 必须与当前 candidate_map.screen_version 匹配
    if (action.candidate_map_fingerprint is not None
            and action.candidate_map_fingerprint != cm.screen_version):
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=(f"candidate_map_fingerprint mismatch: "
                    f"action={action.candidate_map_fingerprint} vs "
                    f"state.candidate_map.screen_version={cm.screen_version}"),
            error_code="FINGERPRINT_MISMATCH",
            decision="reject",
        )

    # expected_screen_fingerprint 必须与 state.fingerprint 匹配
    if (action.expected_screen_fingerprint is not None
            and action.expected_screen_fingerprint != state.fingerprint):
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=(f"expected_screen_fingerprint mismatch: "
                    f"action={action.expected_screen_fingerprint} vs state={state.fingerprint}"),
            error_code="PAGE_MISMATCH",
            decision="reject",
        )

    # bbox 必须在屏幕内
    screen_w, screen_h = state.screen_size
    bbox = candidate.bbox_px
    if not bbox.fits_in(screen_w, screen_h):
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=f"bbox out of screen ({screen_w}x{screen_h}): {bbox}",
            error_code="BBOX_OUT_OF_SCREEN",
            decision="reject",
        )

    # 重复失败防护：(state.fingerprint, candidate_id)
    fail_key = (state.fingerprint, action.candidate_id)
    if fail_key in failed_candidate_keys:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=f"Candidate {action.candidate_id} already failed at fingerprint {state.fingerprint}",
            error_code="PREVIOUSLY_FAILED",
            decision="reject",
        )

    # ── confidence / clickable_likelihood 阈值 ──
    if candidate.confidence < config.min_candidate_confidence:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=f"Candidate confidence {candidate.confidence} < threshold {config.min_candidate_confidence}",
            error_code="LOW_CONFIDENCE",
            requires_refinement=True,
            decision="reject",
        )
    if candidate.clickable_likelihood < config.min_clickable_likelihood:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=f"Candidate clickable_likelihood {candidate.clickable_likelihood} < threshold {config.min_clickable_likelihood}",
            error_code="LOW_CLICKABLE_LIKELIHOOD",
            requires_refinement=True,
            decision="reject",
        )
    if not config.allow_ocr_only_tap and candidate.source == "ocr" and not candidate.kind:
        return GuardDecision(
            False, action_type="tap_candidate",
            reason="OCR-only tap not allowed (source=ocr, kind unknown)",
            error_code="OCR_ONLY_NOT_ALLOWED",
            decision="reject",
        )

    # ── 敏感性判定：优先来自候选显式字段，sensitive_hint 仅追加 ──
    sensitive_reason = _check_candidate_sensitivity(candidate, action.sensitive_hint)
    if sensitive_reason:
        # 高危类别 → reject；其他 → ask_user
        if candidate.risk_category and candidate.risk_category.lower() in HIGH_RISK_CATEGORIES:
            decision = "reject"
        else:
            decision = "ask_user"
        return GuardDecision(
            False, action_type="tap_candidate",
            reason=f"Sensitive target: {sensitive_reason}",
            error_code="SENSITIVE_TARGET",
            decision=decision,
        )

    return GuardDecision(
        True, action_type="tap_candidate",
        reason=f"candidate {action.candidate_id} validated",
    )


def _check_candidate_sensitivity(
    candidate: Candidate,
    sensitive_hint: Optional[str],
) -> Optional[str]:
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
            decision="reject",
        )

    screen_w, screen_h = state.screen_size
    bbox = action.bbox_px

    if not bbox.fits_in(screen_w, screen_h):
        return GuardDecision(
            False, action_type="tap_visual",
            reason=f"bbox out of screen ({screen_w}x{screen_h})",
            error_code="BBOX_OUT_OF_SCREEN",
            decision="reject",
        )

    area = bbox.area()
    screen_area = screen_w * screen_h
    area_ratio = area / screen_area if screen_area > 0 else 0

    if area_ratio < 0.0003:
        return GuardDecision(
            False, action_type="tap_visual",
            reason=f"bbox too small: {area}px ({area_ratio:.4f} of screen)",
            error_code="BBOX_TOO_SMALL",
            decision="reject",
        )
    if area_ratio > 0.80:
        return GuardDecision(
            False, action_type="tap_visual",
            reason=f"bbox too large: {area_ratio:.2f} of screen",
            error_code="BBOX_TOO_LARGE",
            decision="reject",
        )

    if (action.expected_screen_fingerprint is not None
            and action.expected_screen_fingerprint != state.fingerprint):
        return GuardDecision(
            False, action_type="tap_visual",
            reason=f"expected_screen_fingerprint mismatch",
            error_code="PAGE_MISMATCH",
            decision="reject",
        )

    # ── allow_tap_visual_fallback ──
    if not config.allow_tap_visual_fallback:
        return GuardDecision(
            False, action_type="tap_visual",
            reason="tap_visual fallback not allowed",
            error_code="TAP_VISUAL_NOT_ALLOWED",
            decision="reject",
        )

    # 敏感性检查
    if action.sensitive_hint:
        return GuardDecision(
            False, action_type="tap_visual",
            reason=f"Sensitive target: sensitive_hint={action.sensitive_hint}",
            error_code="SENSITIVE_TARGET",
            decision="ask_user",
        )
    if action.target_role and action.target_role.lower() in {k.lower() for k in SENSITIVE_KEYWORDS}:
        return GuardDecision(
            False, action_type="tap_visual",
            reason=f"Sensitive target_role: {action.target_role}",
            error_code="SENSITIVE_TARGET",
            decision="ask_user",
        )

    # 低置信或无来源信息 → requires_refinement
    requires_refinement = False
    if area < 500:
        requires_refinement = True

    return GuardDecision(
        True, action_type="tap_visual",
        reason=f"visual target '{action.target_role}' validated",
        requires_refinement=requires_refinement,
    )


# ─────────────── 其他动作校验 ───────────────

def _validate_key(action: ActionSpec) -> GuardDecision:
    if not action.key:
        return GuardDecision(
            False, action_type="remote_key",
            reason="key is required",
            error_code="MISSING_KEY",
            decision="reject",
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
            decision="reject",
        )

    return GuardDecision(True, action_type="remote_key", reason=f"key '{action.key}' allowed")


def _validate_type_text(action: ActionSpec) -> GuardDecision:
    if not action.text:
        return GuardDecision(
            False, action_type="type_text",
            reason="text is required",
            error_code="MISSING_TEXT",
            decision="reject",
        )

    if action.sensitive_hint:
        return GuardDecision(
            False, action_type="type_text",
            reason=f"Sensitive text input: sensitive_hint={action.sensitive_hint}",
            error_code="SENSITIVE_TEXT",
            decision="ask_user",
        )

    return GuardDecision(True, action_type="type_text", reason="text allowed")


def _validate_swipe(action: ActionSpec) -> GuardDecision:
    if not action.direction:
        return GuardDecision(
            False, action_type="swipe",
            reason="direction is required",
            error_code="MISSING_DIRECTION",
            decision="reject",
        )
    if action.direction not in ("up", "down", "left", "right"):
        return GuardDecision(
            False, action_type="swipe",
            reason=f"Invalid direction: {action.direction}",
            error_code="INVALID_DIRECTION",
            decision="reject",
        )
    return GuardDecision(True, action_type="swipe", reason="swipe allowed")


# ─────────────── tap_to_pixel ───────────────

def tap_to_pixel(
    bbox_px: BBox,
    screen_width: int,
    screen_height: int,
) -> tuple:
    """把合法 bbox 转成屏幕点击坐标（中心点）。

    bbox 非法时抛出 InvalidBBoxError，绝不静默裁剪。
    """
    if bbox_px is None:
        raise InvalidBBoxError("bbox_px is None")
    if not bbox_px.fits_in(screen_width, screen_height):
        raise InvalidBBoxError(
            f"bbox exceeds screen ({screen_width}x{screen_height}): {bbox_px}"
        )
    return bbox_px.center()
