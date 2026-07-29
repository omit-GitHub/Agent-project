# -*- coding: utf-8 -*-
"""爱奇艺打开/关闭详情页(电视剧简介)。

包名: com.qiyi.video.speaker (中屏定制版)

策略 (自适应, 不依赖固定坐标):
  in (进入详情):
    1. tap (640, 200) 唤出控制条(顶部, 比中心可靠)
    2. dump UI 树, 子串匹配 id 含 "video_detail" 的节点
       (兼容 video_detail1 / video_detail2 / 将来任何版本)
    3. 用该节点 bounds 算中心, 直接 tap
       (标题再长都不怕, 按钮被挤到哪就点到哪)

  out (退出详情):
    1. tap 屏幕左侧非详情页区域 (200, 400) 返回播放页
       (详情页在右侧, 点击左侧空白区域即可关闭)

用法:
  python aiqiyi/run-detail.py in              # 进入详情页
  python aiqiyi/run-detail.py out             # 退出详情页

前置: 已在爱奇艺播放页。
      设备已开 GUIAgent 无障碍, 且 adb forward tcp:8322 tcp:8322。
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from send import send

# ── 坐标常量 ──
WAKE_X, WAKE_Y = 640, 200        # 唤控制条(顶部)
EXIT_X, EXIT_Y = 200, 400        # 退出详情:点左侧空白区域


def op(i, name, **args):
    r = send({"id": str(i), "op": name, "args": args})
    print(f"[{i}] {name} -> ok={r.get('ok')} "
          f"{json.dumps(r.get('data', r.get('err')), ensure_ascii=False)}")
    return r


def find_detail_button():
    """dump 树, 子串匹配 id 含 'video_detail' 的节点, 返回 (id, cx, cy) 或 None。"""
    resp = send({"id": "detect", "op": "dump",
                 "args": {"depth": 8, "include": ["bounds", "id", "clickable"]}})
    if not resp.get("ok"):
        return None

    def walk(node):
        nid = node.get("id", "")
        if "video_detail" in nid:
            b = node.get("bounds", {})
            cx = (b.get("l", 0) + b.get("r", 0)) // 2
            cy = (b.get("t", 0) + b.get("b", 0)) // 2
            return nid, cx, cy
        for c in node.get("children", []):
            hit = walk(c)
            if hit:
                return hit
        return None

    return walk(resp["data"].get("window", {}))


def do_in():
    """进入详情页。"""
    # ping 确认连接
    r1 = op(1, "ping")
    if not r1.get("ok"):
        sys.exit("ping 失败——确认无障碍服务已开且 adb forward 已建")

    # 唤控制条
    op(2, "tap", x=WAKE_X, y=WAKE_Y)
    time.sleep(1.5)

    # 自适应找详情按钮(支持任意版本 / 任意位置)
    hit = find_detail_button()
    if not hit:
        sys.exit("未找到详情页按钮(id 含 'video_detail' 的节点)")

    nid, detail_x, detail_y = hit
    # 取 id 的最后一段做显示(去掉包名前缀)
    short_id = nid.split("/")[-1] if "/" in nid else nid
    print(f"找到详情按钮: id={short_id}, 坐标=({detail_x}, {detail_y})")

    # 立刻点(控制条 3-5s 后自动隐藏, 不能再等)
    op(3, "tap", x=detail_x, y=detail_y)
    print("\n已进入详情页")


def do_out():
    """退出详情页。"""
    r1 = op(1, "ping")
    if not r1.get("ok"):
        sys.exit("ping 失败——确认无障碍服务已开且 adb forward 已建")

    op(2, "tap", x=EXIT_X, y=EXIT_Y)
    print("\n已退出详情页")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("in", "out"):
        sys.exit("用法: python aiqiyi/run-detail.py in|out\n"
                 "  in   进入详情页\n"
                 "  out  退出详情页")

    cmd = sys.argv[1]
    if cmd == "in":
        do_in()
    else:
        do_out()


if __name__ == "__main__":
    main()
