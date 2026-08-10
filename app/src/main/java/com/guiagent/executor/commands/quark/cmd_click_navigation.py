# -*- coding: utf-8 -*-
"""夸克网盘顶部导航栏点击。

对标 Java: QuarkClickNavigationCommand.java
支持点击：最近观看、全部文件、分享文件、云收藏

流程:
    1. 验证 tab 参数是否合法
    2. 在 UI 树中查找对应文本的节点（y 坐标在 130-180 范围内的顶部导航栏）
    3. 找到则点击节点中心
    4. 找不到则使用预定义坐标点击
"""
import json
import sys

from common.utils import success, error, gesture, dump, node_center, node_bounds

CMD_NAME = "quark.click_navigation"

# 导航栏标签的文本
NAV_RECENT = "最近观看"
NAV_ALL_FILES = "全部文件"
NAV_SHARED = "分享文件"
NAV_FAVORITES = "云收藏"

VALID_TABS = {NAV_RECENT, NAV_ALL_FILES, NAV_SHARED, NAV_FAVORITES}

# 预定义坐标（文本查找失败时的后备方案）
# y 固定在导航栏中间 = 155，x 根据标签名确定
PREDEFINED_COORDS = {
    NAV_RECENT: (110, 155),
    NAV_ALL_FILES: (260, 155),
    NAV_SHARED: (408, 155),
    NAV_FAVORITES: (546, 155),
}


def run(params=None):
    """点击夸克网盘顶部导航栏标签。

    Args:
        params: dict，必须包含 {"tab": "最近观看"|"全部文件"|"分享文件"|"云收藏"}

    Returns:
        dict: {"ok": true, "data": {"command": "quark.click_navigation",
               "result": "clicked_xxx"}}
              或 {"ok": false, "error": {"code": "...", "message": "..."}}
    """
    if not params or "tab" not in params:
        return error("BAD_PARAMS", "Missing parameter: tab")

    tab = params["tab"]

    # 验证是否是有效的标签
    if tab not in VALID_TABS:
        return error("BAD_PARAMS",
                      f"Invalid tab: {tab}. Valid tabs: {', '.join(sorted(VALID_TABS))}")

    # 尝试通过文本查找导航栏标签节点
    r = dump(depth=6)
    if r.get("ok"):
        root = r.get("data", {}).get("window", {})
        nodes = _find_nodes_by_text(root, tab)

        # 查找位于顶部区域的节点（y 坐标在 130-180 之间）
        for node in nodes:
            _, t, _, _ = node_bounds(node)
            if 130 <= t <= 180:
                cx, cy = node_center(node)
                gesture([[cx, cy]], 200)
                return success(CMD_NAME, f"clicked_{tab}")

    # 文本查找失败，使用预定义坐标
    if tab in PREDEFINED_COORDS:
        x, y = PREDEFINED_COORDS[tab]
        gesture([[x, y]], 200)
        return success(CMD_NAME, f"clicked_{tab}_by_coords")

    return error("BAD_PARAMS", f"Unknown tab: {tab}")


def _find_nodes_by_text(root, text_substring):
    """在 UI 树中查找文本或 desc 包含指定子串的节点列表。"""
    results = []
    if root is None:
        return results
    _collect(root, text_substring, results)
    return results


def _collect(node, text_substring, results):
    if node is None:
        return
    node_text = node.get("text", "")
    node_desc = node.get("desc", "")
    if (text_substring in node_text) or (text_substring in node_desc):
        results.append(node)
    for child in node.get("children", []):
        _collect(child, text_substring, results)


if __name__ == "__main__":
    p = None
    if len(sys.argv) > 1:
        p = {"tab": sys.argv[1]}
    result = run(p)
    print(json.dumps(result, ensure_ascii=False, indent=2))
