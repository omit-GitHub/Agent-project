# -*- coding: utf-8 -*-
"""Per-App DPAD 键位映射与导航知识。

记录每个 App 在不同场景（player_with_bar / speed_panel / episode_panel 等）下：
  - 可聚焦元素的 resource-id 列表
  - 布局（horizontal_row / vertical_list / grid）
  - 默认焦点元素
  - 达到目标所需的典型导航方向

数据驱动：新增 App / 新场景只改本文件，不动核心逻辑。

注意：这些知识是启发式 + 实测得出的。不同 App 版本可能有差异，
DPAD executor 的 focus_element() 在导航失败时会通过焦点追踪自动调整。
"""

# ─────────────── 爱奇艺 ───────────────

AIQIYI_KEYMAPS = {
    # 播放器页面，控制条已显
    "player_with_bar": {
        "focusable_elements": [
            "btn_pause", "btn_play",             # 播放/暂停
            "im_play_next", "im_play_last",      # 下一集/上一集
            "tv_change_episode",                 # 选集按钮
            "textview_speed",                    # 倍速按钮
            "textview_resolution",               # 清晰度按钮
            "video_detail",                      # 详情按钮
        ],
        "layout": "horizontal_row",
        "default_focus": "btn_pause",
        "navigation": {
            # 从默认焦点到目标的典型方向
            "speed": ("RIGHT", 3),               # 假设默认聚焦在 btn_pause，向右 3 次
            "quality": ("RIGHT", 4),
            "episode": ("RIGHT", 2),
        },
    },

    # 倍速选择面板
    "speed_panel": {
        "focusable_elements": [
            "textview_075_speed",
            "textview_100_speed",
            "textview_125_speed",
            "textview_150_speed",
            "textview_200_speed",
        ],
        "layout": "vertical_list",
        "default_focus": "textview_100_speed",   # 当前倍速（1.0x）通常默认聚焦
    },

    # 清晰度选择面板
    "quality_panel": {
        "focusable_elements": [
            "resolution_270",
            "resolution_480",
            "resolution_720",
            "resolution_1080",
        ],
        "layout": "vertical_list",
    },

    # 选集面板
    "episode_panel": {
        "focusable_elements": ["episode_item"],  # 通用 ID 模式
        "layout": "grid",
        "grid_columns": 6,                       # 常见 6 列网格
    },
}


# ─────────────── 腾讯视频 ───────────────

TENCENT_KEYMAPS = {
    "player_with_bar": {
        "focusable_elements": [
            "playBtn", "pauseBtn",               # 播放/暂停
            "nextBtn", "prevBtn",                # 下一集/上一集
            "speedBtn",                          # 倍速
            "qualityBtn",                        # 清晰度
            "episodeBtn",                        # 选集
            "introBtn",                          # 简介
        ],
        "layout": "horizontal_row",
        "default_focus": "playBtn",
    },

    "speed_panel": {
        "focusable_elements": [
            "speed_050", "speed_075", "speed_100",
            "speed_125", "speed_150", "speed_200",
        ],
        "layout": "vertical_list",
    },

    "quality_panel": {
        "focusable_elements": [
            "quality_270", "quality_480",
            "quality_720", "quality_1080",
        ],
        "layout": "vertical_list",
    },

    "episode_panel": {
        "focusable_elements": ["episode_select_item"],
        "layout": "grid",
        "grid_columns": 6,
    },
}


# ─────────────── 夸克网盘（文件浏览器，非播放器）───────────────

QUARK_KEYMAPS = {
    "file_list": {
        "focusable_elements": ["file_item", "folder_item"],
        "layout": "vertical_list",
    },
}


# ─────────────── 注册表 ───────────────

KEYMAPS = {
    "aiqiyi": AIQIYI_KEYMAPS,
    "tencent": TENCENT_KEYMAPS,
    "quark": QUARK_KEYMAPS,
}


def get_keymap(app: str, context: str):
    """获取指定 App + 场景的 DPAD 键位映射。

    Args:
        app: "aiqiyi" | "tencent" | "quark" | None
        context: "player_with_bar" | "speed_panel" | "quality_panel" | "episode_panel" | ...

    Returns:
        dict 或 None（未配置时返回 None）
    """
    if not app or app not in KEYMAPS:
        return None
    return KEYMAPS[app].get(context)


def list_apps():
    """列出已配置键位映射的 App 名。"""
    return list(KEYMAPS.keys())


def list_contexts(app: str):
    """列出指定 App 已配置的场景名。"""
    if app not in KEYMAPS:
        return []
    return list(KEYMAPS[app].keys())


# ─────────────── 方向键映射 ───────────────

# 方向名 → remote_key 接受的 key 字符串
DIRECTION_TO_KEY = {
    "UP": "UP",
    "DOWN": "DOWN",
    "LEFT": "LEFT",
    "RIGHT": "RIGHT",
}

# 反向映射（用于往回走）
OPPOSITE_DIRECTION = {
    "UP": "DOWN",
    "DOWN": "UP",
    "LEFT": "RIGHT",
    "RIGHT": "LEFT",
}
