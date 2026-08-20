# -*- coding: utf-8 -*-
"""爱奇艺打开/关闭详情页(电视剧简介) — Phase 7 无 dump 版。

策略 (自适应, 不依赖固定坐标):
  in (进入详情):
    1. tap (640, 200) 唤出控制条
    2. observe_screen() 获取候选列表
    3. 匹配 text 含"简介"或"详情"的候选
    4. 用候选 bbox 中心 tap

  out (退出详情):
    1. tap 屏幕左侧非详情页区域 (200, 400) 返回播放页

用法:
  python aiqiyi/run-detail.py in              # 进入详情页
  python aiqiyi/run-detail.py out             # 退出详情页
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from send import send
from common.utils import success, error
from observation.screen.cmd_observe_screen import observe_screen

# ── 坐标常量 ─
WAKE_X, WAKE_Y = 640, 200
EXIT_X, EXIT_Y = 200, 400


def op(i, name, **args):
    r = send({"id": str(i), "op": name, "args": args})
    print(f"[{i}] {name} -> ok={r.get('ok')} "
          f"{json.dumps(r.get('data', r.get('err')), ensure_ascii=False)}")
    return r


def find_detail_button_from_candidates(candidates):
    """从候选列表中找详情按钮。

    优先级:
      1. text 含"简介"或"详情"
      2. kind == "button" 且位于顶部区域 (y < 200)

    Returns:
        (cx, cy, matched_by) 或 None
    """
    # 策略 1: text 匹配
    for c in candidates:
        c_text = c.get("text", "")
        if "简介" in c_text or "详情" in c_text:
            bbox = c.get("bbox_px", {})
            cx = (bbox.get("x1", 0) + bbox.get("x2", 0)) // 2
            cy = (bbox.get("y1", 0) + bbox.get("y2", 0)) // 2
            return cx, cy, f"text:{c_text}"

    # 策略 2: button 类型且位于顶部
    for c in candidates:
        bbox = c.get("bbox_px", {})
        y1 = bbox.get("y1", 0)
        if c.get("kind") == "button" and y1 < 200:
            cx = (bbox.get("x1", 0) + bbox.get("x2", 0)) // 2
            cy = (bbox.get("y1", 0) + bbox.get("y2", 0)) // 2
            return cx, cy, f"button_top:{c.get('text', '')}"

    return None


def do_in():
    """进入详情页。"""
    r1 = op(1, "ping")
    if not r1.get("ok"):
        sys.exit("ping 失败")

    # 唤控制条
    op(2, "tap", x=WAKE_X, y=WAKE_Y)
    time.sleep(1.5)

    # observe_screen 获取候选
    obs_result = observe_screen()
    if not obs_result.get("ok"):
        sys.exit("observe_screen 失败")

    candidates = obs_result.get("data", {}).get("candidates", [])
    hit = find_detail_button_from_candidates(candidates)

    if not hit:
        # 兜底坐标
        detail_x, detail_y = 513, 97
        print(f"未找到详情按钮，使用兜底坐标 ({detail_x}, {detail_y})")
    else:
        detail_x, detail_y, matched_by = hit
        print(f"找到详情按钮：{matched_by}, 坐标=({detail_x}, {detail_y})")

    op(3, "tap", x=detail_x, y=detail_y)
    print("\n已进入详情页")


def do_out():
    """退出详情页。"""
    r1 = op(1, "ping")
    if not r1.get("ok"):
        sys.exit("ping 失败")

    op(2, "tap", x=EXIT_X, y=EXIT_Y)
    print("\n已退出详情页")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("in", "out"):
        sys.exit("用法：python aiqiyi/run-detail.py in|out\n"
                 "  in   进入详情页\n"
                 "  out  退出详情页")

    cmd = sys.argv[1]
    if cmd == "in":
        do_in()
    else:
        do_out()


# ── Registry 入口函数 ──

def run_open(params=None):
    """aiqiyi.open_detail — 进入详情页。"""
    r1 = op(1, "ping")
    if not r1.get("ok"):
        return error("EXECUTION_FAILED", "ping failed")

    op(2, "tap", x=WAKE_X, y=WAKE_Y)
    time.sleep(1.5)

    obs_result = observe_screen()
    if not obs_result.get("ok"):
        # 兜底坐标
        FALLBACK_X, FALLBACK_Y = 513, 97
        op(3, "tap", x=FALLBACK_X, y=FALLBACK_Y)
        return success("aiqiyi.open_detail",
                       f"detail_opened (matched_by=fallback_coords, tap={FALLBACK_X},{FALLBACK_Y})")

    candidates = obs_result.get("data", {}).get("candidates", [])
    hit = find_detail_button_from_candidates(candidates)

    if hit:
        detail_x, detail_y, matched_by = hit
        op(3, "tap", x=detail_x, y=detail_y)
        return success("aiqiyi.open_detail",
                       f"detail_opened (matched_by={matched_by}, tap={detail_x},{detail_y})")

    # 兜底坐标
    FALLBACK_X, FALLBACK_Y = 513, 97
    op(3, "tap", x=FALLBACK_X, y=FALLBACK_Y)
    return success("aiqiyi.open_detail",
                   f"detail_opened (matched_by=fallback_coords, tap={FALLBACK_X},{FALLBACK_Y})")


def run_close(params=None):
    """aiqiyi.close_detail — 退出详情页。"""
    r1 = op(1, "ping")
    if not r1.get("ok"):
        return error("EXECUTION_FAILED", "ping failed")
    op(2, "tap", x=EXIT_X, y=EXIT_Y)
    return success("aiqiyi.close_detail", "detail_closed")


if __name__ == "__main__":
    main()
