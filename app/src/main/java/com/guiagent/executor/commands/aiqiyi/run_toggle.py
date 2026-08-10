# -*- coding: utf-8 -*-
"""爱奇艺播放/暂停适配。

包名: com.qiyi.video.speaker (中屏定制版)
策略:
  1. ping 拿屏幕尺寸;
  2. tap 中心唤出控制条(控制条默认隐藏, 约 5-8s 后自动隐藏);
  3. 等 0.8s 后 click_node id=btn_pause 精确点击;
  4. 失败则用坐标 tap 兜底。

用法:
  python aiqiyi/run-toggle.py

前置: 已在爱奇艺播放页(先跑 run-search.py + run-play.py 选爱奇艺片源进入)。
      设备已开 GUIAgent 无障碍, 且 adb forward tcp:8322 tcp:8322。
"""
import json, os, sys, time

# 让 aiqiyi/ 下的脚本能找到根目录的 send.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from send import send
from common.utils import success, error

# 爱奇艺播放/暂停按钮 res-id
BTN_PAUSE_ID = "com.qiyi.video.speaker:id/btn_pause"
# 兜底坐标(btn_pause 的 bounds 中心)
BTN_PAUSE_X = 55    # (19+92)//2
BTN_PAUSE_Y = 724   # (692+757)//2


def op(i, name, **args):
    r = send({"id": str(i), "op": name, "args": args})
    print(f"[{i}] {name} -> ok={r.get('ok')} "
          f"{json.dumps(r.get('data', r.get('err')), ensure_ascii=False)}")
    return r


def main():
    # 1. ping 拿屏幕尺寸
    r1 = op(1, "ping")
    if not r1.get("ok"):
        sys.exit("ping 失败——确认无障碍服务已开且 adb forward 已建")
    screen = r1["data"].get("screen", {})
    w, h = screen.get("w", 1280), screen.get("h", 800)
    cx, cy = w // 2, h // 2

    # 2. tap 顶部唤出控制条(避免 tap 中心误触播放/暂停)
    op(2, "tap", x=cx, y=200)
    time.sleep(0.8)

    # 3. click_node 精确点击 btn_pause
    r3 = op(3, "click_node", id=BTN_PAUSE_ID)
    if r3.get("ok"):
        print(f"\n已点击播放/暂停按钮(id=btn_pause)")
        return

    # 4. 兜底: 坐标 tap
    print(f"click_node 失败({r3.get('err')}), 改走坐标 tap")
    op(4, "tap", x=BTN_PAUSE_X, y=BTN_PAUSE_Y)
    print(f"\n已点击播放/暂停按钮(坐标 {BTN_PAUSE_X},{BTN_PAUSE_Y})")


def run(params=None):
    """Registry 入口 — aiqiyi.toggle_play。"""
    # 1. ping 拿屏幕尺寸
    r1 = op(1, "ping")
    if not r1.get("ok"):
        return error("EXECUTION_FAILED", "ping failed")
    screen = r1["data"].get("screen", {})
    w, h = screen.get("w", 1280), screen.get("h", 800)
    cx, cy = w // 2, h // 2

    # 2. tap 顶部唤出控制条
    op(2, "tap", x=cx, y=200)
    time.sleep(0.8)

    # 3. click_node 精确点击 btn_pause
    r3 = op(3, "click_node", id=BTN_PAUSE_ID)
    if r3.get("ok"):
        return success("aiqiyi.toggle_play", "toggled")

    # 4. 兜底: 坐标 tap
    op(4, "tap", x=BTN_PAUSE_X, y=BTN_PAUSE_Y)
    return success("aiqiyi.toggle_play", "toggled (fallback)")


if __name__ == "__main__":
    main()
