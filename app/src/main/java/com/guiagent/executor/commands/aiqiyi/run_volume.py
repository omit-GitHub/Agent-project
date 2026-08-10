# -*- coding: utf-8 -*-
"""爱奇艺调音量适配 —— 右侧垂直慢滑。

包名: com.qiyi.video.speaker (中屏定制版)
实测结论: 爱奇艺播放页**支持**右侧垂直慢滑调音量,
         通过调整滑动距离和速度控制每次改变的音量幅度。

策略: 屏幕右侧 (x=w*0.75) 垂直慢滑:
  - 上滑(y 大→小) = 音量+
  - 下滑(y 小→大) = 音量-
  一次手势改变约 5 级音量; 调多格传次数。

用法:
  python aiqiyi/run-volume.py up            # 调高 1 次（约+5级）
  python aiqiyi/run-volume.py down          # 调低 1 次（约-5级）
  python aiqiyi/run-volume.py up 3          # 调高 3 次（约+15级）

前置: 已在爱奇艺播放页。
      设备已开 GUIAgent 无障碍, 且 adb forward tcp:8322 tcp:8322。
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from send import send
from common.utils import success, error, parse_count


def op(i, name, **args):
    r = send({"id": str(i), "op": name, "args": args})
    print(f"[{i}] {name} -> ok={r.get('ok')} "
          f"{json.dumps(r.get('data', r.get('err')), ensure_ascii=False)}")
    return r


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("up", "down"):
        sys.exit("用法: python aiqiyi/run-volume.py up|down [次数]\n"
                 "  up=调高  down=调低  (次数默认 1)")
    direction = sys.argv[1]
    count = 1
    if len(sys.argv) > 2:
        try:
            count = int(sys.argv[2])
            if count < 1:
                sys.exit("次数须 >= 1")
        except ValueError:
            sys.exit(f"次数非法: {sys.argv[2]}")

    # 1. ping 拿屏幕尺寸
    r1 = op(1, "ping")
    if not r1.get("ok"):
        sys.exit("ping 失败——确认无障碍服务已开且 adb forward 已建")
    screen = r1["data"].get("screen", {})
    w, h = screen.get("w", 1280), screen.get("h", 800)

    # 2. 算右侧垂直慢滑起止点
    # 中间值：15% 屏高（约 120px）+ 400ms
    cx = int(w * 0.75)     # 屏幕右侧四分位
    y_lo = int(h * 0.425)  # 上端
    y_hi = int(h * 0.575)  # 下端
    if direction == "up":
        x1, y1, x2, y2 = cx, y_hi, cx, y_lo   # 上滑 = 音量+
    else:
        x1, y1, x2, y2 = cx, y_lo, cx, y_hi   # 下滑 = 音量-

    # 3. 连滑 count 次
    DUR = 400   # ms, 中等速度
    for k in range(count):
        op(f"2.{k}", "swipe", x1=x1, y1=y1, x2=x2, y2=y2, duration=DUR)
        if k < count - 1:
            time.sleep(0.3)

    print(f"\n已{direction}滑 {count} 次 -> 约{'调高' if direction=='up' else '调低'}音量")


# ── Registry 入口函数 ──

def run_up(params=None):
    """aiqiyi.volume_up — 调高音量。

    params: {"count": N} (默认 1)
    """
    count = parse_count(params)

    r1 = op(1, "ping")
    if not r1.get("ok"):
        return error("EXECUTION_FAILED", "ping failed")
    screen = r1["data"].get("screen", {})
    w, h = screen.get("w", 1280), screen.get("h", 800)

    cx = int(w * 0.75)
    y_lo = int(h * 0.425)
    y_hi = int(h * 0.575)
    DUR = 400

    for k in range(count):
        op(f"r2.{k}", "swipe", x1=cx, y1=y_hi, x2=cx, y2=y_lo, duration=DUR)
        if k < count - 1:
            time.sleep(0.3)

    return success("aiqiyi.volume_up", f"volume_up x{count}")


def run_down(params=None):
    """aiqiyi.volume_down — 调低音量。

    params: {"count": N} (默认 1)
    """
    count = parse_count(params)

    r1 = op(1, "ping")
    if not r1.get("ok"):
        return error("EXECUTION_FAILED", "ping failed")
    screen = r1["data"].get("screen", {})
    w, h = screen.get("w", 1280), screen.get("h", 800)

    cx = int(w * 0.75)
    y_lo = int(h * 0.425)
    y_hi = int(h * 0.575)
    DUR = 400

    for k in range(count):
        op(f"r2.{k}", "swipe", x1=cx, y1=y_lo, x2=cx, y2=y_hi, duration=DUR)
        if k < count - 1:
            time.sleep(0.3)

    return success("aiqiyi.volume_down", f"volume_down x{count}")


if __name__ == "__main__":
    main()
