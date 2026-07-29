# -*- coding: utf-8 -*-
"""爱奇艺打开/关闭详情页(电视剧简介)。

包名: com.qiyi.video.speaker (中屏定制版)
自动适配不同版本的详情页按钮：
- video_detail1: 位于控制条顶部, 坐标 (534,35)-(599,72) → 中心 (566, 53)
- video_detail2: 位于控制条标题下方, 坐标 (481,79)-(546,119) → 中心 (513, 99)

策略:
  in (进入详情):
    1. tap (640, 200) 唤出控制条(顶部, 比中心可靠)
    2. dump UI 树检测详情页按钮版本
    3. tap 对应坐标点击详情按钮

  out (退出详情):
    1. tap 屏幕左侧非详情页区域 (200, 400) 返回播放页
    (详情页在右侧, 点击左侧空白区域即可关闭)

用法:
  python aiqiyi/run-detail.py in              # 进入详情页
  python aiqiyi/run-detail.py out             # 退出详情页
  GUIAGENT_TRANSPORT=local python aiqiyi/run-detail.py in

前置: 已在爱奇艺播放页。
      设备已开 GUIAgent 无障碍, 且 adb forward tcp:8321 localabstract:@guiagent。
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from send import send

# ── 坐标常量 ──
WAKE_X, WAKE_Y = 640, 200        # 唤控制条(顶部)
DETAIL_V1_X, DETAIL_V1_Y = 566, 53   # video_detail1 中心
DETAIL_V2_X, DETAIL_V2_Y = 513, 99   # video_detail2 中心
EXIT_X, EXIT_Y = 200, 400        # 退出详情:点左侧空白区域


def op(i, name, **args):
    r = send({"id": str(i), "op": name, "args": args})
    print(f"[{i}] {name} -> ok={r.get('ok')} "
          f"{json.dumps(r.get('data', r.get('err')), ensure_ascii=False)}")
    return r


def detect_detail_version():
    """检测详情页按钮版本,返回 (版本, x, y)"""
    resp = send({"id": "detect", "op": "dump", "args": {"depth": 5}})
    if not resp.get("ok"):
        return None, 0, 0

    window = resp["data"].get("window", {})

    def find_detail_btn(node, version):
        if version in node.get("id", ""):
            return True
        for child in node.get("children", []):
            if find_detail_btn(child, version):
                return True
        return False

    # 优先检测 video_detail2 (旧版本)
    if find_detail_btn(window, "video_detail2"):
        return "v2", DETAIL_V2_X, DETAIL_V2_Y
    # 然后检测 video_detail1 (新版本)
    elif find_detail_btn(window, "video_detail1"):
        return "v1", DETAIL_V1_X, DETAIL_V1_Y

    return None, 0, 0


def do_in():
    """进入详情页。"""
    # ping 确认连接
    r1 = op(1, "ping")
    if not r1.get("ok"):
        sys.exit("ping 失败——确认无障碍服务已开且 adb forward 已建")

    # 唤控制条
    op(2, "tap", x=WAKE_X, y=WAKE_Y)
    time.sleep(2.0)

    # 检测详情页按钮版本
    version, detail_x, detail_y = detect_detail_version()
    if not version:
        sys.exit("未找到详情页按钮")

    print(f"检测到详情页按钮版本: {version}, 坐标: ({detail_x}, {detail_y})")

    # 点详情按钮
    op(3, "tap", x=detail_x, y=detail_y)
    print("\n已进入详情页")


def do_out():
    """退出详情页。"""
    # ping 确认连接
    r1 = op(1, "ping")
    if not r1.get("ok"):
        sys.exit("ping 失败——确认无障碍服务已开且 adb forward 已建")

    # 点左侧空白区域退出详情
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
