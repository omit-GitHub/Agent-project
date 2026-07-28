# -*- coding: utf-8 -*-
"""切换播放/暂停:点开片源进入播放器后,在任意视频播放器上切换播放状态。

策略(解耦"唤控制条"与"切换",避免二次操作抵消):
  1. ping 拿屏幕尺寸,算中心点;
  2. 先 find 播放/暂停按钮——find text=""/desc="" 一次拉回有文本节点,本地按
     desc/text 子串匹配("播放""暂停""play""pause""继续"resume");若控制条当前
     可见,直接命中 → tap 其 bounds 中心,结束;
  3. find 不到(控制条隐藏)→ tap 中心一次(唤出控制条,或直接切换播放);
  4. 再 find 按钮 → 命中则 tap,结束;再找不到则**停手**——
     因为 step3 的 tap 中心可能已切换播放,再 tap 会抵消(原 bug 正是如此:
     控制条消失时 tap 中心直接切了播放,find 不到,兜底再 tap 又切回)。

关键: 不再用"find 不到就 tap 中心兜底"——tap 中心有切换副作用,二次 tap 会抵消,
     控制条消失时尤其明显。

若已知目标播放器的播放按钮 res-id,可显式传入,跳过 desc 猜测,最稳:
  python run-toggle.py exo_player_play_pause

用法:
  python run-toggle.py                 # 通用模式:desc 匹配(解耦,不二次 tap)
  python run-toggle.py <res-id>        # 指定播放/暂停按钮 res-id,直接 click_node

前置: 已在播放器界面(先跑 run-search.py + run-play.py 进入某片源)。
      设备已开 GUIAgent 无障碍服务(ws 随无障碍常驻;PC 直连设备填 GUIAGENT_WS_HOST=<设备IP> 或先 adb forward tcp:8322 tcp:8322)。
"""
import json, sys, time
from send import send

# 播放/暂停按钮常见的 contentDescription / text 子串(中英均覆盖)
TOGGLE_HINTS = ["暂停", "播放", "pause", "play", "继续", "resume"]


def op(i, name, **args):
    r = send({"id": str(i), "op": name, "args": args})
    print(f"[{i}] {name} -> ok={r.get('ok')} "
          f"{json.dumps(r.get('data', r.get('err')), ensure_ascii=False)}")
    return r


def center(b):
    cx = (b.get("l", 0) + (b.get("r", 0))) // 2
    cy = (b.get("t", 0) + (b.get("b", 0))) // 2
    return cx, cy


def find_toggle_node(i, tries=5, gap=0.4):
    """find text=""/desc="" 一次拉回有文本节点,本地按 hints 子串匹配。
    比逐 hint find 快(2 次往返 vs 12 次),控制条短暂显示时更易命中。返回首个命中或 None。"""
    for k in range(tries):
        for field in ("text", "desc"):
            r = op(f"{i}.{k}.{field}", "find", **{field: ""}, limit=80)
            if not r.get("ok"):
                continue
            for n in r["data"].get("nodes", []):
                val = (n.get(field) or "")
                b = n.get("bounds") or {}
                if val and any(h in val for h in TOGGLE_HINTS) and b.get("b", 0) > b.get("t", 0):
                    return n
        time.sleep(gap)
    return None


def tap_node(i, node):
    """tap 节点 bounds 中心(find 响应无 nid,故用坐标 tap)。返回 (x,y)。"""
    nx, ny = center(node["bounds"])
    op(i, "tap", x=nx, y=ny)
    return nx, ny


def main():
    rid = sys.argv[1] if len(sys.argv) > 1 else None

    # 1. ping 拿屏幕尺寸
    r1 = op(1, "ping")
    if not r1.get("ok"):
        sys.exit("ping 失败——确认无障碍服务已开且 ws 可达(设 GUIAGENT_WS_HOST=<设备IP> 或 adb forward tcp:8322 tcp:8322)")
    screen = r1["data"].get("screen", {})
    w, h = screen.get("w", 1080), screen.get("h", 1920)
    cx, cy = w // 2, h // 2

    # 2. 指定 res-id:直接 click_node,最稳
    if rid:
        r2 = op(2, "click_node", id=rid)
        if r2.get("ok"):
            print(f"\n已点击播放/暂停按钮(id={rid})")
            return
        print(f"click_node id={rid} 失败({r2.get('err')}),改走 desc 匹配")

    # 3. 先 find 按钮(控制条当前可见则直接命中)→ 命中即 tap,结束
    node = find_toggle_node(3)
    if node and node.get("bounds"):
        nx, ny = tap_node(4, node)
        print(f"\n已点击播放/暂停按钮({node.get('desc') or node.get('text')}) @({nx},{ny})")
        return

    # 4. 控制条隐藏:tap 中心一次(唤出控制条,或直接切换播放)
    op(5, "tap", x=cx, y=cy)
    time.sleep(0.5)

    # 5. 再 find 按钮:命中则 tap;未命中则停手(避免二次 tap 抵消)
    node = find_toggle_node(6)
    if node and node.get("bounds"):
        nx, ny = tap_node(7, node)
        print(f"\n已点击播放/暂停按钮({node.get('desc') or node.get('text')}) @({nx},{ny})")
    else:
        print("\n未匹配到按钮。tap 中心可能已切换播放(不再二次操作避免抵消)。")
        print("若实际未切换,说明按钮无 desc/text,用 dump 抓 res-id 后重跑:")
        print(f"  python run-toggle.py <res-id>")


if __name__ == "__main__":
    main()
