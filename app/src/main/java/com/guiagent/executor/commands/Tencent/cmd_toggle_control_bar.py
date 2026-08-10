# -*- coding: utf-8 -*-
"""腾讯视频 打开/关闭控制条。

对标 Java: TencentToggleControlBarCommand → tencent.toggle_control_bar

策略:
  tap 视频区域顶部 (640, 200) — 唤出/收起控制条。

参数:
  无（当前不接受额外参数）

注意:
  腾讯视频不支持侧滑手势调节音量/亮度（详见 readme_tencent.md）。
"""
import json
import sys
import time

from common.utils import success, error, tap, sleep


CMD_NAME = "tencent.toggle_control_bar"

# 唤控制条 — 视频区域顶部
WAKE_X = 640
WAKE_Y = 200


def run(params=None):
    """切换控制条显示/隐藏。

    Returns:
        dict: {"ok": True,  "data": {"command": "tencent.toggle_control_bar", "result": "toggled"}}
              {"ok": False, "error": {"code": "...", "message": "..."}}
    """
    try:
        tap(WAKE_X, WAKE_Y)
        return success(CMD_NAME, "toggled")
    except Exception as e:
        return error("EXECUTION_FAILED", str(e))


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
