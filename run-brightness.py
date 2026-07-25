# -*- coding: utf-8 -*-
"""播放界面上下滑调亮度:上滑调亮、下滑调暗。

与 run-volume.py 对称:屏幕**左侧**垂直慢滑调亮度(左侧=亮度,右侧=音量)。
**仅限播放中可用**——非播放界面此手势无效或触发别的动作,调用方须确保
当前已在播放器界面。

手势在**屏幕左侧**做垂直**慢滑**(x 不变,y 变):上滑 y 从大→小,下滑 y 从小→大。
多数播放器分屏区:左侧上下滑=亮度,右侧=音量,中间左右滑=进度——故必须在左侧;
且要"慢慢"滑(duration 较长),快滑会被当成别的动作。
一次手势调一格亮度;调多格传次数或多次调用。

用法:
  python run-brightness.py up        # 调亮一格
  python run-brightness.py down      # 调暗一格
  python run-brightness.py up 3      # 调亮三格
  python run-brightness.py down 2    # 调暗两格
  GUIAGENT_TRANSPORT=local python run-brightness.py up   # 设备本机直连

前置: 已在播放器界面(先跑 run-search.py + run-play.py 进入某片源)。
      设备已开 GUIAgent 无障碍服务,且 `adb forward tcp:8321 localabstract:@guiagent`。

若该播放器不支持左侧上下滑调亮度(手势被别的功能占用或无此功能),此脚本无效——
那是播放器行为差异,非 GUIAgent 能力问题。
"""
import json, sys, time
from send import send


def op(i, name, **args):
    r = send({"id": str(i), "op": name, "args": args})
    print(f"[{i}] {name} -> ok={r.get('ok')} "
          f"{json.dumps(r.get('data', r.get('err')), ensure_ascii=False)}")
    return r


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("up", "down"):
        sys.exit("用法: python run-brightness.py up|down [次数]\n"
                 "  up=调亮  down=调暗  (次数默认 1,如 up 3 调亮三格)")
    direction = sys.argv[1]
    count = 1
    if len(sys.argv) > 2:
        try:
            count = int(sys.argv[2])
            if count < 1:
                sys.exit("次数须 >= 1")
        except ValueError:
            sys.exit(f"次数非法: {sys.argv[2]}")

    # 1. ping 拿屏幕尺寸
    r1 = op(1, "ping")
    if not r1.get("ok"):
        sys.exit("ping 失败——确认无障碍服务已开且 adb forward 已建")
    screen = r1["data"].get("screen", {})
    w, h = screen.get("w", 1280), screen.get("h", 800)

    # 2. 算垂直慢滑起止点:屏幕左侧 x(左侧上下滑=亮度),滑距 = 屏高 30%
    #    上滑 y 大->小(从下往上)=调亮,下滑 y 小->大(从上往下)=调暗
    cx = int(w * 0.25)          # 屏幕左侧四分位(避开中间进度区/右侧音量区)
    y_lo = int(h * 0.35)        # 上端
    y_hi = int(h * 0.65)        # 下端
    if direction == "up":
        x1, y1, x2, y2 = cx, y_hi, cx, y_lo
    else:
        x1, y1, x2, y2 = cx, y_lo, cx, y_hi

    # 3. 连滑 count 次,每次调一格亮度;慢滑(duration 长)才被识别为亮度手势
    DUR = 700                  # ms,慢滑;太快会被当快滑触发别的动作
    for k in range(count):
        op(f"2.{k}", "swipe", x1=x1, y1=y1, x2=x2, y2=y2, duration=DUR)
        if k < count - 1:
            time.sleep(0.4)

    print(f"\n已左侧{direction}滑 {count} 次 -> {'调亮' if direction=='up' else '调暗'}约 {count} 格亮度")


if __name__ == "__main__":
    main()
