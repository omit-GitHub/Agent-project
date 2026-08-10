# -*- coding: utf-8 -*-
"""夸克网盘命令包。

提供夸克网盘 (com.quark.yun.tv) 的专用操作命令:
  - launch_app      启动夸克网盘 APP
  - click_navigation 顶部导航栏点击
  - scroll_up       搜索结果向上翻页
  - scroll_down     搜索结果向下翻页
  - select_file     选择文件/搜索结果
  - go_back         智能返回
  - search          搜索功能

共享内部工具:
  - find_file_items   在 UI 树中定位文件项列表
  - group_items_by_row 按行分组
  - file_item_text    提取文件项文本
  - build_search_result 构建搜索结果数据
"""

import re

from common.utils import (
    dump, find_nodes,
    find_all_nodes_in_tree, node_center, node_bounds, node_height,
    collect_texts,
)


# ─────────────────────── 内部工具：文件项识别 ───────────────────────

def find_file_items(root=None):
    """在 UI 树中找到文件项列表（对标 Java QuarkFileItems.find）。

    选择直接子项最多的 RecyclerView，过滤宽/高 >= 80 的项，
    按 (top, left) 排序（从上到下、从左到右）。

    Args:
        root: UI 树根节点 dict。为 None 时自动 dump。

    Returns:
        list[node]: 排序后的文件项节点列表。
    """
    if root is None:
        r = dump(depth=10)
        if not r.get("ok"):
            return []
        root = r.get("data", {}).get("window", {})

    rv_children = _find_best_rv_children(root)
    if not rv_children:
        return []

    items = []
    for child in rv_children:
        l, t, r_bound, b = node_bounds(child)
        h = b - t
        w = r_bound - l
        if w >= 80 and h >= 80:
            items.append(child)

    items.sort(key=lambda n: (node_bounds(n)[1], node_bounds(n)[0]))
    return items


def _find_best_rv_children(node):
    """递归找到子项最多的 RecyclerView 的 children 列表。"""
    if node is None:
        return None

    best = None
    max_count = 0

    cls = node.get("cls", "")
    if "RecyclerView" in cls:
        children = node.get("children", [])
        if len(children) > max_count:
            best = children
            max_count = len(children)

    for child in node.get("children", []):
        result = _find_best_rv_children(child)
        if result is not None and len(result) > max_count:
            best = result
            max_count = len(result)

    return best


def group_items_by_row(items, tolerance=50):
    """按 y 坐标将文件项分组为行（对标 Java QuarkFileItems.groupByRow）。

    行内容差 tolerance 以内归为同一行，行内按 x 排序，行间按 y 排序。
    """
    if not items:
        return []

    rows = []
    for item in items:
        _, cy = node_center(item)
        matched = None
        for row in rows:
            _, row_cy = node_center(row[0])
            if abs(cy - row_cy) < tolerance:
                matched = row
                break
        if matched is None:
            matched = []
            rows.append(matched)
        matched.append(item)

    for row in rows:
        row.sort(key=lambda n: node_bounds(n)[0])
    rows.sort(key=lambda row: node_bounds(row[0])[1])
    return rows


def file_item_text(item):
    """提取文件项的文本（对标 Java QuarkFileItems.text）。

    优先从子节点递归获取文本；自身文本长度 <= 2 时忽略。
    """
    if item is None:
        return ""
    for child in item.get("children", []):
        t = file_item_text(child)
        if t:
            return t
    text = item.get("text", "").strip()
    return text if len(text) > 2 else ""


# ─────────────────────── 内部工具：搜索结果构建 ───────────────────────

def build_search_result(keyword, root, file_items):
    """构建夸克搜索的统一结果字段（对标 Java QuarkSearchResult.build）。

    Args:
        keyword: 搜索关键词
        root: UI 树根节点
        file_items: 文件项列表

    Returns:
        dict: {"query", "search_status", "count", "items", "result"}
    """
    query_echoed = _is_query_echoed(root, keyword, file_items)

    if not query_echoed:
        search_status = "unknown"
    elif len(file_items) == 0:
        search_status = "not_found"
    else:
        search_status = "found"

    items = []
    for i, item in enumerate(file_items):
        items.append({
            "index": i + 1,
            "text": file_item_text(item),
        })

    return {
        "query": keyword,
        "search_status": search_status,
        "count": len(file_items),
        "items": items,
        "result": "search_" + keyword,
    }


def _is_query_echoed(root, keyword, file_items):
    """检查搜索关键词是否回显在 UI 中（非文件项区域内）。"""
    if not root or not keyword or not keyword.strip():
        return False
    expected = keyword.strip().lower()
    return _contains_exact_outside(root, expected, set(id(f) for f in file_items))


def _contains_exact_outside(node, expected, item_ids):
    """在 UI 树中查找精确文本匹配（排除文件项节点）。"""
    if node is None or id(node) in item_ids:
        return False
    text = node.get("text", "")
    if text and text.strip().lower() == expected:
        return True
    desc = node.get("desc", "")
    if desc and desc.strip().lower() == expected:
        return True
    for child in node.get("children", []):
        if _contains_exact_outside(child, expected, item_ids):
            return True
    return False


# ─────────────────────── 内部工具：滚动辅助 ───────────────────────

def find_rv_for_scroll(root=None):
    """查找用于滚动的 RecyclerView 节点。

    返回节点 dict 或 None。要求 class 包含 RecyclerView 且高度 > 300。
    """
    if root is None:
        r = dump(depth=10)
        if not r.get("ok"):
            return None
        root = r.get("data", {}).get("window", {})
    return _find_rv_node(root)


def _find_rv_node(node):
    """递归查找高度 > 300 的 RecyclerView 节点。"""
    if node is None:
        return None
    cls = node.get("cls", "")
    if "RecyclerView" in cls:
        h = node_height(node)
        if h > 300:
            return node
    for child in node.get("children", []):
        hit = _find_rv_node(child)
        if hit is not None:
            return hit
    return None


def calc_median_item_height(rv_node):
    """计算 RecyclerView 子项的中位高度（对标 Java calculateMedianItemHeight）。

    仅统计高度 > 50 的子项。无有效子项时返回默认值 106。
    """
    heights = []
    for child in rv_node.get("children", []):
        if child is None:
            continue
        h = node_height(child)
        if h > 50:
            heights.append(h)
    if not heights:
        return 106
    heights.sort()
    return heights[len(heights) // 2]


def count_visible_items(rv_node):
    """计算 RecyclerView 中完全可见的子项数（对标 Java getVisibleItemCount）。

    过滤条件：
      1. 高度 >= 50% 中位高度（排除 header）
      2. 底部不超过 RV 底部 - 10px（排除底部被截断的项）
    """
    l, t, r, b = node_bounds(rv_node)
    median_h = calc_median_item_height(rv_node)
    threshold = int(median_h * 0.5)
    count = 0
    for child in rv_node.get("children", []):
        if child is None:
            continue
        h = node_height(child)
        _, _, _, child_b = node_bounds(child)
        if h >= threshold and child_b <= b - 10:
            count += 1
    return max(1, count)


# ─────────────────────── 内部工具：文本搜索辅助 ───────────────────────

def _find_nodes_by_text(root, text_substring, limit=20):
    """在 UI 树中查找文本或 desc 包含指定子串的节点列表。"""
    results = []
    if root is None:
        return results
    _collect_by_text(root, text_substring, results, limit)
    return results


def _collect_by_text(node, text_substring, results, limit):
    if node is None or len(results) >= limit:
        return
    node_text = node.get("text", "")
    node_desc = node.get("desc", "")
    if (text_substring in node_text) or (text_substring in node_desc):
        results.append(node)
        if len(results) >= limit:
            return
    for child in node.get("children", []):
        _collect_by_text(child, text_substring, results, limit)


def _find_nodes_by_regex(root, pattern, limit=20):
    """在 UI 树中查找文本或 desc 匹配正则表达式的节点列表。"""
    results = []
    if root is None:
        return results
    compiled = re.compile(pattern)
    _collect_by_regex(root, compiled, results, limit)
    return results


def _collect_by_regex(node, compiled, results, limit):
    if node is None or len(results) >= limit:
        return
    node_text = node.get("text", "")
    node_desc = node.get("desc", "")
    if (node_text and compiled.search(node_text)) or \
       (node_desc and compiled.search(node_desc)):
        results.append(node)
        if len(results) >= limit:
            return
    for child in node.get("children", []):
        _collect_by_regex(child, compiled, results, limit)
