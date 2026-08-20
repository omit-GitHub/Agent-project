# -*- coding: utf-8 -*-
"""搜索片源（聚合平台入口）— Phase 6 无 dump 版。"""
import json
import sys
import time

from common.utils import (  # noqa: E402
    success_with_data, error, global_action,
    click_node_by_id, set_text_by_id, sleep,
)
from observation.screen.cmd_observe_screen import observe_screen  # noqa: E402

CMD_NAME = "launcher_search"

SEARCH_ENTRY_ID = "classsic_nav_search"
SEARCH_TEXT_ID = "mid_search_text_et"
SEARCH_TRIGGER_ID = "mid_search_text"
RESULT_ITEM_ID = "pop_mid_content_item_tv"


def run(params=None):
    """搜索片源。"""
    if not params or "keyword" not in params:
        return error("BAD_PARAMS", "Missing parameter: keyword")

    keyword = params.get("keyword", "")
    if not isinstance(keyword, str) or not keyword.strip():
        return error("BAD_PARAMS", "keyword must not be empty")
    keyword = keyword.strip()

    # 0. 回主页
    global_action("HOME")
    sleep(1.0)

    # 1. 点搜索入口
    r1 = click_node_by_id(SEARCH_ENTRY_ID)
    if not r1.get("ok"):
        # 检查是否已在搜索页
        obs_check = observe_screen()
        if obs_check.get("ok"):
            candidates = obs_check.get("data", {}).get("candidates", [])
            in_search_page = any(
                SEARCH_TEXT_ID in c.get("metadata", {}).get("id", "")
                for c in candidates
            )
            if not in_search_page:
                return error("NO_MATCH", f"Search entry not found: {SEARCH_ENTRY_ID}")
        else:
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

    # 4. 读结果列表（改用 observe_screen）
    obs_result = observe_screen()
    candidates = []
    if obs_result.get("ok"):
        candidates = obs_result.get("data", {}).get("candidates", [])

    # 构建搜索结果
    items = []
    for c in candidates:
        c_text = c.get("text", "")
        if c_text and c.get("kind") in ("card", "text"):
            bbox = c.get("bbox_px", {})
            items.append({
                "index": len(items) + 1,
                "text": c_text,
                "x": (bbox.get("x1", 0) + bbox.get("x2", 0)) // 2,
                "y": (bbox.get("y1", 0) + bbox.get("y2", 0)) // 2,
            })

    # 判断搜索状态
    if len(items) > 0:
        search_status = "found"
    else:
        keyword_echoed = any(
            keyword.lower() in c.get("text", "").lower()
            for c in candidates
        )
        no_results = any(
            "没有搜索到" in c.get("text", "")
            for c in candidates
        )
        search_status = "not_found" if (keyword_echoed and no_results) else "unknown"

    data = {
        "query": keyword,
        "search_status": search_status,
        "count": len(items),
        "items": items,
    }

    return success_with_data(CMD_NAME, data)


if __name__ == "__main__":
    p = None
    if len(sys.argv) > 1:
        p = {"keyword": sys.argv[1]}
    else:
        p = {"keyword": ""}
    result = run(p)
    print(json.dumps(result, ensure_ascii=False, indent=2))
