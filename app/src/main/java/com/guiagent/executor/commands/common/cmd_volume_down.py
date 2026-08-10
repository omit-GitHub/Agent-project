# -*- coding: utf-8 -*-
"""音量-。支持 count 参数控制减少格数。优先手势，失败降级遥控器。

对标 Java: VolumeDownCommand.java

参数:
    {"count": 3} — 调低 3 格（默认 1，最大 20）

手势方式: 屏幕右侧下滑，连滑 count 次
遥控器降级: remote_key VOLUME_DOWN，连按 count 次
"""
import json
import sys
import time

from common.utils import (
    success, error, gesture, remote_key, get_screen, parse_count, sleep_ms,
)
from common.cmd_volume_up import _swipe_volume  # 复用同一手势逻辑

CMD_NAME = "volume_down"


def run(params=None):
    """调低音量。

    Args:
        params: 可选 dict，支持 {"count": N}，默认 1，最大 20。

    Returns:
        dict: 成功返回 {"ok": true, "data": {"command": "volume_down", "result": "..."}}
              失败返回 {"ok": false, "error": {"code": "...", "message": "..."}}
    """
    count = parse_count(params, default=1, max_val=20)

    # 1. 优先: 屏幕右侧下滑，连滑 count 次
    gesture_ok = True
    for k in range(count):
        r = _swipe_volume(up=False)
        if not r.get("ok"):
            gesture_ok = False
            break
        if k < count - 1:
            sleep_ms(300)

    if gesture_ok:
        return success(CMD_NAME, f"volume_down x{count} (gesture)")

    # 2. 降级: 遥控器按键，连按 count 次
    try:
        for k in range(count):
            remote_key("VOLUME_DOWN", duration=1800)
            if k < count - 1:
                sleep_ms(120)
        return success(CMD_NAME, f"volume_down x{count} (remoteKey fallback)")
    except Exception as e:
        return error("EXECUTION_FAILED", str(e))


if __name__ == "__main__":
    # CLI 用法: python cmd_volume_down.py [count]
    p = None
    if len(sys.argv) > 1:
        try:
            p = {"count": int(sys.argv[1])}
        except ValueError:
            pass
    result = run(p)
    print(json.dumps(result, ensure_ascii=False, indent=2))
