# -*- coding: utf-8 -*-
"""夸克网盘顶部导航栏点击 — Phase 6 无 dump 版。"""
import json
import sys

from common.utils import success, error, gesture  # noqa: E402
from observation.screen.cmd_observe_screen import observe_screen  # noqa: E402

CMD_NAME = "quark.click_navigation"

NAV_RECENT = "最近观看"
NAV_ALL_FILES = "全部文件"
NAV_SHARED = "分享文件"
NAV_FAVORITES = "云收藏"

VALID_TABS = {NAV_RECENT, NAV_ALL_FILES, NAV_SHARED, NAV_FAVORITES}

PREDEFINED_COORDS = {
    NAV_RECENT: (110, 155),
    NAV_ALL_FILES: (260, 155),
    NAV_SHARED: (408, 155),
    NAV_FAVORITES: (546, 155),
}


def run(params=None):
    """点击夸克网盘顶部导航栏标签。"""
    if not params or "tab" not in params:
        return error("BAD_PARAMS", "Missing parameter: tab")

    tab = params["tab"]
    if tab not in VALID_TABS:
        return error("BAD_PARAMS", f"Invalid tab: {tab}. Must be one of {VALID_TABS}")

    # 观察屏幕获取候选
    obs_result = observe_screen()
    if not obs_result.get("ok"):
        # 降级到预定义坐标
        x, y = PREDEFINED_COORDS[tab]
        gesture([[x, y]], 200)
        return success(CMD_NAME, f"clicked_{tab} (fallback_coords)")

    candidates = obs_result.get("data", {}).get("candidates", [])

    # 查找匹配文本的候选
    target_candidate = None
    for c in candidates:
        if c.get("text") == tab:
            target_candidate = c
            break

    if target_candidate:
        bbox = target_candidate.get("bbox_px", {})
        cx = (bbox.get("x1", 0) + bbox.get("x2", 0)) // 2
        cy = (bbox.get("y1", 0) + bbox.get("y2", 0)) // 2
        gesture([[cx, cy]], 200)
        return success(CMD_NAME, f"clicked_{tab} (candidate)")
    else:
        # 降级到预定义坐标
        x, y = PREDEFINED_COORDS[tab]
        gesture([[x, y]], 200)
        return success(CMD_NAME, f"clicked_{tab} (fallback_coords)")


if __name__ == "__main__":
    result = run({"tab": NAV_ALL_FILES})
    print(json.dumps(result, ensure_ascii=False, indent=2))
