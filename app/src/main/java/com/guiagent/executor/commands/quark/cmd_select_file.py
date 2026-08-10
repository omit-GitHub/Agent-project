# -*- coding: utf-8 -*-
"""夸克网盘选择文件/搜索结果。自动识别界面类型并适配。

对标 Java: QuarkSelectFileCommand.java + QuarkFileItems.java

支持的界面:
    - 搜索结果页：右侧单列列表，直接子项就是可点击项
    - 普通主页：文件列表是方块网格，项可能没有 clickable 标记

参数格式:
    {"values": [N]}      — 选第 N 个（从 1 开始，按从左到右、从上到下排序）
    {"values": [R, C]}   — 选第 R 行第 C 列（仅多列布局有效）
"""
import json
import sys

from common.utils import success, error, gesture, parse_values

from . import find_file_items, group_items_by_row, file_item_text

CMD_NAME = "quark.select_file"


def run(params=None):
    """选择文件/搜索结果。

    Args:
        params: dict，必须包含 {"values": [N]} 或 {"values": [R, C]}

    Returns:
        dict: {"ok": true, "data": {"command": "quark.select_file", "result": "..."}}
              或 {"ok": false, "error": {"code": "...", "message": "..."}}
    """
    if not params:
        return error("BAD_PARAMS", "Missing parameters")

    # 解析参数
    values = parse_values(params)
    if not values or len(values) < 1:
        return error("BAD_PARAMS", "Invalid parameter format")

    first = int(values[0])
    second = int(values[1]) if len(values) > 1 else -1

    try:
        # 1. 获取文件项列表
        items = find_file_items()
        if not items:
            return error("NO_MATCH", "No file items found")

        # 2. 选择目标
        target = None
        desc = ""

        if second == -1:
            # 单参数：选第 N 个
            n = first
            if n < 1 or n > len(items):
                return error("NO_MATCH",
                              f"Item {n} out of range (1-{len(items)})")
            target = items[n - 1]
            desc = f"item_{n}"
        else:
            # 双参数：选第 R 行第 C 列
            row = first
            col = second
            if row < 1 or col < 1:
                return error("BAD_PARAMS", "row/col must be >= 1")
            rows = group_items_by_row(items)
            if row > len(rows):
                return error("NO_MATCH",
                              f"Row {row} out of range (1-{len(rows)})")
            target_row = rows[row - 1]
            if col > len(target_row):
                return error("NO_MATCH",
                              f"Col {col} out of range (row {row} has {len(target_row)} cols)")
            target = target_row[col - 1]
            desc = f"row_{row}_col_{col}"

        # 3. 点击目标中心
        b = target.get("bounds", {})
        cx = (b.get("l", 0) + b.get("r", 0)) // 2
        cy = (b.get("t", 0) + b.get("b", 0)) // 2

        gesture([[cx, cy]], 200)

        # 4. 获取文件名
        file_name = file_item_text(target)
        if len(file_name) > 30:
            file_name = file_name[:30] + "..."

        rows = group_items_by_row(items)
        result_text = (
            f"selected_{desc} ({len(items)} items, {len(rows)} rows)"
        )
        if file_name:
            result_text += f' "{file_name}"'

        return success(CMD_NAME, result_text)

    except Exception as e:
        return error("EXECUTION_FAILED", f"Failed: {e}")


if __name__ == "__main__":
    p = None
    if len(sys.argv) > 1:
        vals = [int(x) for x in sys.argv[1:]]
        p = {"values": vals}
    result = run(p)
    print(json.dumps(result, ensure_ascii=False, indent=2))
