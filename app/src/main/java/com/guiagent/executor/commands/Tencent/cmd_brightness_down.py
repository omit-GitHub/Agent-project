# -*- coding: utf-8 -*-
"""腾讯视频 亮度-。支持 count 参数控制调暗格数。

对标 Java: TencentBrightnessDownCommand → tencent.brightness_down

⚠️ 腾讯视频实测不支持侧滑手势调节亮度（详见 readme_tencent.md），
   保留命令以备未来支持。

策略:
  屏幕左侧 25% 处垂直下滑 — 每次滑动调暗一格。

参数:
  {"count": 3} — 调暗 3 格（默认 1，最大 20）
"""
import json
import sys
import time

from common.utils import (
    success, error, swipe, get_screen, parse_count, sleep_ms,
)


CMD_NAME = "tencent.brightness_down"


def _swipe_brightness(up=True):
    """左侧垂直滑动调亮度（单次）。

    Args:
        up: True=上滑(亮度+), False=下滑(亮度-)

    Returns:
        dict: swipe 操作结果
    """
    w, h = get_screen()

    cx = int(w * 0.25)       # 屏幕左侧四分位（亮度调节区）
    y_lo = int(h * 0.425)
    y_hi = int(h * 0.575)

    if up:
        # 上滑: 从 y_hi 到 y_lo（y 坐标减小 = 向上）
        return swipe(cx, y_hi, cx, y_lo, duration=400)
    else:
        # 下滑: 从 y_lo 到 y_hi（y 坐标增大 = 向下）
        return swipe(cx, y_lo, cx, y_hi, duration=400)


def run(params=None):
    """调暗屏幕亮度。

    Args:
        params: 可选 dict，支持 {"count": N}，默认 1，最大 20。

    Returns:
        dict: {"ok": True,  "data": {"command": "tencent.brightness_down", "result": "brightness_down x3"}}
              {"ok": False, "error": {"code": "...", "message": "..."}}
    """
    count = parse_count(params, default=1, max_val=20)

    try:
        for k in range(count):
            swipe_result = _swipe_brightness(up=False)
            if not swipe_result.get("ok"):
                return error("SWIPE_FAILED",
                             f"brightness_down swipe #{k + 1} returned false")
            if k < count - 1:
                sleep_ms(400)
        return success(CMD_NAME, f"brightness_down x{count}")
    except Exception as e:
        return error("EXECUTION_FAILED", str(e))


if __name__ == "__main__":
    # CLI 用法: python cmd_brightness_down.py [count]
    p = None
    if len(sys.argv) > 1:
        try:
            p = {"count": int(sys.argv[1])}
        except ValueError:
            pass
    result = run(p)
    print(json.dumps(result, ensure_ascii=False, indent=2))
