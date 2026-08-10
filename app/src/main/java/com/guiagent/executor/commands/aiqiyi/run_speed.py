# -*- coding: utf-8 -*-
"""爱奇艺调倍速（自动适配电视剧/电影）。

自动检测当前播放页类型：
- 有选集按钮 → TV 模式（坐标 846, 724）
- 无选集按钮 → 电影模式（坐标 988, 724）

用法:
  python aiqiyi/run-speed.py 0.75    # 0.75倍速
  python aiqiyi/run-speed.py 1.0     # 1.0倍速（正常速度）
  python aiqiyi/run-speed.py 1.5     # 1.5倍速
  python aiqiyi/run-speed.py 2.0     # 2.0倍速
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from send import send
from common.utils import success, error


# 倍速选项 res-id 映射
SPEED_OPTIONS = {
    "0.75": "textview_075_speed",
    "1.0": "textview_normal_speed",
    "1.25": "textview_125_speed",
    "1.5": "textview_150_speed",
    "2.0": "textview_200_speed",
}

# TV / 电影模式的倍速按钮坐标
TV_SPEED_BTN = (846, 724)
MOVIE_SPEED_BTN = (988, 724)


def has_episode_btn(node):
    """递归检查 UI 树中是否有选集按钮。"""
    nid = node.get("id", "")
    if "tv_change_episode" in nid:
        return True
    for child in node.get("children", []):
        if has_episode_btn(child):
            return True
    return False


def find_speed_node(res_id, max_tries=5, interval=0.3):
    """根据 res-id 查找倍速节点。"""
    for _ in range(max_tries):
        resp = send({"id": "find", "op": "find", "args": {"id": res_id, "limit": 1}})
        if not resp.get("ok"):
            time.sleep(interval)
            continue

        nodes = resp.get("data", {}).get("nodes", [])
        if nodes:
            return nodes[0]
        time.sleep(interval)
    return None


def main():
    if len(sys.argv) < 2:
        print("用法: python aiqiyi/run-speed.py <倍速>")
        print("可选: 0.75, 1.0, 1.5, 2.0")
        return

    target = sys.argv[1]
    if target not in SPEED_OPTIONS:
        print(f"不支持的倍速: {target}")
        return

    # 1. 唤醒控制条
    send({"id": "1", "op": "tap", "args": {"x": 640, "y": 200}})
    time.sleep(2.0)

    # 2. dump 检测模式
    resp = send({"id": "2", "op": "dump", "args": {"depth": 5}})
    if not resp.get("ok"):
        print("dump 失败")
        return

    window = resp.get("data", {}).get("window", {})
    is_tv = has_episode_btn(window)
    mode = "tv" if is_tv else "movie"
    speed_btn = TV_SPEED_BTN if is_tv else MOVIE_SPEED_BTN
    print(f"检测到模式: {mode}, 倍速按钮坐标: {speed_btn}")

    # 3. 立刻点击倍速按钮（控制条还在）
    send({"id": "3", "op": "tap", "args": {"x": speed_btn[0], "y": speed_btn[1]}})
    time.sleep(1.0)

    # 4. 查找目标倍速节点
    res_id = SPEED_OPTIONS[target]
    node = find_speed_node(res_id)
    if not node:
        print(f"未找到 {target}x 选项")
        return

    # 5. 点击目标
    bounds = node.get("bounds", {})
    cx = (bounds.get("l", 0) + bounds.get("r", 0)) // 2
    cy = (bounds.get("t", 0) + bounds.get("b", 0)) // 2

    send({"id": "4", "op": "tap", "args": {"x": cx, "y": cy}})
    print(f"已切换到 {target}x 倍速 @ ({cx}, {cy})")


def run(params=None):
    """Registry 入口 — aiqiyi.set_speed。

    params: {"speed": "1.5"} 或 {"values": ["1.5"]}
    """
    target = None
    if params:
        target = params.get("speed")
        if not target:
            values = params.get("values", params.get("params"))
            if isinstance(values, list) and len(values) > 0:
                target = str(values[0])
            elif isinstance(values, str):
                target = values
    if not target:
        return error("BAD_PARAMS", "Missing parameter: speed")
    target = str(target)
    if target not in SPEED_OPTIONS:
        return error("BAD_PARAMS",
                     f"Invalid speed: {target}. Valid: {', '.join(sorted(SPEED_OPTIONS.keys()))}")

    # 1. 唤醒控制条
    send({"id": "r1", "op": "tap", "args": {"x": 640, "y": 200}})
    time.sleep(2.0)

    # 2. dump 检测模式
    resp = send({"id": "r2", "op": "dump", "args": {"depth": 5}})
    if not resp.get("ok"):
        return error("EXECUTION_FAILED", "dump failed")

    window = resp.get("data", {}).get("window", {})
    is_tv = has_episode_btn(window)
    speed_btn = TV_SPEED_BTN if is_tv else MOVIE_SPEED_BTN

    # 3. 点击倍速按钮
    send({"id": "r3", "op": "tap", "args": {"x": speed_btn[0], "y": speed_btn[1]}})
    time.sleep(1.0)

    # 4. 查找目标倍速节点
    res_id = SPEED_OPTIONS[target]
    node = find_speed_node(res_id)
    if not node:
        return error("NO_MATCH", f"Speed option {target}x not found")

    # 5. 点击目标
    bounds = node.get("bounds", {})
    cx = (bounds.get("l", 0) + bounds.get("r", 0)) // 2
    cy = (bounds.get("t", 0) + bounds.get("b", 0)) // 2
    send({"id": "r4", "op": "tap", "args": {"x": cx, "y": cy}})

    mode = "TV" if is_tv else "movie"
    return success("aiqiyi.set_speed", f"speed_{target} ({mode} mode)")


if __name__ == "__main__":
    main()
