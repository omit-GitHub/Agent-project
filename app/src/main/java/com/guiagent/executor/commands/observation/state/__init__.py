# -*- coding: utf-8 -*-
"""UI State 子包 — UI State Resolver。

对外暴露:
  - resolve_state() → StateSnapshot  (主入口，在 resolver.py)
  - StateSnapshot / PlayerState      (数据结构，在 schema.py)
  - classify_page_type()             (页面分类，在 page_classifier.py)
  - detect_player_state()            (播放器状态检测，在 player_state.py)
"""
from .schema import (
    StateSnapshot,
    PlayerState,
    empty_snapshot,
    snapshot_from_legacy,
    PAGE_TYPE_STRUCTURED,
    PAGE_TYPE_VISUAL,
    PAGE_TYPE_PLAYER,
    PAGE_TYPE_HIDDEN_CONTROLS,
    PAGE_TYPE_UNKNOWN,
    APP_CATEGORY_VIDEO_PLAYER,
    APP_CATEGORY_FILE_BROWSER,
    APP_CATEGORY_LAUNCHER,
    APP_CATEGORY_SYSTEM,
    APP_CATEGORY_UNKNOWN,
    OVERLAY_SPEED_PANEL,
    OVERLAY_QUALITY_PANEL,
    OVERLAY_EPISODE_PANEL,
    OVERLAY_DETAIL_PANEL,
)
from .resolver import resolve_state
from .page_classifier import classify_page_type
from .player_state import detect_player_state

__all__ = [
    # 主入口
    "resolve_state",
    # 数据结构
    "StateSnapshot",
    "PlayerState",
    # 工厂
    "empty_snapshot",
    "snapshot_from_legacy",
    # 子能力
    "classify_page_type",
    "detect_player_state",
    # 常量
    "PAGE_TYPE_STRUCTURED",
    "PAGE_TYPE_VISUAL",
    "PAGE_TYPE_PLAYER",
    "PAGE_TYPE_HIDDEN_CONTROLS",
    "PAGE_TYPE_UNKNOWN",
    "APP_CATEGORY_VIDEO_PLAYER",
    "APP_CATEGORY_FILE_BROWSER",
    "APP_CATEGORY_LAUNCHER",
    "APP_CATEGORY_SYSTEM",
    "APP_CATEGORY_UNKNOWN",
    "OVERLAY_SPEED_PANEL",
    "OVERLAY_QUALITY_PANEL",
    "OVERLAY_EPISODE_PANEL",
    "OVERLAY_DETAIL_PANEL",
]
