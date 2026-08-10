# -*- coding: utf-8 -*-
"""夸克搜索结果向下翻页。使用精确计算的慢速手势，避免 fling 惯性导致对齐不准。

对标 Java: QuarkScrollDownCommand.java

滚动算法:
    1. 找到 RecyclerView，获取 bounds
    2. 收集完全可见的文件项（排除 header 和截断项）
    3. 计算中位行高 medianH
    4. 滚动距离 = 可见条数 × 单行高度（整页翻转，保证上下对齐）
    5. 用 1500ms 慢速手势拖拽（低于 fling 阈值，确保精准停止）
"""
import json
import sys

from common.utils import success, error, gesture, sleep_ms, parse_count

from . import find_rv_for_scroll, calc_median_item_height, count_visible_items, node_bounds

CMD_NAME = "quark.scroll_down"


def run(params=None):
    """向下翻页（内容向上移动）。

    Args:
        params: 可选 dict，{"count": N} 翻页次数（默认 1，最大 20）

    Returns:
        dict: {"ok": true, "data": {"command": "quark.scroll_down", "result": "..."}}
              或 {"ok": false, "error": {"code": "...", "message": "..."}}
    """
    count = parse_count(params, default=1, max_val=20)

    rv = find_rv_for_scroll()
    if rv is None:
        return error("EXECUTION_FAILED", "RecyclerView not found")

    # 计算滚动参数
    median_h = calc_median_item_height(rv)
    visible_count = count_visible_items(rv)
    # 滚动距离 = 可见行数 × 单行高度（整页翻转，保证上下对齐）
    scroll_distance = visible_count * median_h

    l, t, r, b = node_bounds(rv)
    scroll_x = (l + r) // 2

    # scroll DOWN = 内容向上移 = 手指从底部拖到顶部
    finger_start = b - 80   # 距底部 80px（留边距）
    finger_end = finger_start - scroll_distance
    # 确保终点不超过 RV 顶部
    if finger_end < t + 20:
        finger_end = t + 20

    for k in range(count):
        # 慢速拖拽 1500ms — 低于 RecyclerView 的 fling 速度阈值
        # 确保滚动停在精确位置，不会因惯性多滚
        gesture([[scroll_x, finger_start], [scroll_x, finger_end]], 1500)
        if k < count - 1:
            sleep_ms(500)

    return success(CMD_NAME,
                    f"scrolled_down x{count} (distance={scroll_distance}px, "
                    f"{visible_count} items, itemH={median_h})")


if __name__ == "__main__":
    p = None
    if len(sys.argv) > 1:
        p = {"count": int(sys.argv[1])}
    result = run(p)
    print(json.dumps(result, ensure_ascii=False, indent=2))
