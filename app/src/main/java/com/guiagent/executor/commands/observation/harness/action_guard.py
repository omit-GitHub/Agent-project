# -*- coding: utf-8 -*-
"""Action Guard — 校验 VLM 建议的动作是否合法。

对应 Cursor 任务书 §6.1。
所有 VLM 输出的动作必须经过此模块校验才能执行。
"""
from dataclasses import dataclass
from typing import Literal

from ..vlm.schemas import NextAction


class GuardDecision:
    """Guard 决策结果。"""
    def __init__(
        self,
        allowed: bool,
        action: NextAction | None = None,
        reason: str = "",
        error_code: str | None = None,
    ):
        self.allowed = allowed
        self.action = action
        self.reason = reason
        self.error_code = error_code

    def __bool__(self):
        return self.allowed


# 敏感词列表（触发 ask_user）
SENSITIVE_KEYWORDS = [
    "付款", "支付", "充值", "订阅", "购买", "扣费",
    "删除", "卸载", "清除", "格式化",
    "发送", "提交", "确认", "授权",
    "密码", "验证码", "登录", "注册",
    "退出登录", "注销",
]

# 敏感区域（归一化坐标，屏幕底部 10% 通常为危险区域）
SENSITIVE_ZONE_Y_MIN = 0.90


# 支持的按键列表
SUPPORTED_KEYS = {
    "UP", "DOWN", "LEFT", "RIGHT",
    "ENTER", "DPAD_CENTER", "MENU", "BACK", "HOME",
    "VOLUME_UP", "VOLUME_DOWN", "VOLUME_MUTE",
    "MEDIA_PLAY_PAUSE", "MEDIA_PLAY", "MEDIA_PAUSE",
    "MEDIA_NEXT", "MEDIA_PREVIOUS", "FAST_FORWARD", "REWIND",
}

# 支持的方向列表
SUPPORTED_DIRECTIONS = {"up", "down", "left", "right"}


@dataclass
class ActionGuardConfig:
    """Action Guard 配置。"""
    min_bbox_area: float = 0.0003
    max_bbox_area: float = 0.80
    sensitive_confirm: bool = True
    inner_padding: float = 0.02  # 2% 屏幕内边距


def validate_action(
    action: NextAction,
    screen_width: int,
    screen_height: int,
    subgoal: str,
    config: ActionGuardConfig | None = None,
) -> GuardDecision:
    """校验动作是否合法。

    Args:
        action: VLM 建议的动作
        screen_width: 屏幕宽度（像素）
        screen_height: 屏幕高度（像素）
        subgoal: 用户子目标（用于敏感词检测）
        config: 配置（可选）

    Returns:
        GuardDecision
    """
    config = config or ActionGuardConfig()

    # 1. 检查动作类型是否支持
    if action.type not in NextAction.model_fields["type"].annotation.__args__:
        return GuardDecision(
            False,
            reason=f"Unsupported action type: {action.type}",
            error_code="UNSUPPORTED_ACTION",
        )

    # 2. tap 必须有 target_label 和 bbox
    if action.type == "tap":
        if not action.target_label:
            return GuardDecision(
                False,
                reason="tap requires target_label",
                error_code="MISSING_TARGET_LABEL",
            )
        if not action.bbox_normalized:
            return GuardDecision(
                False,
                reason="tap requires bbox_normalized",
                error_code="MISSING_BBOX",
            )
        bbox = action.bbox_normalized
        if bbox.x1 >= bbox.x2 or bbox.y1 >= bbox.y2:
            return GuardDecision(
                False,
                reason=f"Invalid bbox: x1={bbox.x1} >= x2={bbox.x2} or y1={bbox.y1} >= y2={bbox.y2}",
                error_code="INVALID_BBOX",
            )
        area = bbox.area()
        if area < config.min_bbox_area:
            return GuardDecision(
                False,
                reason=f"bbox area too small: {area:.6f} < {config.min_bbox_area}",
                error_code="BBOX_TOO_SMALL",
            )
        if area > config.max_bbox_area:
            return GuardDecision(
                False,
                reason=f"bbox area too large: {area:.4f} > {config.max_bbox_area}",
                error_code="BBOX_TOO_LARGE",
            )
        # 检查是否在敏感区域
        if bbox.y1 >= SENSITIVE_ZONE_Y_MIN:
            return GuardDecision(
                False,
                reason=f"bbox in sensitive zone: y1={bbox.y1} >= {SENSITIVE_ZONE_Y_MIN}",
                error_code="SENSITIVE_ZONE",
            )

    # 3. remote_key / media_key 必须有合法的 key
    if action.type in ("remote_key", "media_key"):
        if not action.key:
            return GuardDecision(
                False,
                reason=f"{action.type} requires key",
                error_code="MISSING_KEY",
            )
        if action.key.upper() not in SUPPORTED_KEYS:
            return GuardDecision(
                False,
                reason=f"Unsupported key: {action.key}",
                error_code="UNSUPPORTED_KEY",
            )

    # 4. swipe 必须有 direction 和 distance
    if action.type == "swipe":
        if not action.direction:
            return GuardDecision(
                False,
                reason="swipe requires direction",
                error_code="MISSING_DIRECTION",
            )
        if action.direction not in SUPPORTED_DIRECTIONS:
            return GuardDecision(
                False,
                reason=f"Unsupported direction: {action.direction}",
                error_code="UNSUPPORTED_DIRECTION",
            )
        if not action.distance or action.distance < 0.05:
            return GuardDecision(
                False,
                reason=f"swipe distance too small: {action.distance}",
                error_code="INVALID_DISTANCE",
            )

    # 5. type_text 敏感词检测
    if action.type == "type_text":
        if not action.text:
            return GuardDecision(
                False,
                reason="type_text requires text",
                error_code="MISSING_TEXT",
            )
        if config.sensitive_confirm:
            text_lower = action.text.lower()
            for keyword in SENSITIVE_KEYWORDS:
                if keyword in text_lower:
                    return GuardDecision(
                        False,
                        reason=f"Sensitive keyword detected: {keyword}",
                        error_code="SENSITIVE_TEXT",
                    )

    # 6. 检查 subgoal 是否包含敏感词
    if config.sensitive_confirm:
        subgoal_lower = subgoal.lower()
        for keyword in SENSITIVE_KEYWORDS:
            if keyword in subgoal_lower:
                return GuardDecision(
                    False,
                    reason=f"Sensitive subgoal keyword: {keyword}",
                    error_code="SENSITIVE_SUBGOAL",
                )

    # 7. done / ask_user / wait / back / reveal_controls 直接通过
    return GuardDecision(True, action=action, reason="OK")


def tap_to_pixel(
    bbox_normalized,
    screen_width: int,
    screen_height: int,
    inner_padding: float = 0.02,
    vlm_padded_size: int = 1024,
) -> tuple[int, int]:
    """将归一化 bbox 转换为像素坐标（考虑 VLM 的 padding）。

    VLM (qwen-vl-plus) 内部处理:
    1. 将输入图像 resize 到保持宽高比的最长边 1024
    2. 加 padding 变成 1024x1024
    3. 返回的归一化坐标基于 1024x1024

    例如 1280x800 的图像:
    - resize 到 1024x640
    - padding 上下各 192px → 1024x1024
    - VLM 返回的 y=0.75 实际对应原图的 (0.75*1024-192)/0.8 = 720

    Args:
        bbox_normalized: BBox 对象（基于 VLM 的 1024x1024 归一化坐标）
        screen_width: 原始屏幕宽度
        screen_height: 原始屏幕高度
        inner_padding: 内边距比例（默认 2%）
        vlm_padded_size: VLM 的填充后尺寸（默认 1024）

    Returns:
        (x, y) 像素坐标
    """
    # 计算 VLM 的缩放和 padding
    scale = vlm_padded_size / max(screen_width, screen_height)
    scaled_w = int(screen_width * scale)
    scaled_h = int(screen_height * scale)
    pad_x_vlm = (vlm_padded_size - scaled_w) // 2
    pad_y_vlm = (vlm_padded_size - scaled_h) // 2

    # 从 VLM 的归一化坐标反算到原始图像坐标
    # VLM 坐标 → 缩放后坐标 → 原始坐标
    x1_vlm = bbox_normalized.x1 * vlm_padded_size
    y1_vlm = bbox_normalized.y1 * vlm_padded_size
    x2_vlm = bbox_normalized.x2 * vlm_padded_size
    y2_vlm = bbox_normalized.y2 * vlm_padded_size

    # 去除 padding，得到缩放后的坐标
    x1_scaled = x1_vlm - pad_x_vlm
    y1_scaled = y1_vlm - pad_y_vlm
    x2_scaled = x2_vlm - pad_x_vlm
    y2_scaled = y2_vlm - pad_y_vlm

    # 缩放回原始尺寸
    x1_orig = x1_scaled / scale
    y1_orig = y1_scaled / scale
    x2_orig = x2_scaled / scale
    y2_orig = y2_scaled / scale

    # 计算中心
    cx = (x1_orig + x2_orig) / 2
    cy = (y1_orig + y2_orig) / 2

    # 在原始坐标空间加内边距
    w = x2_orig - x1_orig
    h = y2_orig - y1_orig
    pad_x_inner = w * inner_padding
    pad_y_inner = h * inner_padding
    cx = max(x1_orig + pad_x_inner, min(x2_orig - pad_x_inner, cx))
    cy = max(y1_orig + pad_y_inner, min(y2_orig - pad_y_inner, cy))

    x = int(cx)
    y = int(cy)

    # 确保在屏幕内
    x = max(0, min(screen_width - 1, x))
    y = max(0, min(screen_height - 1, y))

    return x, y
