# -*- coding: utf-8 -*-
"""搜索片源（聚合平台入口，基于 whohuatv launcher，覆盖爱奇艺/优酷/腾讯/芒果）。

对标 Java: SearchCommand.java

参数:
    {"keyword": "飞驰人生"} — 搜索关键词

前置条件:
    无。命令内部会先无条件回主页（搜索入口只在主页存在，在主页按 HOME 无害）。

执行逻辑:
    0. go home
    1. click id=classsic_nav_search (搜索入口)
    2. set_text id=mid_search_text_et text=keyword
    3. click id=mid_search_text (触发搜索)
    4. find id=pop_mid_content_item_tv limit=20 (读结果)
"""
import json
import sys
import time

from common.utils import (
    success_with_data, error, global_action, click_node_by_id, set_text_by_id,
    find_nodes, sleep, contains_text, dump, group_by_row, flatten_rows,
    node_center,
)

CMD_NAME = "launcher_search"

SEARCH_ENTRY_ID = "classsic_nav_search"
SEARCH_TEXT_ID = "mid_search_text_et"
SEARCH_TRIGGER_ID = "mid_search_text"
RESULT_ITEM_ID = "pop_mid_content_item_tv"


def _build_search_data(keyword, result_nodes, root_node):
    """构建搜索结果数据。

    Args:
        keyword: 搜索关键词
        result_nodes: find_nodes 返回的节点列表
        root_node: UI 树根节点（用于判断搜索状态）

    Returns:
        dict: {"query": ..., "search_status": ..., "count": ..., "items": [...]}
    """
    # 按行分组 + 展平（对标 Java AccessibilityGrid.groupByRow + flatten）
    rows = group_by_row(result_nodes)
    ordered = flatten_rows(rows)

    items = []
    for i, node in enumerate(ordered):
        cx, cy = node_center(node)
        items.append({
            "index": i + 1,
            "text": node.get("text", ""),
            "x": cx,
            "y": cy,
        })

    # 判断搜索状态
    count = len(ordered)
    if count > 0:
        search_status = "found"
    else:
        query_visible = contains_text(root_node, keyword)
        no_results_visible = contains_text(root_node, "没有搜索到相关内容")
        search_status = "not_found" if (query_visible and no_results_visible) else "unknown"

    return {
        "query": keyword,
        "search_status": search_status,
        "count": count,
        "items": items,
    }


def run(params=None):
    """搜索片源。

    Args:
        params: dict，必须包含 {"keyword": "xxx"}

    Returns:
        dict: 成功返回 {"ok": true, "data": {"command": "launcher_search", ...}}
              失败返回 {"ok": false, "error": {"code": "...", "message": "..."}}
    """
    if not params or "keyword" not in params:
        return error("BAD_PARAMS", "Missing parameter: keyword")

    keyword = params.get("keyword", "")
    if not isinstance(keyword, str) or not keyword.strip():
        return error("BAD_PARAMS", "keyword must not be empty")
    keyword = keyword.strip()

    # 0. 无条件先回主页（launcher 内部也有子页面，仅凭包名无法判断是否在主页）
    global_action("HOME")
    sleep(1.0)

    # 1. 点搜索入口
    r1 = click_node_by_id(SEARCH_ENTRY_ID)
    if not r1.get("ok"):
        return error("NO_MATCH", f"Search entry not found: {SEARCH_ENTRY_ID}")
    sleep(1.0)

    # 2. 填关键词
    r2 = set_text_by_id(SEARCH_TEXT_ID, keyword)
    if not r2.get("ok"):
        return error("EXECUTION_FAILED", "Failed to set search text")
    sleep(0.5)

    # 3. 触发搜索
    r3 = click_node_by_id(SEARCH_TRIGGER_ID)
    if not r3.get("ok"):
        return error("NO_MATCH", f"Search trigger not found: {SEARCH_TRIGGER_ID}")
    sleep(2.0)

    # 4. 读结果列表
    r4 = find_nodes(RESULT_ITEM_ID, limit=20)
    result_nodes = []
    if r4.get("ok"):
        result_nodes = r4.get("data", {}).get("nodes", [])

    # dump 获取当前 UI 树根节点（用于判断搜索状态）
    root_node = {}
    r_dump = dump(depth=3)
    if r_dump.get("ok"):
        root_node = r_dump.get("data", {}).get("window", {})

    data = _build_search_data(keyword, result_nodes, root_node)
    return success_with_data(CMD_NAME, data)


if __name__ == "__main__":
    # CLI 用法: python cmd_launcher_search.py [keyword]
    p = None
    if len(sys.argv) > 1:
        p = {"keyword": sys.argv[1]}
    else:
        p = {"keyword": ""}
    result = run(p)
    print(json.dumps(result, ensure_ascii=False, indent=2))
