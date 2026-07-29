# -*- coding: utf-8 -*-
"""爱奇艺下一集 / 选集适配（仅电视剧）。

包名: com.qiyi.video.speaker (中屏定制版)

功能:
  next          — 下一集(点 im_play_next 按钮)
  select R C    — 选集: 打开选集面板, 点第 R 行第 C 列的格子
                  (用户在屏幕上看到面板后指定行列, 避免正集/预告搞混)

不支持 prev(上一集): 爱奇艺控制栏无上一集按钮, 且正集/预告在选集面板中岔排,
accessibility 无法区分, 需要用户肉眼判断后指定行列。

时序规则(实测确认):
  - 控制条 tap (640,200) 唤出, 约 3-5s 自动隐藏
  - dump 后必须立刻 tap, 不能加 wait
  - 两轮 wake 之间需等 5s+

坐标 (1280x800 横屏):
  唤出控制条:    (640, 200)  顶部(比中心可靠)
  im_play_next:  (177, 724)
  选集入口:      (1212, 724)
  面板 close:    (1237, 53)
  选集网格:      (743,93)-(1277,800), 5列
  单格尺寸:      ~107x107

用法:
  python aiqiyi/run-episode.py next              # 下一集
  python aiqiyi/run-episode.py select 2 3        # 选集: 第2行第3列

前置: 已在爱奇艺播放页。
      设备已开 GUIAgent 无障碍, 且 adb forward tcp:8321 localabstract:@guiagent。
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from send import send

# ── 坐标常量 ──
WAKE_X, WAKE_Y = 640, 200
NEXT_X, NEXT_Y = 177, 724
EPISODE_BTN_X, EPISODE_BTN_Y = 1212, 724
CLOSE_X, CLOSE_Y = 1237, 53

# 选集网格参数
GRID_LEFT = 743
GRID_TOP = 93
GRID_RIGHT = 1277
GRID_BOTTOM = 800
COLS = 5
CELL_W = (GRID_RIGHT - GRID_LEFT) // COLS   # ~107
CELL_H = 107                                 # ~107


def op(i, name, **args):
    r = send({"id": str(i), "op": name, "args": args})
    print(f"[{i}] {name} -> ok={r.get('ok')} "
          f"{json.dumps(r.get('data', r.get('err')), ensure_ascii=False)}")
    return r


def do_next():
    """下一集: wake → tap im_play_next 坐标。"""
    op(10, "tap", x=WAKE_X, y=WAKE_Y)
    time.sleep(2.0)
    op(11, "tap", x=NEXT_X, y=NEXT_Y)
    print(f"\n已点击下一集")


def open_episode_panel():
    """唤控制条 → tap 选集按钮 → 等面板渲染。返回是否成功。"""
    op(20, "tap", x=WAKE_X, y=WAKE_Y)
    time.sleep(2.0)
    op(21, "tap", x=EPISODE_BTN_X, y=EPISODE_BTN_Y)
    time.sleep(1.5)
    return True


def cell_center(row, col):
    """计算第 row 行第 col 列的格子中心坐标。row/col 从 1 开始。"""
    x = GRID_LEFT + (col - 1) * CELL_W + CELL_W // 2
    y = GRID_TOP + (row - 1) * CELL_H + CELL_H // 2
    return x, y


def do_select(row, col):
    """选集: 打开面板 → tap 指定行列的格子 → 关闭面板。"""
    print(f"目标: 第 {row} 行第 {col} 列")

    open_episode_panel()

    tx, ty = cell_center(row, col)
    op(22, "tap", x=tx, y=ty)
    print(f"  点击 ({tx},{ty})")

    time.sleep(0.8)
    op(23, "tap", x=CLOSE_X, y=CLOSE_Y)
    print(f"\n已选择第 {row} 行第 {col} 列")


def main():
    if len(sys.argv) < 2:
        sys.exit("用法: python aiqiyi/run-episode.py next|select\n"
                 "  next              下一集\n"
                 "  select <行> <列>  选集(行/列从1起)")

    cmd = sys.argv[1]

    r1 = op(1, "ping")
    if not r1.get("ok"):
        sys.exit("ping 失败")

    if cmd == "next":
        do_next()
    elif cmd == "select":
        if len(sys.argv) < 4:
            sys.exit("用法: python aiqiyi/run-episode.py select <行> <列>")
        try:
            row = int(sys.argv[2])
            col = int(sys.argv[3])
            if row < 1 or col < 1 or col > COLS:
                sys.exit(f"行列非法: row={row} col={col} (col 须 1-{COLS})")
        except ValueError:
            sys.exit(f"行列非法: {sys.argv[2]} {sys.argv[3]}")
        do_select(row, col)
    else:
        sys.exit(f"未知命令: {cmd}\n  可选: next / select")


if __name__ == "__main__":
    main()
