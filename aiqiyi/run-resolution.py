# -*- coding: utf-8 -*-
"""爱奇艺调清晰度（自动适配电视剧/电影）。

自动检测当前播放页类型：
- 有选集按钮 → TV 模式（坐标 1029, 724）
- 无选集按钮 → 电影模式（坐标 1171, 724）

清晰度选项: 1080P(VIP) / 720P(登录) / 480P(免费)
点击非当前清晰度会跳转登录/会员页面，跳转即表示点击成功。

用法:
  python aiqiyi/run-resolution.py 720     # 切到720P
  python aiqiyi/run-resolution.py 1080    # 切到1080P
  python aiqiyi/run-resolution.py 480     # 切到480P
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from send import send


# 清晰度文本匹配
RESOLUTION_PATTERNS = {
    "1080": ["1080P", "1080p"],
    "720": ["720P", "720p"],
    "480": ["480P", "480p"],
}

# TV / 电影模式的清晰度按钮坐标
TV_RESOLUTION_BTN = (1029, 724)
MOVIE_RESOLUTION_BTN = (1171, 724)


def has_episode_btn(node):
    """递归检查 UI 树中是否有选集按钮。"""
    nid = node.get("id", "")
    if "tv_change_episode" in nid:
        return True
    for child in node.get("children", []):
        if has_episode_btn(child):
            return True
    return False


def find_node_by_text(patterns, max_tries=5, interval=0.3):
    """根据文本模式查找节点。"""
    for _ in range(max_tries):
        resp = send({"id": "find", "op": "find", "args": {"text": "", "limit": 100}})
        if not resp.get("ok"):
            time.sleep(interval)
            continue

        nodes = resp.get("data", {}).get("nodes", [])
        for node in nodes:
            text = node.get("text", "")
            for pattern in patterns:
                if pattern in text:
                    return node
        time.sleep(interval)
    return None


def main():
    if len(sys.argv) < 2:
        print("用法: python aiqiyi/run-resolution.py <清晰度>")
        print("可选: 720, 1080, 480")
        return

    target = sys.argv[1]
    if target not in RESOLUTION_PATTERNS:
        print(f"不支持的清晰度: {target}")
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
    resolution_btn = TV_RESOLUTION_BTN if is_tv else MOVIE_RESOLUTION_BTN
    print(f"检测到模式: {mode}, 清晰度按钮坐标: {resolution_btn}")

    # 3. 立刻点击清晰度按钮（控制条还在）
    send({"id": "3", "op": "tap", "args": {"x": resolution_btn[0], "y": resolution_btn[1]}})
    time.sleep(1.0)

    # 4. 查找目标清晰度节点
    patterns = RESOLUTION_PATTERNS[target]
    node = find_node_by_text(patterns)
    if not node:
        print(f"未找到 {target}P 选项")
        return

    # 5. 点击目标
    bounds = node.get("bounds", {})
    cx = (bounds.get("l", 0) + bounds.get("r", 0)) // 2
    cy = (bounds.get("t", 0) + bounds.get("b", 0)) // 2

    send({"id": "4", "op": "tap", "args": {"x": cx, "y": cy}})
    text = node.get("text", "")
    print(f"已点击 {text} @ ({cx}, {cy})")
    print("注意: 可能会跳转到登录/会员页面，这是正常的")


if __name__ == "__main__":
    main()
