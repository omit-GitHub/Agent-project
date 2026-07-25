# -*- coding: utf-8 -*-
"""调整播放倍速:进入播放器后,把播放倍速切到指定档位。

策略(两步:先开面板,再选档位):
  1. ping 拿屏幕尺寸,算中心点;
  2. tap 中心唤出播放控制条;
  3. 点倍速按钮(唤出档位面板)——传 res-id 则直接 click_node;否则按
     desc/text 子串匹配("倍速""倍数""速率""speed"),命中 tap 其 bounds 中心;
  4. 等面板渲染,精确匹配目标档位——先 `find text=""`/`desc=""` 把面板上有文本
     的节点全拉回,**本地去后缀后精确比较**(覆盖 1.5x/1.5X/1.5×/1.5倍速/裸 1.5),
     避免 find 子串匹配把 "1" 误中到 "1.25×" 之类;
  5. 命中即 tap 档位 bounds 中心;找不到则提示用 dump 抓 res-id。

用法:
  python run-speed.py 1.5                # 切到 1.5x
  python run-speed.py 2                  # 切到 2x
  python run-speed.py 1                  # 切到 1x(正常速)
  python run-speed.py 0.75                # 切到 0.75x
  python run-speed.py 1.5 <speed-btn-id> # 指定倍速按钮 res-id(跳过 desc 猜测,最稳)
  GUIAGENT_TRANSPORT=local python run-speed.py 1.5   # 设备本机直连

前置: 已在播放器界面(先跑 run-search.py + run-play.py 进入某片源)。
      设备已开 GUIAgent 无障碍服务,且 `adb forward tcp:8321 localabstract:@guiagent`。
"""
import json, sys, time
from send import send

# 倍速按钮(唤出档位面板的那个)常见 contentDescription / text 子串
SPEED_BTN_HINTS = ["倍速", "倍数", "速率", "speed", "playback speed", "播放速度"]


def op(i, name, **args):
    r = send({"id": str(i), "op": name, "args": args})
    print(f"[{i}] {name} -> ok={r.get('ok')} "
          f"{json.dumps(r.get('data', r.get('err')), ensure_ascii=False)}")
    return r


def center(b):
    cx = (b.get("l", 0) + b.get("r", 0)) // 2
    cy = (b.get("t", 0) + b.get("b", 0)) // 2
    return cx, cy


def find_node(i, hints, tries=5, gap=0.5):
    """按 desc / text 子串依次匹配;返回首个命中(且有 bounds)节点或 None。"""
    for _ in range(tries):
        for field in ("desc", "text"):
            for hint in hints:
                r = op(f"{i}.{field}.{hint}", "find", **{field: hint, "limit": 5})
                if r.get("ok"):
                    ns = [n for n in r["data"].get("nodes", []) if n.get("bounds") and
                          n["bounds"].get("b", 0) > n["bounds"].get("t", 0)]
                    if ns:
                        return ns[0]
        time.sleep(gap)
    return None


SPEED_SUFFIXES = ["x", "X", "×", "倍速", " 倍速"]   # 档位文本常见后缀(×=U+00D7 乘号)

# 档位的非数字文本别名(数值 rate -> 别名集合)。如芒果 TV 的 1x 档位显示为"正常"。
# 别名会先经 _strip_suffix 去后缀(故"正常倍速"也能命中"正常"),再做精确比较。
RATE_ALIASES = {
    1.0: ["正常", "标准", "原速", "正常速", "标准速", "正常播放", "normal", "Normal"],
}


def _strip_suffix(val):
    """去掉倍速档位文本的常见后缀,返回核心文本。"""
    v = val.strip()
    for suf in SPEED_SUFFIXES:
        if v.endswith(suf):
            return v[:-len(suf)].strip()
    return v


def _is_rate(val, rate):
    """val 是否表示目标倍速 rate。
    1) 数值比较: '1x'/'1.0×'/'1.5倍速'/'裸 1.5' 等去后缀后数值 == rate;
    2) 别名比较: rate==1 时额外接受'正常''标准''原速''normal'等
       (如芒果 TV 的 1x 档位就是'正常')。
    '1.25x' 不命中 rate=1(数值 1.25 != 1,别名也不含)。"""
    core = _strip_suffix(val)
    try:
        if float(core) == float(rate):
            return True
    except ValueError:
        pass
    try:
        aliases = RATE_ALIASES.get(float(rate))
        if aliases and core in aliases:
            return True
    except ValueError:
        pass
    return False


def find_speed_option(i, rate, tries=5, gap=0.5):
    """精确匹配目标档位:find text=""/desc="" 把面板上有文本的节点全拉回,
    本地去后缀后精确比较 == rate。避免子串匹配把 '1' 误中 '1.25×'。"""
    for k in range(tries):
        for field in ("text", "desc"):
            # text="" 子串匹配所有有该字段的节点(Nodes.match: contains("") 恒真)
            r = op(f"{i}.{k}.{field}", "find", **{field: ""}, limit=80)
            if not r.get("ok"):
                continue
            for n in r["data"].get("nodes", []):
                val = (n.get(field) or "").strip()
                b = n.get("bounds") or {}
                if val and _is_rate(val, rate) and b.get("b", 0) > b.get("t", 0):
                    return n
        time.sleep(gap)
    return None


def main():
    if len(sys.argv) < 2:
        sys.exit("用法: python run-speed.py <倍速> [speed-btn-id]\n"
                 "  例: python run-speed.py 1.5   /   python run-speed.py 2")
    rate = sys.argv[1].strip()
    try:
        float(rate)
    except ValueError:
        sys.exit(f"倍速值非法: {rate}(应为数字,如 1.5 / 2 / 0.75)")
    rid = sys.argv[2] if len(sys.argv) > 2 else None

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

    # 3. 点倍速按钮,唤出档位面板
    opened = False
    if rid:
        r3 = op(3, "click_node", id=rid)
        opened = r3.get("ok")
        if not opened:
            print(f"click_node id={rid} 失败({r3.get('err')}),改走 desc 匹配")
    if not opened:
        node = find_node(4, SPEED_BTN_HINTS, tries=5)
        if node and node.get("bounds"):
            nx, ny = center(node["bounds"])
            op(5, "tap", x=nx, y=ny)
            opened = True
            print(f"已点倍速按钮({node.get('desc') or node.get('text')}) @({nx},{ny})")
        else:
            sys.exit("未匹配到倍速按钮(desc/text)。请用 dump 抓 res-id 后重跑:\n"
                     f"  python run-speed.py {rate} <speed-btn-id>")
    time.sleep(0.8)  # 等档位面板渲染

    # 4. 精确匹配目标档位(本地去后缀比较,避免子串误中:如 "1" 不再误中 "1.25×")
    node = find_speed_option(6, rate)
    if node and node.get("bounds"):
        nx, ny = center(node["bounds"])
        op(7, "tap", x=nx, y=ny)
        print(f"\n已选倍速档位 {rate}({node.get('text') or node.get('desc')}) @({nx},{ny})")
    else:
        print(f"\n未匹配到倍速档位 {rate}。可能该播放器不支持此档位,或档位按钮无 text/desc。")
        print("用 dump 看档位面板实际节点,据此调整:")
        print(f"  python send.py '{{\"id\":\"1\",\"op\":\"dump\",\"args\":{{\"depth\":6}}}}'")


if __name__ == "__main__":
    main()
