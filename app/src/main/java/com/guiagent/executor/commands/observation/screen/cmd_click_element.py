# -*- coding: utf-8 -*-
"""click_element — 按 element_id 点击已定位的元素。

设计原则：
  - 必须提供 element_id 和 screen_version
  - 校验 element_id 存在于当前观察缓存
  - 校验 screen_version 未过期
  - 点击元素的 action_point
  - 动作后失效观察缓存

返回格式：
  {
    "ok": True,
    "data": {
      "command": "click_element",
      "result": "clicked element e_17",
      "element_label": "第3集",
      "source": "dump+ocr",
      "click_confidence": 0.94
    }
  }
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from send import send
from common.utils import success_with_data, error
from observation.observation_cache import get_element, check_screen_version, invalidate


def handler(params):
    """click_element 命令处理器。

    Args:
        params: {
            "element_id": "e_17",
            "screen_version": "pkg:act:shotHash:treeHash"
        }

    Returns:
        成功或失败响应
    """
    if not params:
        return error("BAD_PARAMS", "Missing parameters")

    element_id = params.get("element_id")
    screen_version = params.get("screen_version")

    if not element_id:
        return error("BAD_PARAMS", "Missing element_id")
    if not screen_version:
        return error("BAD_PARAMS", "Missing screen_version")

    # 1. 校验 screen_version
    if not check_screen_version(screen_version):
        return error(
            "SCREEN_VERSION_MISMATCH",
            "Screen version has changed. Please call observe_screen() first."
        )

    # 2. 获取元素
    element = get_element(element_id)
    if not element:
        return error(
            "ELEMENT_NOT_FOUND",
            f"Element {element_id} not found in current observation. "
            "It may have expired or the page has changed."
        )

    # 3. 提取点击坐标
    action_point = element.get("action_point")
    if not action_point or len(action_point) != 2:
        return error("INVALID_ELEMENT", f"Element {element_id} has invalid action_point")

    x, y = action_point

    # 4. 执行点击
    try:
        resp = send({
            "id": f"click_{element_id}",
            "op": "tap",
            "args": {"x": int(x), "y": int(y)}
        })

        if not resp.get("ok"):
            return error("CLICK_FAILED", f"Failed to click at ({x}, {y})")

        # 5. 失效观察缓存（动作后必须重新观察）
        invalidate()

        # 6. 返回结果
        return success_with_data("click_element", {
            "result": f"clicked element {element_id}",
            "element_label": element.get("label", ""),
            "source": element.get("source", "unknown"),
            "click_confidence": element.get("click_confidence", 0),
            "action_point": [x, y],
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return error("EXECUTION_FAILED", str(e))


def click_element(params):
    """命令入口函数。"""
    return handler(params)
