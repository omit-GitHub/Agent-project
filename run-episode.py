# -*- coding: utf-8 -*-
"""切上一集 / 下一集:进入播放器后,切换到上一集或下一集。

策略(通用,不强依赖某个 APP 的 res-id):
  1. ping 拿屏幕尺寸,算中心点;
  2. tap 中心唤出播放控制条(上一集/下一集按钮通常在控制条上);
  3. find 按钮——按 desc/text 子串匹配方向对应的关键词,
     命中即 tap 其 bounds 中心(节点级最稳);
  4. 找不到按钮——**不乱点**(切集不可逆,点错会跳集),提示用 dump 抓 res-id 传参重试。

若已知目标播放器的上一集/下一集按钮 res-id,可显式传入,跳过 desc 猜测,最稳:
  python run-episode.py next exo_next
  python run-episode.py prev  exo_prev

用法:
  python run-episode.py next                 # 下一集(desc 匹配 + 中心 tap 唤控制条)
  python run-episode.py prev                  # 上一集
  python run-episode.py next <res-id>         # 指定下一集按钮 res-id
  python run-episode.py prev <res-id>        # 指定上一集按钮 res-id
  GUIAGENT_TRANSPORT=local python run-episode.py next    # 设备本机直连

前置: 已在播放器界面(先跑 run-search.py + run-play.py 进入某片源)。
      设备已开 GUIAgent 无障碍服务,且 `adb forward tcp:8321 localabstract:@guiagent`。
"""
import json, sys, time
from send import send

# 各方向对应的 contentDescription / text 子串(中英均覆盖)
HINTS = {
    "next": ["下一集", "下一部", "下一个", "下一集", "next", "后一"],
    "prev": ["上一集", "上一部", "上一个", "上一集", "prev", "previous", "前一"],
}


def op(i, name, **args):
    r = send({"id": str(i), "op": name, "args": args})
    print(f"[{i}] {name} -> ok={r.get('ok')} "
          f"{json.dumps(r.get('data', r.get('err')), ensure_ascii=False)}")
    return r


def center(b):
    cx = (b.get("l", 0) + b.get("r", 0)) // 2
    cy = (b.get("t", 0) + b.get("b", 0)) // 2
    return cx, cy


def find_episode_node(i, hints):
    """按 desc / text 子串匹配上/下一集按钮;控制条带动画,重试。返回首个命中节点或 None。"""
    for k in range(5):
        for field in ("desc", "text"):
            for hint in hints:
                r = op(f"{i}.{field}.{hint}", "find", **{field: hint, "limit": 5})
                if r.get("ok"):
                    ns = r["data"].get("nodes", [])
                    # 过滤掉无 bounds 的脏节点
                    ns = [n for n in ns if n.get("bounds") and
                          n["bounds"].get("b", 0) > n["bounds"].get("t", 0)]
                    if ns:
                        return ns[0]
        time.sleep(0.5)
    return None


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("next", "prev"):
        sys.exit("用法: python run-episode.py next|prev [res-id]\n"
                 "  next=下一集  prev=上一集  (可选 res-id 指定按钮,最稳)")
    direction = sys.argv[1]
    rid = sys.argv[2] if len(sys.argv) > 2 else None
    label = "下一集" if direction == "next" else "上一集"

    # 1. ping 拿屏幕尺寸
    r1 = op(1, "ping")
    if not r1.get("ok"):
        sys.exit("ping 失败——确认无障碍服务已开且 adb forward 已建")
    screen = r1["data"].get("screen", {})
    w, h = screen.get("w", 1280), screen.get("h", 800)
    cx, cy = w // 2, h // 2

    # 2. tap 中心唤出控制条
    op(2, "tap", x=cx, y=cy)
    time.sleep(0.6)

    # 3a. 指定 res-id:直接 click_node,最稳
    if rid:
        r3 = op(3, "click_node", id=rid)
        if r3.get("ok"):
            print(f"\n已点击{label}按钮(id={rid})")
            return
        print(f"click_node id={rid} 失败({r3.get('err')}),改走 desc 匹配")

    # 3b. 通用:desc/text 子串匹配
    #   注意: find 响应不带 nid(flatJson 未输出),命中后用 tap 其 bounds 中心点击。
    node = find_episode_node(4, HINTS[direction])
    if node and node.get("bounds"):
        nx, ny = center(node["bounds"])
        op(5, "tap", x=nx, y=ny)
        print(f"\n已点击{label}按钮({node.get('desc') or node.get('text')}) @({nx},{ny})")
    else:
        # 4. 找不到按钮:切集不可逆,不乱点。提示 dump 抓 res-id。
        print(f"\n未匹配到{label}按钮(desc/text)。切集不可逆,不兜底乱点。")
        print("请用 `python send.py '{\"id\":\"1\",\"op\":\"dump\",\"args\":{\"depth\":6}}'` 抓当前页,")
        print(f"找到{label}按钮的 res-id 后重跑:")
        print(f"  python run-episode.py {direction} <res-id>")


if __name__ == "__main__":
    main()
