# -*- coding: utf-8 -*-
"""夸克网盘返回功能（智能自适应）。

对标 Java: QuarkGoBackCommand.java

自动检测当前页面类型，智能决定返回次数:
    - 文件浏览页面：返回 1 次
    - 视频播放页面：返回 2 次（退出播放器）
    - 自动处理确认对话框

用户只需调用一次 "quark.go_back" 命令，无需关心当前在哪个页面。
"""
import json
import re
import sys

from common.utils import success, error, global_action, gesture, sleep_ms

from . import _find_nodes_by_text, _find_nodes_by_regex, dump

CMD_NAME = "quark.go_back"
MAX_BACK_PRESSES = 3  # 最多按 3 次返回


def run(params=None):
    """智能返回。

    Args:
        params: 可选 dict，当前无使用参数。

    Returns:
        dict: {"ok": true, "data": {"command": "quark.go_back",
               "result": "back_once"|"back_multiple_N"}}
              或 {"ok": false, "error": {"code": "...", "message": "..."}}
    """
    back_press_count = 0

    for i in range(MAX_BACK_PRESSES):
        # 执行返回
        r = global_action("BACK")
        if not r.get("ok"):
            if back_press_count == 0:
                return error("EXECUTION_FAILED", "Failed to perform back action")
            break

        back_press_count += 1
        sleep_ms(500)

        # 处理可能出现的确认对话框
        _handle_confirmation_dialog()

        sleep_ms(300)

        # 检查是否到达文件列表页面
        if _check_has_file_list():
            break

        # 检查是否还在夸克网盘应用中
        if not _check_in_quark_app():
            break

    if back_press_count == 0:
        return error("EXECUTION_FAILED", "No back action performed")
    elif back_press_count == 1:
        return success(CMD_NAME, "back_once")
    else:
        return success(CMD_NAME, f"back_multiple_{back_press_count}")


def _check_in_quark_app():
    """检查是否还在夸克网盘应用中（通过 dump 树中包名判断）。"""
    r = dump(depth=3)
    if not r.get("ok"):
        return False
    root = r.get("data", {}).get("window", {})
    return _has_quark_package(root)


def _has_quark_package(node):
    """递归检查节点树中是否有夸克包名的节点。"""
    if node is None:
        return False
    pkg = node.get("pkg", "")
    if pkg and "quark" in pkg:
        return True
    for child in node.get("children", []):
        if _has_quark_package(child):
            return True
    return False


def _check_has_file_list():
    """检查当前页面是否有文件列表。

    方法 1：查找日期文本节点（如 2024/07/22）→ 很可能是文件列表页面
    方法 2：查找 RecyclerView 并检查是否有多个复杂子项
    """
    r = dump(depth=6)
    if not r.get("ok"):
        return False
    root = r.get("data", {}).get("window", {})

    # 方法 1：查找日期文本节点（YYYY/MM/DD 格式）
    date_nodes = _find_nodes_by_regex(root, r"\d{4}/\d{2}/\d{2}", limit=5)
    if date_nodes:
        return True

    # 方法 2：查找 RecyclerView 并检查是否有大量复杂子项
    rv_nodes = _find_nodes_by_regex(root, r"RecyclerView", limit=10)
    for rv in rv_nodes:
        # 检查 "RecyclerView" 是否在 cls 字段中（正则匹配了所有含此文本的节点）
        cls = rv.get("cls", "")
        if "RecyclerView" not in cls:
            continue

        complex_children = 0
        for child in rv.get("children", []):
            if child and len(child.get("children", [])) > 2:
                complex_children += 1

        if complex_children >= 3:
            return True

    return False


def _handle_confirmation_dialog():
    """处理退出确认对话框。

    查找包含 "确认"、"确定"、"是"、"退出"、"OK"、"Yes" 等文本的可点击按钮并点击。
    """
    confirm_texts = ["确认", "确定", "是", "退出", "OK", "Yes"]

    r = dump(depth=5)
    if not r.get("ok"):
        return False
    root = r.get("data", {}).get("window", {})

    for text in confirm_texts:
        nodes = _find_nodes_by_text(root, text)
        for node in nodes:
            clickable = _find_clickable_ancestor(node)
            if clickable is not None:
                b = clickable.get("bounds", {})
                cx = (b.get("l", 0) + b.get("r", 0)) // 2
                cy = (b.get("t", 0) + b.get("b", 0)) // 2
                gesture([[cx, cy]], 200)
                return True

    return False


def _find_clickable_ancestor(node):
    """查找可点击的祖先节点（含自身）。"""
    current = node
    while current is not None:
        if current.get("clickable", False):
            return current
        current = current.get("parent")
    return None


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
