# -*- coding: utf-8 -*-
"""爱奇艺进入详情页（简介页）— Phase 6 无 dump 版。

定位策略（3 级降级）:
  1. 候选列表匹配 text 含"简介"或"详情"
  2. 候选列表匹配 kind == "button" 且位于顶部区域
  3. 固定坐标 (513, 97) — 兜底

命令：aiqiyi.open_detail
参数：无

用法：
  python aiqiyi/cmd_open_detail.py

前置：已在爱奇艺播放页。
"""
import os
import sys
import time

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from common.utils import success, error, tap  # noqa: E402
from observation.screen.cmd_observe_screen import observe_screen  # noqa: E402

# 唤控制条 — 顶部中心
WAKE_X, WAKE_Y = 640, 200
WAKE_WAIT = 1.5
MAX_WAKE_RETRIES = 2
# 兜底坐标
FALLBACK_X, FALLBACK_Y = 513, 97


def run_open(params=None):
    """Registry 入口 — aiqiyi.open_detail。

    3 级降级定位详情按钮，带重试。
    """
    detail_candidate = None

    for attempt in range(MAX_WAKE_RETRIES):
        # 非首次：先 tap 左侧关闭可能遮挡的弹窗
        if attempt > 0:
            tap(200, 400)
            time.sleep(0.5)

        # 唤控制条
        tap(WAKE_X, WAKE_Y)
        time.sleep(WAKE_WAIT)

        # 观察屏幕获取候选
        obs_result = observe_screen()
        if not obs_result.get("ok"):
            continue

        candidates = obs_result.get("data", {}).get("candidates", [])

        # 策略 1: text 含"简介"或"详情"
        for c in candidates:
            c_text = c.get("text", "")
            if "简介" in c_text or "详情" in c_text:
                detail_candidate = c
                break

        if detail_candidate:
            break

        # 策略 2: button 类型且位于顶部区域 (y < 200)
        for c in candidates:
            bbox = c.get("bbox_px", {})
            y1 = bbox.get("y1", 0)
            if c.get("kind") == "button" and y1 < 200:
                detail_candidate = c
                break

        if detail_candidate:
            break

    if detail_candidate:
        bbox = detail_candidate.get("bbox_px", {})
        tap_x = (bbox.get("x1", 0) + bbox.get("x2", 0)) // 2
        tap_y = (bbox.get("y1", 0) + bbox.get("y2", 0)) // 2
        matched_by = f"candidate:{detail_candidate.get('text', 'unknown')}"
    else:
        # 策略 3: 兜底坐标
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
        print(f"已进入详情页：{data.get('result', '')}")
    else:
        err = result.get("error", {})
        print(f"失败：{err.get('message', 'unknown')}", file=sys.stderr)


if __name__ == "__main__":
    main()
