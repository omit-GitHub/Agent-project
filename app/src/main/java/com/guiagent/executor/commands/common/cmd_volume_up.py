# -*- coding: utf-8 -*-
"""音量+。支持 count 参数控制增加格数。优先手势，失败降级遥控器。

对标 Java: VolumeUpCommand.java

参数:
    {"count": 3} — 调高 3 格（默认 1，最大 20）

手势方式: 屏幕右侧上滑，连滑 count 次
遥控器降级: remote_key VOLUME_UP，连按 count 次
"""
import json
import sys
import time

from common.utils import (
    success, error, gesture, remote_key, get_screen, parse_count, sleep_ms,
)

CMD_NAME = "volume_up"


def _swipe_volume(up=True):
    """右侧垂直滑动调音量（单次）。

    Args:
        up: True=上滑(音量+), False=下滑(音量-)

    Returns:
        dict: gesture 操作结果
    """
    w, h = get_screen()

    cx = int(w * 0.75)       # 屏幕右侧四分位
    y_lo = int(h * 0.425)
    y_hi = int(h * 0.575)

    if up:
        # 上滑: 从 y_hi 到 y_lo（y 坐标减小 = 向上）
        points = [[cx, y_hi], [cx, y_lo]]
    else:
        # 下滑: 从 y_lo 到 y_hi（y 坐标增大 = 向下）
        points = [[cx, y_lo], [cx, y_hi]]

    r = gesture(points, duration=400)
    direction = "volume_up" if up else "volume_down"
    if r.get("ok"):
        return r
    return error("GESTURE_FAILED", f"{direction} gesture returned false")


def run(params=None):
    """调高音量。

    Args:
        params: 可选 dict，支持 {"count": N}，默认 1，最大 20。

    Returns:
        dict: 成功返回 {"ok": true, "data": {"command": "volume_up", "result": "..."}}
              失败返回 {"ok": false, "error": {"code": "...", "message": "..."}}
    """
    count = parse_count(params, default=1, max_val=20)

    # 1. 优先: 屏幕右侧上滑手势，连滑 count 次
    gesture_ok = True
    for k in range(count):
        r = _swipe_volume(up=True)
        if not r.get("ok"):
            gesture_ok = False
            break
        if k < count - 1:
            sleep_ms(300)

    if gesture_ok:
        return success(CMD_NAME, f"volume_up x{count} (gesture)")

    # 2. 降级: 遥控器按键，连按 count 次
    try:
        for k in range(count):
            remote_key("VOLUME_UP", duration=1800)
            if k < count - 1:
                sleep_ms(120)
        return success(CMD_NAME, f"volume_up x{count} (remoteKey fallback)")
    except Exception as e:
        return error("EXECUTION_FAILED", str(e))


if __name__ == "__main__":
    # CLI 用法: python cmd_volume_up.py [count]
    p = None
    if len(sys.argv) > 1:
        try:
            p = {"count": int(sys.argv[1])}
        except ValueError:
            pass
    result = run(p)
    print(json.dumps(result, ensure_ascii=False, indent=2))
