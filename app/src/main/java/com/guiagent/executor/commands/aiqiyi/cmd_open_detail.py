# -*- coding: utf-8 -*-
"""爱奇艺进入详情页（简介页）。多级自适应定位详情按钮。

包名: com.qiyi.video.speaker (中屏定制版)

定位策略（4 级降级）:
  1. 子串匹配 id 含 "video_detail"（兼容 video_detail1/video_detail2/任何未来版本）
  2. 扫描顶部信息栏，找 "简介" 文本节点，用 bounds 中心 tap
  3. 全局 DFS 找 text 或 contentDescription 含 "详情" 或 "简介" 的节点
  4. 固定坐标 (513, 97) — 基于 1280×800 屏幕顶部栏详情按钮默认位置

命令: aiqiyi.open_detail
参数: 无

用法:
  python aiqiyi/cmd_open_detail.py

前置: 已在爱奇艺播放页。
      设备已开 GUIAgent 无障碍, 且 adb forward tcp:8322 tcp:8322。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.utils import (
    tap, dump, ping, sleep,
    find_node_in_tree, node_center,
    success, error,
)

# 唤控制条 — 顶部中心
WAKE_X, WAKE_Y = 640, 200
# 控制条完全渲染等待时间 (秒)
WAKE_WAIT = 1.5
# 最大唤醒重试次数
MAX_WAKE_RETRIES = 2
# 兜底坐标 — 基于 UI dump: video_detail2 在 (481,79)-(546,116) 的中心
FALLBACK_X, FALLBACK_Y = 513, 97


def _find_detail_by_id(window):
    """策略 1: id 子串匹配 'video_detail'。"""
    node = find_node_in_tree(window, "video_detail")
    if node:
        cx, cy = node_center(node)
        nid = node.get("id", "")
        short_id = nid.split("/")[-1] if "/" in nid else nid
        return cx, cy, f"id:{short_id}"
    return None


def _find_text_in_top_bar(window, keyword, max_y_ratio=0.25):
    """策略 2: 扫描顶部信息栏找指定文本。"""
    def walk(node):
        if node is None:
            return None
        b = node.get("bounds", {})
        t = b.get("t", 0)
        # 粗略过滤: 只查顶部区域 (按 800px 屏高比例)
        if t > int(800 * max_y_ratio):
            return None
        text = node.get("text", "")
        desc = node.get("desc", "")
        if (text and keyword in text) or (desc and keyword in desc):
            return node
        for c in node.get("children", []):
            hit = walk(c)
            if hit:
                return hit
        return None

    node = walk(window)
    if node:
        cx, cy = node_center(node)
        return cx, cy, f"text:{keyword}"
    return None


def _find_by_text_global(window, keyword):
    """策略 3: 全局 DFS 找 text/desc 含 keyword 的节点。"""
    def walk(node):
        if node is None:
            return None
        text = node.get("text", "")
        desc = node.get("desc", "")
        if (text and keyword in text) or (desc and keyword in desc):
            return node
        for c in node.get("children", []):
            hit = walk(c)
            if hit:
                return hit
        return None

    node = walk(window)
    if node:
        cx, cy = node_center(node)
        return cx, cy, f"text_keyword:{keyword}"
    return None


def run_open(params=None):
    """Registry 入口 — aiqiyi.open_detail。

    4 级降级定位详情按钮，带重试。
    """
    detail_result = None

    for attempt in range(MAX_WAKE_RETRIES):
        # 非首次: 先 tap 左侧关闭可能遮挡的弹窗
        if attempt > 0:
            tap(200, 400)
            sleep(0.5)

        # 唤控制条
        tap(WAKE_X, WAKE_Y)
        time.sleep(WAKE_WAIT)

        # dump UI 树
        resp = dump(depth=8, include=["bounds", "id", "text", "clickable"])
        if not resp.get("ok"):
            continue
        window = resp["data"].get("window", {})

        # 策略 1: id 子串匹配
        detail_result = _find_detail_by_id(window)
        if detail_result:
            break

        # 策略 2: 顶栏 "简介" 文本
        detail_result = _find_text_in_top_bar(window, "简介")
        if detail_result:
            break

        # 策略 3: 全局 DFS 找 "详情" / "简介"
        detail_result = _find_by_text_global(window, "详情")
        if not detail_result:
            detail_result = _find_by_text_global(window, "简介")
        if detail_result:
            break

    if detail_result:
        tap_x, tap_y, matched_by = detail_result
    else:
        # 策略 4: 兜底坐标
        tap_x, tap_y = FALLBACK_X, FALLBACK_Y
        matched_by = "fallback_coords"

    tap(tap_x, tap_y)
    return success("aiqiyi.open_detail",
                   f"detail_opened (matched_by={matched_by}, tap={tap_x},{tap_y})")


# Alias for unified registry
run = run_open


def main():
    result = run_open()
    if result.get("ok"):
        data = result.get("data", {})
        print(f"已进入详情页: {data.get('result', '')}")
    else:
        err = result.get("error", {})
        print(f"失败: {err.get('message', 'unknown')}", file=sys.stderr)


if __name__ == "__main__":
    main()
