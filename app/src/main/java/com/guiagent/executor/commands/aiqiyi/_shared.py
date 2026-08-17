# -*- coding: utf-8 -*-
"""爱奇艺命令共享常量 — 供 run_toggle / run_speed / run_resolution 等使用。

把散落在各 run_*.py 里的常量集中到这里，避免重复定义。
重构 v2 后，这些常量主要用作 fallback（主路径改为 DPAD/节点点击，
坐标点击只在节点查找失败时兜底）。
"""


# ─────────────── App 标识 ───────────────

APP_NAME = "aiqiyi"
PKG = "com.qiyi.video.speaker"


# ─────────────── 播放器控制条唤出 ───────────────

WAKE_X = 640
WAKE_Y = 200


# ─────────────── 播放/暂停按钮 ───────────────

BTN_PAUSE_ID = "com.qiyi.video.speaker:id/btn_pause"
# fallback 坐标（节点查找失败时用）
BTN_PAUSE_X = 55
BTN_PAUSE_Y = 724


# ─────────────── 倍速 ───────────────

# 倍速选项 → 节点 resource-id 子串
SPEED_OPTIONS = {
    "0.75": "textview_075_speed",
    "1.0":  "textview_100_speed",
    "1.25": "textview_125_speed",
    "1.5":  "textview_150_speed",
    "2.0":  "textview_200_speed",
}

# fallback 坐标（TV 模式 vs 电影模式 位置不同）
TV_SPEED_BTN = (846, 724)
MOVIE_SPEED_BTN = (988, 724)


# ─────────────── 清晰度 ───────────────

# 清晰度模式 → 匹配文字
RESOLUTION_PATTERNS = {
    "270": ["270P", "270p"],
    "480": ["480P", "480p"],
    "720": ["720P", "720p"],
    "1080": ["1080P", "1080p"],
}

# fallback 坐标
TV_RESOLUTION_BTN = (1029, 724)
MOVIE_RESOLUTION_BTN = (1171, 724)


# ─────────────── 选集 ───────────────

EPISODE_GRID_ID = "episodeGridView"
EPISODE_PANEL_TITLE_ID = "episodePanelTitle"
EPISODE_BTN_X = 1212
EPISODE_BTN_Y = 724
NEXT_BTN_X = 177
NEXT_BTN_Y = 724


# ─────────────── 详情 ───────────────

DETAIL_ID = "video_detail"
DETAIL_FALLBACK_X = 513
DETAIL_FALLBACK_Y = 97
DETAIL_EXIT_X = 200
DETAIL_EXIT_Y = 400


# ─────────────── 通用 ───────────────

CONTROL_BAR_IDS = (
    "playerControlBar", "player_bottom_bar",
    "player_control", "playerbottombar",
)
