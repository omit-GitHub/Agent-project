# -*- coding: utf-8 -*-
"""焦点追踪器 — 通过 UI 树 diff 检测焦点移动。

核心能力:
  - find_focused_node(tree): 找到 focused=true 的节点
  - detect_focus_change(tree_before, tree_after): 检测焦点是否移动

设计要点:
  - 不依赖坐标（DPAD 导航的关键：焦点变化才是真实信号）
  - 一次 DFS 找第一个 focused=true 节点（多焦点场景取第一个）
  - 容错：树为空 / 无焦点节点 都返回 None，不抛错
"""
from typing import Optional, Dict, Any, Tuple


# ─────────────── 主入口 ───────────────

def find_focused_node(tree: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """在 UI 树中找第一个 focused=true 的节点。

    Returns:
        节点 dict 或 None（无焦点节点 / 树为空）
    """
    if not tree:
        return None

    # 根节点自己可能 focused
    if tree.get("focused"):
        return tree

    # DFS
    stack = list(tree.get("children", []) or [])
    while stack:
        node = stack.pop()
        if not node:
            continue
        if node.get("focused"):
            return node
        # 子节点入栈（反向保持 DFS 顺序）
        children = node.get("children", []) or []
        stack.extend(reversed(children))

    return None


def get_focused_id(tree: Optional[Dict[str, Any]]) -> Optional[str]:
    """获取焦点节点的 resource-id。无焦点返回 None。"""
    node = find_focused_node(tree)
    if node is None:
        return None
    return (node.get("id") or "").strip() or None


def get_focused_info(tree: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """获取焦点节点的摘要信息（id + text + class + bounds）。

    Returns:
        {"id": ..., "text": ..., "class": ..., "bounds": {...}} 或 None
    """
    node = find_focused_node(tree)
    if node is None:
        return None
    return {
        "id": (node.get("id") or "").strip() or None,
        "text": (node.get("text") or "").strip(),
        "content_desc": (node.get("content_desc") or node.get("contentDescription")
                         or node.get("desc") or "").strip(),
        "class": (node.get("class") or "").strip(),
        "bounds": node.get("bounds"),
        "clickable": bool(node.get("clickable")),
    }


def detect_focus_change(
    tree_before: Optional[Dict[str, Any]],
    tree_after: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """检测两次 dump 之间焦点是否移动。

    Returns:
        {
            "focus_moved": bool,
            "tracking_available": bool,       # 是否能追踪（至少一棵树有焦点）
            "old_focus_id": str or None,
            "new_focus_id": str or None,
            "old_focus_text": str or None,
            "new_focus_text": str or None,
            "new_focus_info": dict or None,   # 新焦点节点的完整摘要
        }
    """
    old_id = get_focused_id(tree_before)
    new_id = get_focused_id(tree_after)

    old_node = find_focused_node(tree_before)
    new_node = find_focused_node(tree_after)

    old_text = (old_node.get("text") or "").strip() if old_node else None
    new_text = (new_node.get("text") or "").strip() if new_node else None

    tracking_available = old_id is not None or new_id is not None

    # 焦点移动判定：
    # - 两边都有焦点：id 不同即移动
    # - 只有新树有焦点：视为"获得焦点"（也算 moved）
    # - 只有旧树有焦点：视为"失去焦点"（也算 moved）
    # - 两边都没焦点：未移动（但 tracking_available=False）
    if old_id is None and new_id is None:
        focus_moved = False
    else:
        focus_moved = (old_id != new_id)

    return {
        "focus_moved": focus_moved,
        "tracking_available": tracking_available,
        "old_focus_id": old_id,
        "new_focus_id": new_id,
        "old_focus_text": old_text,
        "new_focus_text": new_text,
        "new_focus_info": get_focused_info(tree_after),
    }


# ─────────────── 树比较辅助 ───────────────

def tree_hash(tree: Optional[Dict[str, Any]]) -> Optional[str]:
    """计算树的轻量 hash（用于快速判断树是否完全相同）。

    不比较 children 顺序，只比较节点集合。
    """
    if not tree:
        return None
    import hashlib
    import json
    try:
        s = json.dumps(tree, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(s.encode("utf-8")).hexdigest()[:12]
    except Exception:
        return None
