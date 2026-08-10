# -*- coding: utf-8 -*-
"""爱奇艺打开/关闭控制条。

包名: com.qiyi.video.speaker (中屏定制版)

策略:
  控制条默认隐藏，tap 顶部中心 (640, 200) 唤出。
  控制条约 3-5s 后自动隐藏，tap 后需尽快操作。

命令: aiqiyi.toggle_control_bar
参数: 无

用法:
  python aiqiyi/cmd_toggle_control_bar.py

前置: 已在爱奇艺播放页。
      设备已开 GUIAgent 无障碍, 且 adb forward tcp:8322 tcp:8322。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.utils import tap, success, error

# 唤控制条 — 顶部中心
WAKE_X, WAKE_Y = 640, 200


def run(params=None):
    """Registry 入口 — aiqiyi.toggle_control_bar。

    无参数。tap 顶部中心唤出控制条。
    """
    tap(WAKE_X, WAKE_Y)
    return success("aiqiyi.toggle_control_bar", "toggled")


def main():
    result = run()
    if result.get("ok"):
        data = result.get("data", {})
        print(f"已切换控制条: {data.get('result', '')}")
    else:
        err = result.get("error", {})
        print(f"失败: {err.get('message', 'unknown')}", file=sys.stderr)


if __name__ == "__main__":
    main()
