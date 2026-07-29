# -*- coding: utf-8 -*-
"""爱奇艺播放页自动检测模块。

通过 dump UI 判断当前是 TV 模式还是电影模式：
- 有 tv_change_episode (选集) 按钮 → TV 模式
- 无 tv_change_episode → 电影模式

返回对应的按钮坐标。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from send import send


def detect_mode(wait=2.0):
    """检测当前播放页模式。

    Returns:
        dict: 包含 mode ("tv" 或 "movie") 和对应的坐标
    """
    # 唤醒控制条
    send({"id": "detect_1", "op": "tap", "args": {"x": 640, "y": 200}})
    time.sleep(wait)

    # dump UI
    resp = send({"id": "detect_2", "op": "dump", "args": {"depth": 5}})
    if not resp.get("ok"):
        raise Exception("dump failed")

    # 递归检查是否有选集按钮
    def has_episode_btn(node):
        nid = node.get("id", "")
        if "tv_change_episode" in nid:
            return True
        for child in node.get("children", []):
            if has_episode_btn(child):
                return True
        return False

    window = resp.get("data", {}).get("window", {})
    has_episode = has_episode_btn(window)

    mode = "tv" if has_episode else "movie"

    # 根据模式返回对应坐标
    if mode == "tv":
        return {
            "mode": "tv",
            "speed_btn": (846, 724),
            "resolution_btn": (1029, 724),
        }
    else:  # movie
        return {
            "mode": "movie",
            "speed_btn": (988, 724),
            "resolution_btn": (1171, 724),
        }


if __name__ == "__main__":
    # 测试
    result = detect_mode()
    print(f"Detected mode: {result['mode']}")
    print(f"Speed button: {result['speed_btn']}")
    print(f"Resolution button: {result['resolution_btn']}")
