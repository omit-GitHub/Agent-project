# -*- coding: utf-8 -*-
"""UI State Resolver — 主入口 resolve_state()。

职责:
  1. 通过 WS ping 获取屏幕信息（pkg, activity, screen_size）
  2. 通过 WS dump 获取 UI 树
  3. 通过 collect_texts 提取可见文字
  4. 调用 page_classifier 分类 page_type + app_category
  5. 调用 player_state 检测播放器子状态
  6. 调用 detect_overlay 检测浮层类型
  7. 组装 StateSnapshot 返回

返回的 StateSnapshot 是 to_dict() 之后直接给 registry / Agent 用的。
任何一步失败都不会抛异常 —— 兜底返回 empty_snapshot()，并在 dump_status 标记。
"""
import hashlib
import json
import os
import sys
import traceback
from typing import Optional, Dict, Any

# 确保能找到 send / common 模块
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from send import send                                         # noqa: E402
from common.utils import collect_texts                        # noqa: E402

from .schema import (                                         # noqa: E402
    StateSnapshot,
    PlayerState,
    empty_snapshot,
    PAGE_TYPE_UNKNOWN,
    APP_CATEGORY_UNKNOWN,
)
from .page_classifier import classify_page_type               # noqa: E402
from .player_state import detect_player_state, detect_overlay # noqa: E402


# ─────────────── 常量 ───────────────

# dump 参数
DUMP_DEPTH = 5
DUMP_INCLUDE = ["id", "text", "class", "clickable", "enabled",
                "focused", "bounds", "content_desc", "pkg"]

# 收集可见文字的参数
MAX_SUMMARY_TEXTS = 15
MAX_TEXT_LEN = 40

# 我们自己 App 的包名（ping 会错误返回这个，需要替换）
_OWN_PKG = "com.huawei.aifttr.digitalpersonshell"


# ─────────────── 主入口 ───────────────

def resolve_state(force_refresh: bool = False) -> StateSnapshot:
    """采集并返回当前设备状态的结构化快照。

    Args:
        force_refresh: True 则强制重采；False 时可接缓存（暂不实现缓存）。

    Returns:
        StateSnapshot（任何失败都返回空快照 + dump_status="failed"）

    调用链:
        ping → dump → classify → detect_player → detect_overlay → assemble
    """
    try:
        # 1. Ping —— 获取 pkg / activity / screen_size
        ping_resp = send({"id": "rs_ping", "op": "ping", "args": {}})
        if not ping_resp.get("ok"):
            return _failed_snapshot("ping_failed")

        ping_data = ping_resp.get("data", {})
        pkg = ping_data.get("package", "") or ping_data.get("pkg", "")
        activity = ping_data.get("activity", "")
        screen = ping_data.get("screen", {})
        screen_size = {
            "width": screen.get("w", screen.get("width", 1280)),
            "height": screen.get("h", screen.get("height", 800)),
        }

        # 2. Dump —— 获取 UI 树
        dump_resp = send({
            "id": "rs_dump",
            "op": "dump",
            "args": {"depth": DUMP_DEPTH, "include": DUMP_INCLUDE},
        })
        if not dump_resp.get("ok"):
            # dump 失败 —— 仍能用 ping 数据给出基础状态
            return StateSnapshot(
                pkg=pkg,
                activity=activity,
                screen_size=screen_size,
                dump_status="unavailable",
                page_type=PAGE_TYPE_UNKNOWN,
                app_category=APP_CATEGORY_UNKNOWN,
            )

        window = dump_resp.get("data", {}).get("window", {}) or {}
        tree = window if window else dump_resp.get("data", {})

        # Work around Java ping/dump bug: 如果 pkg 是自己的 App，从 UI 树提取真实 pkg
        if pkg == _OWN_PKG or not pkg:
            tree_pkg = _extract_pkg_from_tree(tree)
            if tree_pkg:
                pkg = tree_pkg

        # 3. 提取可见文字
        summary = collect_texts(
            tree, max_count=MAX_SUMMARY_TEXTS, max_len=MAX_TEXT_LEN
        )

        # dump 状态判断
        node_count = _count_nodes(tree)
        if node_count == 0:
            dump_status = "empty"
        elif node_count < 10:
            dump_status = "partial"
        else:
            dump_status = "ok"

        # 4. 计算 screen_version（与 observe_screen 同格式）
        tree_json = json.dumps(tree, sort_keys=True, ensure_ascii=False)
        tree_hash = hashlib.md5(tree_json.encode("utf-8")).hexdigest()[:12] if tree_json else "none"
        screen_version = f"{pkg}:{activity}:dump:{tree_hash}"

        # 5. 分类 page_type + app_category
        classification = classify_page_type(
            pkg=pkg, activity=activity, tree=tree, summary=summary
        )
        page_type = classification.get("page_type", PAGE_TYPE_UNKNOWN)
        app_category = classification.get("app_category", APP_CATEGORY_UNKNOWN)

        # 6. 检测播放器子状态
        from .schema import APP_CATEGORY_VIDEO_PLAYER
        player: Optional[PlayerState] = None
        if app_category == APP_CATEGORY_VIDEO_PLAYER or page_type == "player":
            player = detect_player_state(tree, pkg=pkg, app_category=app_category)

        # 7. 检测浮层类型
        overlay = detect_overlay(tree)

        # 8. 焦点元素
        focused_element = _extract_focused_element(tree)

        # 9. 组装
        snapshot = StateSnapshot(
            pkg=pkg,
            activity=activity,
            summary=summary,
            screen_version=screen_version,
            page_type=page_type,
            app_category=app_category,
            player=player,
            focused_element=focused_element,
            overlay=overlay,
            dump_status=dump_status,
            screen_size=screen_size,
        )

        # 校验（非法值会抛 ValueError —— 我们在这里捕获并降级）
        try:
            snapshot.validate()
        except ValueError:
            snapshot.page_type = PAGE_TYPE_UNKNOWN

        return snapshot

    except Exception as e:
        traceback.print_exc()
        return _failed_snapshot(f"exception: {e}")


# ─────────────── 辅助 ───────────────

def _failed_snapshot(reason: str) -> StateSnapshot:
    """构造失败兜底快照。"""
    return StateSnapshot(
        dump_status="failed",
        page_type=PAGE_TYPE_UNKNOWN,
        app_category=APP_CATEGORY_UNKNOWN,
        # summary 里留下失败原因，便于调试
        summary=[f"[resolve_state failed: {reason}]"],
    )


def _count_nodes(tree: Dict[str, Any]) -> int:
    """DFS 数节点总数。"""
    if not tree:
        return 0
    count = 1
    for child in tree.get("children", []) or []:
        count += _count_nodes(child)
    return count


def _extract_focused_element(tree: Dict[str, Any]) -> Optional[str]:
    """找到第一个 focused=true 的节点的 resource-id。"""
    if not tree:
        return None
    if tree.get("focused"):
        return tree.get("id") or None
    for child in tree.get("children", []) or []:
        found = _extract_focused_element(child)
        if found:
            return found
    return None


def _extract_pkg_from_tree(tree: Dict[str, Any]) -> str:
    """从 UI 树中提取前台 App 的真实包名。

    Java 端 ping/dump 错误返回无障碍服务自己的包名（_OWN_PKG），
    但 UI 树里节点的 id 字段形如 "com.qiyi.video.speaker:id/btn_pause"，
    包含真实包名。通过统计 id 前缀出现次数，取最多的作为前台 App。

    Returns:
        包名字符串，找不到则返回空字符串
    """
    if not tree:
        return ""
    pkg_counts: Dict[str, int] = {}

    def visit(node):
        if not node:
            return
        nid = node.get("id") or ""
        if ":" in nid:
            pkg = nid.split(":", 1)[0]
            if pkg and pkg != _OWN_PKG:
                pkg_counts[pkg] = pkg_counts.get(pkg, 0) + 1
        for child in node.get("children", []) or []:
            visit(child)

    visit(tree)
    if not pkg_counts:
        return ""
    # 返回出现次数最多的 pkg
    return max(pkg_counts, key=pkg_counts.get)


# ─────────────── 便捷方法 ───────────────

def get_state_dict() -> Dict[str, Any]:
    """resolve_state() 的 dict 版本，便于 JSON 序列化。

    用于:
      - registry._attach_state() 替代原 capture_state()
      - common/cmd_get_state.py 的响应
    """
    return resolve_state().to_dict()
