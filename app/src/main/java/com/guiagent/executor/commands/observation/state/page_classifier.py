# -*- coding: utf-8 -*-
"""页面类型分类器 — 根据 (pkg, activity, UI 树) 判断 page_type。

分类策略（优先级从高到低）:

1. Package + Activity 快速路径（最高置信度，纯查表，零依赖）
   - 已知 3 个视频 App 的包名 + 播放器 Activity 关键词 → player
   - 已知 launcher 包名 → structured
   - 已知夸克包名 → structured (文件浏览器)

2. UI 树启发式兜底（中等置信度）
   - 树里出现播放器控件 ID（playerControlBar / episodeGridView 等）→ player
   - 树里出现 RecyclerView + 多个 clickable → structured
   - 树里有 WebView 但 clickable 很少 → visual
   - 总节点数 < 5 → visual

3. 兜底 → unknown

不做分类模型：我们只对接 3 个 App，查表比 ML 分类器更可靠、更快、零依赖。
"""
import re
from typing import Optional, Dict, Any

from .schema import (
    PAGE_TYPE_STRUCTURED,
    PAGE_TYPE_VISUAL,
    PAGE_TYPE_PLAYER,
    PAGE_TYPE_UNKNOWN,
    APP_CATEGORY_VIDEO_PLAYER,
    APP_CATEGORY_FILE_BROWSER,
    APP_CATEGORY_LAUNCHER,
    APP_CATEGORY_SYSTEM,
    APP_CATEGORY_UNKNOWN,
)


# ─────────────── 已知 App 包名（查表用）───────────────

# 爱奇艺（TV 版 / 手机端）
AIQIYI_PKGS = {
    "com.qiyi.video.speaker",       # 爱奇艺 TV 版（本项目主目标）
    "com.qiyi.video",               # 爱奇艺手机版
    "com.qiyi.video.pad",           # 爱奇艺 Pad 版
}

# 腾讯视频
TENCENT_PKGS = {
    "com.tencent.qqlive",           # 腾讯视频 TV 版（云视听极光）
    "com.tencent.qqlive.speaker",   # 腾讯视频音响版
    " com.tencent.video",           # 腾讯视频手机版（备用）
}

# 夸克网盘
QUARK_PKGS = {
    "com.quark.browser",            # 夸克浏览器 + 网盘
}

# Launcher（华为中屏盒默认 launcher）
LAUNCHER_PKGS = {
    "com.wohuatv.launcher",         # 哇哈 TV launcher（本项目目标设备）
    "com.huawei.aifttr.digitalpersonshell",  # 数字人 Shell（本项目自身）
    "com.android.launcher",
    "com.android.launcher2",
    "com.android.launcher3",
}

# 视频播放器 Activity 关键词（activity 名包含这些 → 大概率是播放器页）
PLAYER_ACTIVITY_KEYWORDS = (
    "Player", "player",
    "PlayBack", "Playback",
    "DetailActivity",               # 爱奇艺的播放详情页（实际在播）
    "VideoDetail",                  # 腾讯的播放详情页
    "PlayerActivity",
    "VodActivity",
    "LiveActivity",
)

# 非播放器但常见的 Activity 关键词
EPISODE_ACTIVITY_KEYWORDS = ("Episode", "Select", "List")
SEARCH_ACTIVITY_KEYWORDS = ("Search", "search")
SETTINGS_ACTIVITY_KEYWORDS = ("Settings", "settings", "Preference")


# ─────────────── 主入口 ───────────────

def classify_page_type(
    pkg: str,
    activity: str = "",
    tree: Optional[Dict[str, Any]] = None,
    summary: Optional[list] = None,
) -> Dict[str, Any]:
    """根据 (pkg, activity, tree) 分类 page_type 和 app_category。

    Args:
        pkg: 前台包名（来自 dump 或 ping）
        activity: 前台 Activity 名（可选；来自 ping）
        tree: UI 树根节点 dict（可选；来自 dump）
        summary: 可见文字列表（可选；来自 collect_texts）

    Returns:
        {
            "page_type": "player" | "structured" | "visual" | "unknown",
            "app_category": "video_player" | "file_browser" | "launcher" | "system" | "unknown",
            "confidence": "high" | "medium" | "low",
            "method": "pkg_activity" | "tree_heuristic" | "fallback",
        }
    """
    pkg = pkg or ""
    activity = activity or ""

    # ── Step 1: 包名快速路径 ──
    result = _classify_by_package(pkg, activity)
    if result is not None:
        return result

    # ── Step 2: UI 树启发式 ──
    if tree is not None:
        result = _classify_by_tree(tree, summary)
        if result is not None:
            return result

    # ── Step 3: 兜底 ──
    return {
        "page_type": PAGE_TYPE_UNKNOWN,
        "app_category": APP_CATEGORY_UNKNOWN,
        "confidence": "low",
        "method": "fallback",
    }


# ─────────────── 包名 + Activity 分类 ───────────────

def _classify_by_package(pkg: str, activity: str) -> Optional[Dict[str, Any]]:
    """包名 + Activity 快速分类。返回 None 表示无法判断。"""
    if not pkg:
        return None

    # 1. Launcher — 必须最先判断（避免被归为 system）
    if pkg in LAUNCHER_PKGS or _pkg_endswith_any(pkg, (".launcher", ".launcher3")):
        return {
            "page_type": PAGE_TYPE_STRUCTURED,
            "app_category": APP_CATEGORY_LAUNCHER,
            "confidence": "high",
            "method": "pkg_activity",
        }

    # 2. 夸克 — 文件浏览器，总是 structured
    if pkg in QUARK_PKGS:
        return {
            "page_type": PAGE_TYPE_STRUCTURED,
            "app_category": APP_CATEGORY_FILE_BROWSER,
            "confidence": "high",
            "method": "pkg_activity",
        }

    # 3. 爱奇艺 / 腾讯 — 看 Activity 决定是播放器还是别的
    if pkg in AIQIYI_PKGS or pkg in TENCENT_PKGS:
        page_type, app_category = _classify_video_app_activity(activity)
        return {
            "page_type": page_type,
            "app_category": app_category,
            "confidence": "high",
            "method": "pkg_activity",
        }

    # 4. 其他未知视频 App（兜底归类）
    if _looks_like_video_app(pkg):
        page_type, app_category = _classify_video_app_activity(activity)
        return {
            "page_type": page_type,
            "app_category": app_category,
            "confidence": "medium",
            "method": "pkg_activity",
        }

    return None


def _classify_video_app_activity(activity: str):
    """视频 App 内部分类：基于 Activity 名判断是播放器、搜索、还是其他。

    Returns: (page_type, app_category)
    """
    activity = activity or ""

    # 播放器 Activity
    if any(kw in activity for kw in PLAYER_ACTIVITY_KEYWORDS):
        return PAGE_TYPE_PLAYER, APP_CATEGORY_VIDEO_PLAYER

    # 搜索 Activity → structured
    if any(kw in activity for kw in SEARCH_ACTIVITY_KEYWORDS):
        return PAGE_TYPE_STRUCTURED, APP_CATEGORY_VIDEO_PLAYER

    # 设置 Activity → structured
    if any(kw in activity for kw in SETTINGS_ACTIVITY_KEYWORDS):
        return PAGE_TYPE_STRUCTURED, APP_CATEGORY_VIDEO_PLAYER

    # 默认：视频 App 内但未识别具体页面 → 保守归为 structured
    # （让 State Resolver 通过 UI 树再次确认）
    return PAGE_TYPE_STRUCTURED, APP_CATEGORY_VIDEO_PLAYER


def _looks_like_video_app(pkg: str) -> bool:
    """猜测一个包名是否属于视频类 App（启发式）。"""
    hints = ("video", "tv", "media", "player", "vod", "movie", "iqiyi", "tencent", "youku")
    pkg_lower = pkg.lower()
    return any(h in pkg_lower for h in hints)


def _pkg_endswith_any(pkg: str, suffixes) -> bool:
    return any(pkg.endswith(s) for s in suffixes)


# ─────────────── UI 树分类 ───────────────

def _classify_by_tree(
    tree: Dict[str, Any],
    summary: Optional[list] = None,
) -> Optional[Dict[str, Any]]:
    """UI 树启发式分类。返回 None 表示无法判断。"""
    if not tree:
        return None

    stats = _collect_tree_stats(tree)

    # 1. 强播放器信号：出现播放器专属控件 ID
    player_signals = (
        "playercontrolbar", "player_control", "player_bottom_bar",
        "episodegridview", "episode_panel", "player_root",
        "btn_pause", "playbtn", "play_btn",
    )
    for id_lower in stats.get("ids_lower", set()):
        if any(sig in id_lower for sig in player_signals):
            return {
                "page_type": PAGE_TYPE_PLAYER,
                "app_category": APP_CATEGORY_VIDEO_PLAYER,
                "confidence": "medium",
                "method": "tree_heuristic",
            }

    # 2. 节点数过少（<5）→ visual（自绘/WebView）
    if stats["node_count"] < 5:
        return {
            "page_type": PAGE_TYPE_VISUAL,
            "app_category": _infer_app_category_from_tree(stats, summary),
            "confidence": "low",
            "method": "tree_heuristic",
        }

    # 3. 有 RecyclerView / ListView + 多个 clickable → structured
    has_list_widget = stats.get("has_list_widget", False)
    clickable_ratio = (
        stats["clickable_count"] / max(1, stats["node_count"])
    )
    if has_list_widget and clickable_ratio > 0.1:
        return {
            "page_type": PAGE_TYPE_STRUCTURED,
            "app_category": _infer_app_category_from_tree(stats, summary),
            "confidence": "medium",
            "method": "tree_heuristic",
        }

    # 4. 有 WebView 但 clickable 稀少 → visual
    if stats.get("has_webview", False) and clickable_ratio < 0.05:
        return {
            "page_type": PAGE_TYPE_VISUAL,
            "app_category": _infer_app_category_from_tree(stats, summary),
            "confidence": "medium",
            "method": "tree_heuristic",
        }

    return None


def _collect_tree_stats(tree: Dict[str, Any]) -> Dict[str, Any]:
    """DFS 收集 UI 树统计信息。"""
    stats = {
        "node_count": 0,
        "clickable_count": 0,
        "ids_lower": set(),
        "classes": set(),
        "has_list_widget": False,
        "has_webview": False,
        "focused_id": None,
    }

    def visit(node):
        if not node:
            return
        stats["node_count"] += 1

        # ID
        nid = node.get("id", "") or ""
        if nid:
            stats["ids_lower"].add(nid.lower())

        # Class
        cls = node.get("class", "") or ""
        if cls:
            stats["classes"].add(cls)
            cls_lower = cls.lower()
            if "recyclerview" in cls_lower or "listview" in cls_lower \
                    or "gridview" in cls_lower:
                stats["has_list_widget"] = True
            if "webview" in cls_lower:
                stats["has_webview"] = True

        # Clickable
        if node.get("clickable"):
            stats["clickable_count"] += 1

        # Focused（第一个找到的）
        if node.get("focused") and stats["focused_id"] is None:
            stats["focused_id"] = nid

        for child in node.get("children", []) or []:
            visit(child)

    visit(tree)
    return stats


def _infer_app_category_from_tree(stats: Dict[str, Any], summary: Optional[list]) -> str:
    """从树统计 + 可见文字推断 app_category（在 page_type 已确定后调用）。"""
    # 文件浏览器信号：节点多、有"文件"/"文件夹"文字
    if summary:
        text_joined = " ".join(summary)
        if any(kw in text_joined for kw in ("文件", "文件夹", "File", "Folder")):
            return APP_CATEGORY_FILE_BROWSER
    return APP_CATEGORY_UNKNOWN
