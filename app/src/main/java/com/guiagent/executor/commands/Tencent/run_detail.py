# -*- coding: utf-8 -*-
"""腾讯视频打开详情页（简介页）。

包名: com.tencent.qqlive.audiobox (中屏定制版)

策略:
  1. ping 拿屏幕尺寸
  2. tap 顶部 (640, 200) 唤出控制条
  3. 等 1.5s 后 tap 简介按钮 (928, 749)
  4. 简介按钮 res-id: tv_plot_introduction

用法:
  python Tencent/run-detail.py

前置: 已在腾讯视频播放页。
      设备已开 GUIAgent 无障碍，且 adb forward tcp:8322 tcp:8322。
"""
import json, os, sys, time

# 让 Tencent/ 下的脚本能找到根目录的 send.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from send import send

# 让本脚本也能找到 common/utils.py（供 run_open() 使用）
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from common.utils import success, error as make_error  # noqa: E402


# 腾讯视频简介按钮 res-id 和坐标
DETAIL_BTN_ID = "com.tencent.qqlive.audiobox:id/tv_plot_introduction"
DETAIL_BTN_X = 928   # (896+960)//2
DETAIL_BTN_Y = 749   # (728+771)//2

# 唤出控制条的坐标（顶部）
WAKE_X = 640
WAKE_Y = 200


def op(i, name, **args):
    r = send({"id": str(i), "op": name, "args": args})
    print(f"[{i}] {name} -> ok={r.get('ok')} "
          f"{json.dumps(r.get('data', r.get('err')), ensure_ascii=False)}")
    return r


def run_open(params=None):
    """腾讯视频打开详情页/简介页（可编程接口）。

    对标 Java: TencentOpenDetailCommand → tencent.open_detail

    Args:
        params: 可选 dict（当前无参数）

    Returns:
        dict: {"ok": True, "data": {"command": "tencent.open_detail", "result": "detail_opened"}}
              或 {"ok": False, "error": {"code": "...", "message": "..."}}
    """
    try:
        # 1. tap 顶部唤出控制条
        send({"id": "rd1", "op": "tap", "args": {"x": WAKE_X, "y": WAKE_Y}})
        time.sleep(1.5)

        # 2. tap 简介按钮（优先用坐标 tap，比 click_node 快，避免控制条自动隐藏）
        send({"id": "rd2", "op": "tap", "args": {"x": DETAIL_BTN_X, "y": DETAIL_BTN_Y}})
        return success("tencent.open_detail", "detail_opened")
    except Exception as e:
        return make_error("EXECUTION_FAILED", str(e))


def main():
    # 1. ping 拿屏幕尺寸
    r1 = op(1, "ping")
    if not r1.get("ok"):
        sys.exit("ping 失败——确认无障碍服务已开且 adb forward 已建")
    screen = r1["data"].get("screen", {})
    w, h = screen.get("w", 1280), screen.get("h", 800)

    # 2. tap 顶部唤出控制条
    op(2, "tap", x=WAKE_X, y=WAKE_Y)
    time.sleep(1.5)

    # 3. tap 简介按钮
    # 优先用坐标 tap（比 click_node 快，避免控制条自动隐藏）
    op(3, "tap", x=DETAIL_BTN_X, y=DETAIL_BTN_Y)
    print(f"\n已点击简介按钮(坐标 {DETAIL_BTN_X},{DETAIL_BTN_Y})")
    print("详情页应该已打开")


if __name__ == "__main__":
    main()
