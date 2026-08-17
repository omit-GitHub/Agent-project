# -*- coding: utf-8 -*-
"""Per-App 控件唤出策略 — 数据定义。

每个 App 维护一个优先级动作序列：revealer 依次尝试每个动作，
每个动作后检查控制条是否出现；一旦出现立即停止。

动作格式:
    {
        "action": "tap" | "remote_key" | "swipe" | "wait",
        "args": {...},          # 传给 WS 操作的参数
        "wait_ms": 500,         # 动作后等待动画/渲染的时间
        "desc": "可选描述",      # 调试用
    }

设计原则:
  - 数据驱动：新增 App 只改本文件，不动核心逻辑
  - 第一步通常是 tap 顶部或屏幕中心（最常见唤出方式）
  - 后续是 DPAD ENTER / MENU 等遥控器按键（兜底）
  - wait_ms 必须够动画渲染用（不同 App 差异大）
"""

# ─────────────── 默认/兜底策略 ───────────────

DEFAULT_STRATEGY = [
    {"action": "tap",
     "args": {"x": 640, "y": 400},     # 屏幕中心 tap
     "wait_ms": 1000,
     "desc": "tap screen center"},
    {"action": "remote_key",
     "args": {"key": "ENTER"},          # DPAD 确认键
     "wait_ms": 1000,
     "desc": "DPAD ENTER"},
    {"action": "remote_key",
     "args": {"key": "MENU"},           # 菜单键
     "wait_ms": 1000,
     "desc": "MENU key"},
]


# ─────────────── 爱奇艺 ───────────────

# 已知：tap(640, 200) 唤出控制条；或 DPAD ENTER；或 MENU
# 实测 wait 通常需要 1.5~2 秒
AIQIYI_STRATEGY = [
    {"action": "tap",
     "args": {"x": 640, "y": 200},     # 顶部中央（视频区上方）
     "wait_ms": 1200,
     "desc": "tap top-center (aiqiyi wake)"},
    {"action": "remote_key",
     "args": {"key": "ENTER"},
     "wait_ms": 1000,
     "desc": "DPAD ENTER (aiqiyi alt)"},
    {"action": "remote_key",
     "args": {"key": "MENU"},
     "wait_ms": 1200,
     "desc": "MENU key (aiqiyi fallback)"},
]


# ─────────────── 腾讯视频 ───────────────

# 已知：tap(640, 200) 同样有效；DPAD ENTER 也有效
# 腾讯视频动画较慢，wait 至少 1.5s
TENCENT_STRATEGY = [
    {"action": "tap",
     "args": {"x": 640, "y": 200},
     "wait_ms": 1500,
     "desc": "tap top-center (tencent wake)"},
    {"action": "remote_key",
     "args": {"key": "ENTER"},
     "wait_ms": 1200,
     "desc": "DPAD ENTER (tencent alt)"},
    {"action": "remote_key",
     "args": {"key": "MENU"},
     "wait_ms": 1200,
     "desc": "MENU key (tencent fallback)"},
]


# ─────────────── 夸克网盘 ───────────────

# 夸克是文件浏览器，没有播放器控制条概念。
# 但某些场景（如视频预览页）可能需要唤出控件。
# 这里提供一个通用策略，具体以实测为准。
QUARK_STRATEGY = [
    {"action": "tap",
     "args": {"x": 640, "y": 400},
     "wait_ms": 800,
     "desc": "tap screen center (quark)"},
    {"action": "remote_key",
     "args": {"key": "ENTER"},
     "wait_ms": 800,
     "desc": "DPAD ENTER (quark alt)"},
]


# ─────────────── 策略注册表 ───────────────

# app 名 → 策略列表
# app 名来自 state_resolver 的 pkg 推断（"aiqiyi" / "tencent" / "quark"）
STRATEGIES = {
    "aiqiyi": AIQIYI_STRATEGY,
    "tencent": TENCENT_STRATEGY,
    "quark": QUARK_STRATEGY,
    "_default": DEFAULT_STRATEGY,
}


def get_strategy(app: str):
    """根据 app 名获取唤出策略。

    Args:
        app: "aiqiyi" | "tencent" | "quark" | None / 其他

    Returns:
        list of action dicts（至少包含 _default 兜底）
    """
    return STRATEGIES.get(app, DEFAULT_STRATEGY)


def list_apps():
    """列出已配置策略的 App 名（不含 _default）。"""
    return [k for k in STRATEGIES.keys() if not k.startswith("_")]
