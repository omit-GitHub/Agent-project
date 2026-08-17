# -*- coding: utf-8 -*-
"""腾讯视频命令共享常量 — 供 run_toggle / run_speed / run_resolution 等使用。"""


# ─────────────── App 标识 ───────────────

APP_NAME = "tencent"
PKG = "com.tencent.qqlive"


# ─────────────── 播放器控制条唤出 ───────────────

WAKE_X = 640
WAKE_Y = 200


# ─────────────── 播放/暂停按钮 ───────────────

PLAY_BTN_ID = "com.tencent.qqlive.audiobox:id/playBtn"
# fallback 坐标
PLAY_BTN_X = 127
PLAY_BTN_Y = 749


# ─────────────── 倍速 ───────────────

# 倍速按钮坐标（打开倍速面板）
SPEED_BTN_X = 1027
SPEED_BTN_Y = 749

# 倍速选项 → 坐标
SPEED_OPTIONS = {
    "0.5":  (684, 183),
    "0.75": (852, 183),
    "1.0":  (1020, 183),
    "1.25": (1187, 183),
    "1.5":  (684, 284),
    "2.0":  (852, 284),
}

# 倍速选项 → 显示文字
SPEED_TEXTS = {
    "0.5": "0.5x", "0.75": "0.75x", "1.0": "1.0x",
    "1.25": "1.25x", "1.5": "1.5x", "2.0": "2.0x",
}


# ─────────────── 清晰度 ───────────────

# 清晰度按钮坐标
DEFINITION_BTN_X = 1138
DEFINITION_BTN_Y = 749

# 清晰度选项 → 坐标（仅实测过的）
RESOLUTION_OPTIONS = {
    "270": (757, 170),
    "480": (906, 170),
    # 720/1080 待实测
}

# 清晰度选项 → 显示文字
RESOLUTION_TEXTS = {
    "270": "270P", "480": "480P",
    "720": "720P", "1080": "1080P",
}


# ─────────────── 选集 ───────────────

EPISODE_LIST_ID = "episode_select_list"
EPISODE_BTN_X = 828
EPISODE_BTN_Y = 749
NEXT_BTN_X = 214
NEXT_BTN_Y = 749
EPISODE_EXIT_X = 200
EPISODE_EXIT_Y = 400


# ─────────────── 详情 ───────────────

DETAIL_BTN_X = 928
DETAIL_BTN_Y = 749


# ─────────────── 通用 ───────────────

CONTROL_BAR_IDS = (
    "player_bottom_layout", "qlive_bottom",
    "player_control", "playercontrol",
)
