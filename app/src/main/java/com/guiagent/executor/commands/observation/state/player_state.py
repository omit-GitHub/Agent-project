# -*- coding: utf-8 -*-
"""播放器状态检测 — 从 UI 树中检测播放器子状态字段。

检测字段:
  - control_bar_visible: 控制条是否可见
  - is_playing: 是否正在播放
  - current_speed: 当前倍速
  - current_quality: 当前清晰度
  - episode_panel_open: 选集面板是否打开
  - focused_element_id: 当前焦点元素的 resource-id
  - current_episode: 当前集数/标题

所有检测基于 a11y 树的节点 ID / text / content-desc。不依赖坐标或 OCR。

设计要点:
  - 全部是"尽力而为"（best-effort）：找不到就返回 None，不抛错
  - 多个检测源互相兜底（ID 匹配 → 文本匹配 → 兜底 None）
  - 不假设特定 App，跨爱奇艺/腾讯通用（靠通用 ID 模式）
"""
from typing import Optional, Dict, Any, List

from .schema import (
    PlayerState,
    OVERLAY_SPEED_PANEL,
    OVERLAY_QUALITY_PANEL,
    OVERLAY_EPISODE_PANEL,
    OVERLAY_DETAIL_PANEL,
)


# ─────────────── 检测用 ID/文本模式 ───────────────

# 控制条容器 ID（任一出现 → 控制条可见）
CONTROL_BAR_ID_PATTERNS = (
    "playercontrolbar", "player_control_bar",
    "player_bottom_bar", "playerbottombar",
    "player_control", "playercontrol",
    "control_bar", "controlbar",
    "bottom_control", "player_bottom",
    # 爱奇艺
    "iqiyi_player_bottom", "qiyi_control",
    # 腾讯
    "player_bottom_layout", "qlive_bottom",
)

# 播放/暂停按钮 ID（用于判断 is_playing）
PLAYING_ID_PATTERNS = (
    "btn_pause", "btnpause", "pause_btn",       # 暂停按钮 = 正在播放
    "pausebtn", "player_pause",
)
PAUSED_ID_PATTERNS = (
    "btn_play", "btnplay", "play_btn",          # 播放按钮 = 已暂停
    "playbtn", "player_play",
)

# 选集面板 ID
EPISODE_PANEL_ID_PATTERNS = (
    "episodegridview", "episode_grid",
    "episode_panel", "episodepanel",
    "episode_select_list", "episode_list_panel",
    "select_episode_view",
)

# 倍速面板 ID / 文本
SPEED_PANEL_ID_PATTERNS = (
    "speed_panel", "speedpanel",
    "playback_speed", "speed_select",
    "change_speed", "speed_list",
)
SPEED_TEXT_PATTERNS = ("0.75x", "1.0x", "1.25x", "1.5x", "2.0x",
                       "0.75倍", "1.0倍", "1.25倍", "1.5倍", "2.0倍",
                       "倍速")

# 清晰度面板 ID / 文本
QUALITY_PANEL_ID_PATTERNS = (
    "quality_panel", "qualitypanel",
    "resolution_panel", "clarity_panel",
    "definition_select", "quality_select",
)
QUALITY_TEXT_PATTERNS = ("270P", "480P", "720P", "1080P", "4K",
                         "标清", "高清", "超清", "蓝光", "清晰度")

# 详情页 ID
DETAIL_PANEL_ID_PATTERNS = (
    "video_detail", "videodetail",
    "detail_panel", "detailpanel",
    "detail_view", "info_panel",
)

# 进度条 / 时间 ID（用于提取 progress_seconds 和 current_episode）
PROGRESS_TEXT_PATTERNS = (r"\d+:\d+",)  # MM:SS 或 HH:MM:SS
EPISODE_TEXT_PATTERN = r"第\s*(\d+)\s*集"


# ─────────────── 主入口 ───────────────

def detect_player_state(
    tree: Optional[Dict[str, Any]],
    pkg: str = "",
    app_category: str = "",
) -> Optional[PlayerState]:
    """从 UI 树检测播放器子状态。

    非播放器场景（app_category != video_player 且树里没有播放器信号）
    返回 None（让 StateSnapshot.player 为 None）。

    Args:
        tree: UI 树根节点 dict
        pkg: 前台包名（用于辅助判断）
        app_category: 已知的 app 类别（如果已分类）

    Returns:
        PlayerState 或 None
    """
    if tree is None:
        return None

    # 收集一次树信息，给所有检测器复用
    ctx = _build_detection_context(tree)

    # 非播放器场景快速退出（如果明确知道不是视频 App 且无播放器信号）
    from .schema import APP_CATEGORY_VIDEO_PLAYER
    is_video_app = (app_category == APP_CATEGORY_VIDEO_PLAYER)
    has_player_signal = ctx.has_player_signal
    if not is_video_app and not has_player_signal:
        return None

    # 构造 PlayerState
    return PlayerState(
        control_bar_visible=_detect_control_bar_visible(ctx),
        is_playing=_detect_is_playing(ctx),
        current_speed=_detect_current_speed(ctx),
        current_quality=_detect_current_quality(ctx),
        episode_panel_open=_detect_episode_panel_open(ctx),
        focused_element_id=ctx.focused_id,
        progress_seconds=None,          # 暂不实现（需 OCR 或进度条解析）
        current_episode=_detect_current_episode(ctx),
    )


# ─────────────── 上下文构造 ───────────────

class _DetectionContext:
    """检测上下文 —— 一次 DFS 收集所有检测器需要的信息。"""
    def __init__(self):
        self.ids_lower: set = set()        # 所有节点 ID 的小写形式
        self.all_texts: List[str] = []     # 所有可见文字（text + content-desc）
        self.focused_id: Optional[str] = None
        self.has_player_signal: bool = False
        self.node_count: int = 0


def _build_detection_context(tree: Dict[str, Any]) -> _DetectionContext:
    """一次 DFS 收集所有检测器需要的信息。"""
    ctx = _DetectionContext()

    def visit(node):
        if not node:
            return
        ctx.node_count += 1

        # ID
        nid = (node.get("id") or "").strip()
        if nid:
            nid_lower = nid.lower()
            ctx.ids_lower.add(nid_lower)
            # 播放器信号检测
            if not ctx.has_player_signal:
                if any(p in nid_lower for p in CONTROL_BAR_ID_PATTERNS) \
                        or any(p in nid_lower for p in EPISODE_PANEL_ID_PATTERNS) \
                        or any(p in nid_lower for p in PLAYING_ID_PATTERNS) \
                        or any(p in nid_lower for p in PAUSED_ID_PATTERNS):
                    ctx.has_player_signal = True
            # 焦点检测（第一个 focused=true 的节点）
            if node.get("focused") and ctx.focused_id is None:
                ctx.focused_id = nid

        # 文字
        for key in ("text", "content_desc", "contentDescription", "desc"):
            t = (node.get(key) or "").strip()
            if t and t not in ctx.all_texts:
                ctx.all_texts.append(t)

        for child in node.get("children", []) or []:
            visit(child)

    visit(tree)
    return ctx


# ─────────────── 各字段检测 ───────────────

def _detect_control_bar_visible(ctx: _DetectionContext) -> bool:
    """控制条是否可见 —— 高置信度：ID 匹配任一控制条模式。"""
    for id_lower in ctx.ids_lower:
        if any(p in id_lower for p in CONTROL_BAR_ID_PATTERNS):
            return True
    return False


def _detect_is_playing(ctx: _DetectionContext) -> Optional[bool]:
    """是否正在播放 —— 基于播放/暂停按钮哪个存在。

    Returns:
        True: 看到暂停按钮（说明正在播放）
        False: 看到播放按钮（说明已暂停）
        None: 都看不到 / 都不确定
    """
    has_pause = any(
        any(p in id_lower for p in PLAYING_ID_PATTERNS)
        for id_lower in ctx.ids_lower
    )
    has_play = any(
        any(p in id_lower for p in PAUSED_ID_PATTERNS)
        for id_lower in ctx.ids_lower
    )
    if has_pause and not has_play:
        return True
    if has_play and not has_pause:
        return False
    return None


def _detect_current_speed(ctx: _DetectionContext) -> Optional[str]:
    """当前倍速 —— 基于可见文字匹配倍速模式。"""
    for t in ctx.all_texts:
        # 精确匹配 "1.5x" / "1.5倍" 模式
        for pat in ("0.75x", "1.0x", "1.25x", "1.5x", "2.0x",
                    "0.75倍", "1.0倍", "1.25倍", "1.5倍", "2.0倍"):
            if pat in t:
                # 提取数字部分
                return pat.replace("x", "").replace("倍", "")
    return None


def _detect_current_quality(ctx: _DetectionContext) -> Optional[str]:
    """当前清晰度 —— 基于可见文字匹配清晰度模式。"""
    for t in ctx.all_texts:
        for pat in ("270P", "480P", "720P", "1080P", "4K"):
            if pat in t.upper():
                return pat
    return None


def _detect_episode_panel_open(ctx: _DetectionContext) -> bool:
    """选集面板是否打开 —— ID 匹配任一选集面板模式。"""
    for id_lower in ctx.ids_lower:
        if any(p in id_lower for p in EPISODE_PANEL_ID_PATTERNS):
            return True
    return False


def _detect_current_episode(ctx: _DetectionContext) -> Optional[str]:
    """当前集数 —— 基于可见文字匹配"第N集"模式。"""
    import re
    for t in ctx.all_texts:
        m = re.search(EPISODE_TEXT_PATTERN, t)
        if m:
            return m.group(0)  # 返回整段匹配（如"第3集"）
    return None


# ─────────────── Overlay 检测（辅助）───────────────

def detect_overlay(tree: Optional[Dict[str, Any]]) -> Optional[str]:
    """检测当前打开的浮层类型（speed_panel / quality_panel / episode_panel / detail_panel / None）。"""
    if tree is None:
        return None
    ctx = _build_detection_context(tree)

    # 优先级：倍速 > 清晰度 > 选集 > 详情
    for id_lower in ctx.ids_lower:
        if any(p in id_lower for p in SPEED_PANEL_ID_PATTERNS):
            return OVERLAY_SPEED_PANEL
    for id_lower in ctx.ids_lower:
        if any(p in id_lower for p in QUALITY_PANEL_ID_PATTERNS):
            return OVERLAY_QUALITY_PANEL
    for id_lower in ctx.ids_lower:
        if any(p in id_lower for p in EPISODE_PANEL_ID_PATTERNS):
            return OVERLAY_EPISODE_PANEL
    for id_lower in ctx.ids_lower:
        if any(p in id_lower for p in DETAIL_PANEL_ID_PATTERNS):
            return OVERLAY_DETAIL_PANEL
    return None
