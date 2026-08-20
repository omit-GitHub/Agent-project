# -*- coding: utf-8 -*-
"""爱奇艺播放页自动检测模块 — Phase 7 无 dump 版。

通过 observe_screen() 判断当前是 TV 模式还是电影模式：
- 有"选集"候选 → TV 模式
- 无"选集"候选 → 电影模式

返回对应的按钮坐标。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from send import send
from observation.screen.cmd_observe_screen import observe_screen


def detect_mode(wait=2.0):
    """检测当前播放页模式。

    Returns:
        dict: 包含 mode ("tv" 或 "movie") 和对应的坐标
    """
    # 唤醒控制条
    send({"id": "detect_1", "op": "tap", "args": {"x": 640, "y": 200}})
    time.sleep(wait)

    # observe_screen 获取候选
    obs_result = observe_screen()
    if not obs_result.get("ok"):
        raise Exception("observe_screen failed")

    candidates = obs_result.get("data", {}).get("candidates", [])

    # 检查是否有选集相关候选
    has_episode = False
    for c in candidates:
        c_text = c.get("text", "")
        if "选集" in c_text:
            has_episode = True
            break

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
