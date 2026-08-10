# -*- coding: utf-8 -*-
"""静音。优先遥控器静音键，失败降级连续下滑到最低音量。

对标 Java: VolumeMuteCommand.java

方式1 (优先): remote_key VOLUME_MUTE
方式2 (降级): 连续 3 次 gesture 下滑
"""
import json
import sys
import time

from common.utils import (
    success, error, remote_key, sleep_ms,
)
from common.cmd_volume_up import _swipe_volume  # 复用同一手势逻辑

CMD_NAME = "volume_mute"


def run(params=None):
    """静音。

    Args:
        params: 可选 dict，当前无使用参数。

    Returns:
        dict: 成功返回 {"ok": true, "data": {"command": "volume_mute", "result": "..."}}
              失败返回 {"ok": false, "error": {"code": "...", "message": "..."}}
    """
    # 1. 优先: 遥控器静音键
    try:
        r = remote_key("VOLUME_MUTE", duration=1800)
        if r.get("ok"):
            return success(CMD_NAME, "volume_mute (remoteKey)")
    except Exception:
        pass

    # 2. 降级: 连续 3 次下滑到最低音量
    try:
        for i in range(3):
            _swipe_volume(up=False)
            if i < 2:
                sleep_ms(200)
        return success(CMD_NAME, "volume_mute (gesture fallback, 3x swipe down)")
    except Exception as e:
        return error("EXECUTION_FAILED", str(e))


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
