# -*- coding: utf-8 -*-
"""腾讯视频播放/暂停。

包名: com.tencent.qqlive.audiobox (中屏定制版)

策略:
  1. ping 拿屏幕尺寸
  2. tap 顶部 (640, 200) 唤出控制条
  3. 等 1.5s 后 tap 播放/暂停按钮 (127, 749)
  4. 播放按钮 res-id: playBtn

用法:
  python Tencent/run-toggle.py

前置: 已在腾讯视频播放页。
      设备已开 GUIAgent 无障碍，且 adb forward tcp:8322 tcp:8322。
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from send import send

# 让本脚本也能找到 common/utils.py（供 run() 使用）
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from common.utils import success, error as make_error  # noqa: E402


# 腾讯视频播放/暂停按钮 res-id 和坐标
PLAY_BTN_ID = "com.tencent.qqlive.audiobox:id/playBtn"
PLAY_BTN_X = 127   # (105+150)//2
PLAY_BTN_Y = 749   # (727+772)//2

# 唤出控制条的坐标（顶部）
WAKE_X = 640
WAKE_Y = 200


def op(i, name, **args):
    r = send({"id": str(i), "op": name, "args": args})
    print(f"[{i}] {name} -> ok={r.get('ok')} "
          f"{json.dumps(r.get('data', r.get('err')), ensure_ascii=False)}")
    return r


def run(params=None):
    """腾讯视频播放/暂停（可编程接口）。

    对标 Java: TencentTogglePlayCommand → tencent.toggle_play

    Args:
        params: 可选 dict（当前无参数）

    Returns:
        dict: {"ok": True, "data": {"command": "tencent.toggle_play", "result": "toggled"}}
              或 {"ok": False, "error": {"code": "...", "message": "..."}}
    """
    try:
        # 1. ping 拿屏幕尺寸
        r1 = send({"id": "r1", "op": "ping", "args": {}})
        if not r1.get("ok"):
            return make_error("EXECUTION_FAILED",
                              "ping failed — accessibility service or adb forward not ready")

        # 2. tap 顶部唤出控制条
        send({"id": "r2", "op": "tap", "args": {"x": WAKE_X, "y": WAKE_Y}})
        time.sleep(1.5)

        # 3. tap 播放/暂停按钮
        send({"id": "r3", "op": "tap", "args": {"x": PLAY_BTN_X, "y": PLAY_BTN_Y}})
        return success("tencent.toggle_play", "toggled")
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

    # 3. tap 播放/暂停按钮
    op(3, "tap", x=PLAY_BTN_X, y=PLAY_BTN_Y)
    print(f"\n已点击播放/暂停按钮(坐标 {PLAY_BTN_X},{PLAY_BTN_Y})")


if __name__ == "__main__":
    main()
