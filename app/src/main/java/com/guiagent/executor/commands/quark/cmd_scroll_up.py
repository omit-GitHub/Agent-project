# -*- coding: utf-8 -*-
"""夸克搜索结果向上翻页。使用精确计算的慢速手势。

对标 Java: QuarkScrollUpCommand.java

算法:
    1. 找到 RecyclerView，获取 bounds
    2. 计算中位行高 medianH
    3. 计算完全可见的条数 visibleCount
    4. 滚动距离 = visibleCount × medianH（整页翻转）
    5. 手指从顶部拖到底部（scroll UP = 内容向下移）
    6. 用 1500ms 慢速手势拖拽（低于 fling 阈值，确保精准停止）
"""
import json
import sys

from common.utils import success, error, gesture, sleep_ms, parse_count

from . import find_rv_for_scroll, calc_median_item_height, count_visible_items, node_bounds

CMD_NAME = "quark.scroll_up"


def run(params=None):
    """向上翻页（内容向下移动）。

    Args:
        params: 可选 dict，{"count": N} 翻页次数（默认 1，最大 20）

    Returns:
        dict: {"ok": true, "data": {"command": "quark.scroll_up", "result": "..."}}
              或 {"ok": false, "error": {"code": "...", "message": "..."}}
    """
    count = parse_count(params, default=1, max_val=20)

    rv = find_rv_for_scroll()
    if rv is None:
        return error("EXECUTION_FAILED", "RecyclerView not found")

    median_h = calc_median_item_height(rv)
    visible_count = count_visible_items(rv)
    scroll_distance = visible_count * median_h  # 整页翻转

    l, t, r, b = node_bounds(rv)
    scroll_x = (l + r) // 2

    # scroll UP = 内容向下移 = 手指从顶部拖到底部
    finger_start = t + 80   # 距顶部 80px
    finger_end = finger_start + scroll_distance
    if finger_end > b - 20:
        finger_end = b - 20

    for k in range(count):
        gesture([[scroll_x, finger_start], [scroll_x, finger_end]], 1500)
        if k < count - 1:
            sleep_ms(500)

    return success(CMD_NAME,
                    f"scrolled_up x{count} (distance={scroll_distance}px, "
                    f"{visible_count} items, itemH={median_h})")


if __name__ == "__main__":
    p = None
    if len(sys.argv) > 1:
        p = {"count": int(sys.argv[1])}
    result = run(p)
    print(json.dumps(result, ensure_ascii=False, indent=2))
