# -*- coding: utf-8 -*-
"""reveal_controls — 显式唤出播放器隐藏控件。

设计原则：
  - 仅在播放器等控件被隐藏时调用
  - 点击屏幕中央唤出控制条
  - 执行后不直接宣称成功，Agent 需再次调用 observe_screen() 检查
  - 动作后失效观察缓存

使用场景：
  - Agent 调用 observe_screen() 后发现控件缺失
  - 判断当前是播放页
  - 调用 reveal_controls() 唤出控件
  - 再次调用 observe_screen() 检查控件是否出现

返回格式：
  {
    "ok": True,
    "data": {
      "command": "reveal_controls",
      "result": "tapped screen center to reveal controls",
      "hint": "Please call observe_screen() to verify controls are visible"
    }
  }
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from send import send
from common.utils import success_with_data, error
from ocr.observation_cache import invalidate


def handler(params=None):
    """reveal_controls 命令处理器。"""
    try:
        # 点击屏幕中央（640, 400）唤出控制条
        resp = send({
            "id": "reveal_1",
            "op": "tap",
            "args": {"x": 640, "y": 400}
        })

        if not resp.get("ok"):
            return error("TAP_FAILED", "Failed to tap screen center")

        # 等待动画完成
        time.sleep(0.8)

        # 失效观察缓存
        invalidate()

        # 返回结果（提示 Agent 重新观察）
        return success_with_data("reveal_controls", {
            "result": "tapped screen center to reveal controls",
            "hint": "Please call observe_screen() to verify controls are visible",
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return error("EXECUTION_FAILED", str(e))


def reveal_controls(params=None):
    """命令入口函数。"""
    return handler(params)
