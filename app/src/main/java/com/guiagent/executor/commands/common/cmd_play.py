# -*- coding: utf-8 -*-
"""播放搜索结果第 X 个片源（通用命令，基于 whohuatv launcher 搜索结果页）。

对标 Java: PlayCommand.java

参数:
    {"index": 3} — 第 3 个（从 1 开始）
    {"row": 2, "col": 1} — 第 2 排第 1 个（从 1 开始）

执行逻辑:
    1. find 海报节点 pop_mid_content_item_pic (clickable, 拿 bounds 排序+点击)
    2. find 标题节点 pop_mid_content_item_tv (仅用于显示片名)
    3. 对齐海报与标题（过滤无标题的多余海报）
    4. 行优先排序: 主序=行(cy 从上到下), 次序=列(cx 从左到右)
    5. tap 第 X 个海报的 bounds 中心
"""
import json
import sys
import time
from statistics import median

from common.utils import (
    success_with_data, error, find_nodes, tap, sleep,
    group_by_row, flatten_rows, node_center, node_bounds,
)

CMD_NAME = "play"

PIC_ID = "pop_mid_content_item_pic"
TITLE_ID = "pop_mid_content_item_tv"


def _find_with_retry(id_substring, retries=5, gap=0.6):
    """find 节点带重试（RecyclerView 渲染动画期间可能瞬时返回空）。

    Args:
        id_substring: ID 子串
        retries: 重试次数
        gap: 重试间隔（秒）

    Returns:
        list[dict]: 有效节点列表（bounds 非空且高度 > 0）
    """
    for k in range(retries):
        r = find_nodes(id_substring, limit=50)
        if r.get("ok"):
            nodes = r.get("data", {}).get("nodes", [])
            # 过滤掉 bounds 无效（高度 <= 0）的节点
            valid = []
            for n in nodes:
                b = n.get("bounds", {})
                if b.get("b", 0) > b.get("t", 0):
                    valid.append(n)
            if valid:
                return valid
        sleep(gap)
    return []


def _align_posters_to_titles(pics, titles):
    """对齐海报与标题。

    标题节点是 search 返回项的权威集合；过滤掉没有对应标题的额外/缓存海报，
    保证 search.items[index-1] 与 play(index) 永远指向同一项。

    Args:
        pics: 海报节点列表
        titles: 标题节点列表

    Returns:
        list[dict]: 对齐后的海报节点列表（按行优先排序）
    """
    # 先对海报按行排序
    rows = group_by_row(pics)
    ordered = flatten_rows(rows)

    # 过滤有文本的标题
    titled = [t for t in titles if t.get("text", "").strip()]

    if not titled or len(titled) >= len(ordered):
        return ordered

    # 截断海报到标题数量
    return ordered[:len(titled)]


def _find_closest_title(titles, pic_x, pic_y):
    """找距离海报中心最近的标题。

    Args:
        titles: 标题节点列表
        pic_x: 海报中心 x
        pic_y: 海报中心 y

    Returns:
        str: 最近标题的文本，找不到返回 ""
    """
    closest_title = ""
    closest_dist = float("inf")

    for title_node in titles:
        text = title_node.get("text", "")
        if not text:
            continue
        tx, ty = node_center(title_node)
        dx = tx - pic_x
        dy = ty - pic_y
        dist = dx * dx + dy * dy
        if dist < closest_dist:
            closest_dist = dist
            closest_title = text

    return closest_title


def run(params=None):
    """播放搜索结果第 X 个片源。

    Args:
        params: dict，支持:
            {"index": N} — 第 N 个（从 1 开始）
            {"row": R, "col": C} — 第 R 排第 C 个（从 1 开始）

    Returns:
        dict: 成功返回 {"ok": true, "data": {"command": "play", "index": ..., ...}}
              失败返回 {"ok": false, "error": {"code": "...", "message": "..."}}
    """
    if not params:
        return error("BAD_PARAMS", "Missing parameters")

    # 解析参数
    requested_index = None
    requested_row = None
    requested_col = None

    try:
        if "index" in params:
            requested_index = int(params["index"])
            if requested_index < 1:
                return error("BAD_PARAMS", "index must be >= 1")
        elif "row" in params and "col" in params:
            requested_row = int(params["row"])
            requested_col = int(params["col"])
            if requested_row < 1 or requested_col < 1:
                return error("BAD_PARAMS", "row/col must be >= 1")
        elif "values" in params:
            # 兼容 run-play.py 的 values 格式
            vals = params["values"]
            if isinstance(vals, list) and len(vals) > 0:
                requested_index = int(vals[0])
            else:
                return error("BAD_PARAMS", "Need {index: N} or {row: R, col: C} or {values: [N]}")
        else:
            return error("BAD_PARAMS", "Need {index: N} or {row: R, col: C}")
    except (ValueError, TypeError):
        return error("BAD_PARAMS", "index/row/col must be integers")

    # 1. 找可点击的海报节点（拿 bounds 排序+点击）
    pics = _find_with_retry(PIC_ID, retries=5)
    if not pics:
        return error("NO_MATCH",
                     "No playable items found — run 'search' first or wait for results to load")

    # 2. 读标题节点（仅用于显示片名）
    tvs = _find_with_retry(TITLE_ID, retries=5)

    # 3. 对齐海报与标题
    playable = _align_posters_to_titles(pics, tvs)
    rows = group_by_row(playable)
    ordered = flatten_rows(rows)

    # 4. 确定目标
    target = None
    index = None

    if requested_index is not None:
        index = requested_index
        if index > len(ordered):
            return error("NO_MATCH",
                         f"Only {len(ordered)} items available, index {index} out of range")
        target = ordered[index - 1]
    else:
        row = requested_row
        col = requested_col
        if row > len(rows):
            return error("NO_MATCH",
                         f"Row {row} out of range (1-{len(rows)})")
        target_row = rows[row - 1]
        if col > len(target_row):
            return error("NO_MATCH",
                         f"Col {col} out of range (row {row} has {len(target_row)} cols)")
        target = target_row[col - 1]
        index = ordered.index(target) + 1

    cx, cy = node_center(target)
    title = _find_closest_title(tvs, cx, cy)

    # 5. 点击海报中心
    tap(cx, cy)

    data = {
        "index": index,
        "title": title,
        "x": cx,
        "y": cy,
        "total": len(ordered),
    }
    if requested_row is not None:
        data["row"] = requested_row
        data["col"] = requested_col

    return success_with_data(CMD_NAME, data)


if __name__ == "__main__":
    # CLI 用法: python cmd_play.py [index]
    p = None
    if len(sys.argv) > 1:
        try:
            p = {"index": int(sys.argv[1])}
        except ValueError:
            print("用法: python cmd_play.py [index]   (index 从 1 开始)", file=sys.stderr)
            sys.exit(1)
    else:
        print("用法: python cmd_play.py [index]   (index 从 1 开始)", file=sys.stderr)
        sys.exit(1)
    result = run(p)
    print(json.dumps(result, ensure_ascii=False, indent=2))
