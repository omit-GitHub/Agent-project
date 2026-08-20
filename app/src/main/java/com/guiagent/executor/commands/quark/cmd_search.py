# -*- coding: utf-8 -*-
"""夸克网盘搜索功能 — Phase 6 无 dump 版。"""
import json
import sys
import time

from common.utils import success_with_data, error, gesture, sleep_ms  # noqa: E402
from observation.screen.cmd_observe_screen import observe_screen  # noqa: E402

CMD_NAME = "quark.search"

# 搜索按钮坐标（顶部左侧）
SEARCH_BTN_X = 227
SEARCH_BTN_Y = 85

# 清空按钮中心坐标
CLEAR_BTN_X = 412
CLEAR_BTN_Y = 242


def run(params=None):
    """在夸克网盘中搜索。"""
    if not params or "keyword" not in params:
        return error("BAD_PARAMS", "Missing parameter: keyword")

    keyword = params["keyword"]
    if not isinstance(keyword, str) or not keyword.strip():
        return error("BAD_PARAMS", "keyword must not be empty")
    keyword = keyword.strip()

    try:
        # 步骤 1: 点击搜索按钮
        gesture([[SEARCH_BTN_X, SEARCH_BTN_Y]], 200)
        sleep_ms(2000)

        # 步骤 2: 清空搜索框
        gesture([[CLEAR_BTN_X, CLEAR_BTN_Y]], 150)
        sleep_ms(500)

        # 步骤 3: 逐个输入搜索关键词
        for c in keyword:
            coords = _get_keyboard_coords(c)
            if coords is not None:
                gesture([[coords[0], coords[1]]], 150)
                sleep_ms(200)

        sleep_ms(1000)

        # 步骤 4: 获取搜索结果（改用 observe_screen）
        obs_result = observe_screen()
        candidates = []
        if obs_result.get("ok"):
            candidates = obs_result.get("data", {}).get("candidates", [])

        # 构建搜索结果（基于候选列表）
        items = []
        for i, c in enumerate(candidates):
            c_text = c.get("text", "")
            if c_text and c.get("kind") in ("card", "text", "button"):
                items.append({
                    "index": len(items) + 1,
                    "text": c_text,
                })

        # 判断搜索状态
        if len(items) > 0:
            search_status = "found"
        else:
            # 检查关键词是否回显
            keyword_echoed = any(
                keyword.lower() in c.get("text", "").lower()
                for c in candidates
            )
            search_status = "not_found" if keyword_echoed else "unknown"

        data = {
            "query": keyword,
            "search_status": search_status,
            "count": len(items),
            "items": items,
        }

        return success_with_data(CMD_NAME, data)

    except Exception as e:
        return error("EXECUTION_FAILED", f"Failed: {e}")


def _get_keyboard_coords(c):
    """获取夸克内置键盘按钮的坐标。"""
    start_x = 117
    button_width = 73
    row_y = [299, 365, 432, 499, 565, 635]

    ch = c.lower()

    if 'a' <= ch <= 'z':
        index = ord(ch) - ord('a')
    elif '0' <= ch <= '9':
        index = 26 + (ord(ch) - ord('0'))
    else:
        return None

    row = index // 6
    col = index % 6

    x = start_x + col * button_width
    y = row_y[row]

    return [x, y]


if __name__ == "__main__":
    p = None
    if len(sys.argv) > 1:
        p = {"keyword": sys.argv[1]}
    result = run(p)
    print(json.dumps(result, ensure_ascii=False, indent=2))
