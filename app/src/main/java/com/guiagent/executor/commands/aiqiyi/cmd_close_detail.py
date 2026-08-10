# -*- coding: utf-8 -*-
"""爱奇艺退出详情页。tap 左侧空白区域返回播放页。

包名: com.qiyi.video.speaker (中屏定制版)

策略:
  详情页在右侧，点击左侧空白区域 (200, 400) 即可关闭。

命令: aiqiyi.close_detail
参数: 无

用法:
  python aiqiyi/cmd_close_detail.py

前置: 已在爱奇艺详情页。
      设备已开 GUIAgent 无障碍, 且 adb forward tcp:8322 tcp:8322。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.utils import tap, success, error

# 退出详情: 点左侧空白区域
EXIT_X, EXIT_Y = 200, 400


def run_close(params=None):
    """Registry 入口 — aiqiyi.close_detail。

    无参数。tap 左侧空白区域关闭详情页。
    """
    tap(EXIT_X, EXIT_Y)
    return success("aiqiyi.close_detail", "detail_closed")


# Alias for unified registry
run = run_close


def main():
    result = run_close()
    if result.get("ok"):
        data = result.get("data", {})
        print(f"已退出详情页: {data.get('result', '')}")
    else:
        err = result.get("error", {})
        print(f"失败: {err.get('message', 'unknown')}", file=sys.stderr)


if __name__ == "__main__":
    main()
