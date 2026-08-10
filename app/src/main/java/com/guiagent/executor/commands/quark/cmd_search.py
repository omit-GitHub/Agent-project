# -*- coding: utf-8 -*-
"""夸克网盘搜索功能。

对标 Java: QuarkSearchCommand.java + QuarkKeyboardUtils.java

完整流程:
    1. 点击搜索按钮（坐标 227, 85）
    2. 清空搜索框（点击清空按钮 412, 242）
    3. 逐个输入搜索关键词的每个字符（使用夸克内置键盘坐标）
    4. 等待搜索结果
    5. 构建搜索数据并附带即时状态快照

键盘布局（6×6 网格）:
    Row 0 (y=299): A B C D E F
    Row 1 (y=365): G H I J K L
    Row 2 (y=432): M N O P Q R
    Row 3 (y=499): S T U V W X
    Row 4 (y=565): Y Z 0 1 2 3
    Row 5 (y=635): 4 5 6 7 8 9
"""
import json
import sys
import time

from common.utils import success_with_data, error, gesture, sleep_ms, dump

from . import find_file_items, build_search_result

CMD_NAME = "quark.search"

# 搜索按钮坐标（顶部左侧）
SEARCH_BTN_X = 227
SEARCH_BTN_Y = 85

# 清空按钮中心坐标
CLEAR_BTN_X = 412
CLEAR_BTN_Y = 242


def run(params=None):
    """在夸克网盘中搜索。

    Args:
        params: dict，必须包含 {"keyword": "xxx"}

    Returns:
        dict: {"ok": true, "data": {"command": "quark.search",
               "query": "...", "search_status": "...", "count": N,
               "items": [...], "state": {...}}}
              或 {"ok": false, "error": {"code": "...", "message": "..."}}
    """
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

        # 步骤 2: 清空搜索框（点击清空按钮）
        gesture([[CLEAR_BTN_X, CLEAR_BTN_Y]], 150)
        sleep_ms(500)

        # 步骤 3: 逐个输入搜索关键词的每个字符
        for c in keyword:
            coords = _get_keyboard_coords(c)
            if coords is not None:
                gesture([[coords[0], coords[1]]], 150)
                sleep_ms(200)

        sleep_ms(1000)

        # 步骤 4: 获取搜索结果
        r = dump(depth=10)
        root = {}
        if r.get("ok"):
            root = r.get("data", {}).get("window", {})

        file_items = find_file_items(root)
        data = build_search_result(keyword, root, file_items)

        # 附即时状态快照，避免 CompoundRegistry 再等待页面稳定
        data["state"] = root

        return success_with_data(CMD_NAME, data)

    except Exception as e:
        return error("EXECUTION_FAILED", f"Failed: {e}")


def _get_keyboard_coords(c):
    """获取夸克内置键盘按钮的坐标。

    键盘布局: 6×6 网格，按字母表顺序排列。
        startX = 117, buttonWidth = 73
        rowY = [299, 365, 432, 499, 565, 635]

    字母 A-Z 位置 0-25，数字 0-9 位置 26-35。
    不支持的字符返回 None。
    """
    start_x = 117
    button_width = 73
    row_y = [299, 365, 432, 499, 565, 635]

    ch = c.lower()

    # 字母 a-z (位置 0-25)
    if 'a' <= ch <= 'z':
        index = ord(ch) - ord('a')
    # 数字 0-9 (位置 26-35)
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
