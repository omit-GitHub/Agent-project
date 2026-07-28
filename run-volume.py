# -*- coding: utf-8 -*-
"""播放界面上下滑调音量:上滑调高、下滑调低。

基于多数视频播放器在播放界面的手势行为:屏幕上滑 = 音量+,下滑 = 音量-。
**仅限播放中可用**——非播放界面(列表/设置页)此手势无效,甚至会触发别的动作
(如下滑拉通知),调用方须确保当前已在播放器界面。

手势在**屏幕右侧**做垂直**慢滑**(x 不变,y 变):上滑 y 从大→小,下滑 y 从小→大。
多数播放器分屏区:右侧上下滑=音量,左侧=亮度,中间左右滑=进度——故必须在右侧;
且要"慢慢"滑(duration 较长),快滑会被当成别的动作(如翻页/快进)。
一次手势调一格音量(Android 音量阶进);调多格传次数或多次调用。

用法:
  python run-volume.py up            # 调高一格
  python run-volume.py down          # 调低一格
  python run-volume.py up 3          # 调高三格
  python run-volume.py down 2        # 调低两格

前置: 已在播放器界面(先跑 run-search.py + run-play.py 进入某片源)。
      设备已开 GUIAgent 无障碍服务(ws 随无障碍常驻;PC 直连设备填 GUIAGENT_WS_HOST=<设备IP> 或先 adb forward tcp:8322 tcp:8322)。

若该播放器不支持上下滑调音量(手势被别的功能占用或无此功能),此脚本无效——
那是播放器行为差异,非 GUIAgent 能力问题。回退方案是协议新增 `volume` op 走
AudioManager(无 root),见 video-player-ops.md §4。
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
        sys.exit("用法: python run-volume.py up|down [次数]\n"
                 "  up=调高  down=调低  (次数默认 1,如 up 3 调高三格)")
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
        sys.exit("ping 失败——确认无障碍服务已开且 ws 可达(设 GUIAGENT_WS_HOST=<设备IP> 或 adb forward tcp:8322 tcp:8322)")
    screen = r1["data"].get("screen", {})
    w, h = screen.get("w", 1280), screen.get("h", 800)

    # 2. 算垂直慢滑起止点:屏幕右侧 x(右侧上下滑=音量),滑距 = 屏高 30%
    #    上滑 y 大->小(从下往上),下滑 y 小->大(从上往下)
    cx = int(w * 0.75)          # 屏幕右侧四分位(避开中间进度区/左侧亮度区)
    y_lo = int(h * 0.35)        # 上端
    y_hi = int(h * 0.65)        # 下端
    if direction == "up":
        x1, y1, x2, y2 = cx, y_hi, cx, y_lo
    else:
        x1, y1, x2, y2 = cx, y_lo, cx, y_hi

    # 3. 连滑 count 次,每次调一格音量;慢滑(duration 长)才被识别为音量手势
    DUR = 700                  # ms,慢滑;太快会被当快滑触发别的动作
    for k in range(count):
        op(f"2.{k}", "swipe", x1=x1, y1=y1, x2=x2, y2=y2, duration=DUR)
        if k < count - 1:
            time.sleep(0.4)

    print(f"\n已{direction}滑 {count} 次 -> {'调高' if direction=='up' else '调低'}约 {count} 格音量")


if __name__ == "__main__":
    main()
