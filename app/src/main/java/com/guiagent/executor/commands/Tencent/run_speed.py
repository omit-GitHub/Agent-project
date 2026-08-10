# -*- coding: utf-8 -*-
"""腾讯视频调倍速。

包名: com.tencent.qqlive.audiobox (中屏定制版)

策略:
  1. ping 拿屏幕尺寸
  2. tap 顶部 (640, 200) 唤出控制条
  3. 等 1.5s 后 tap 倍速按钮 (1027, 749)
  4. 等 1s 让面板渲染
  5. find 目标倍速选项（文本匹配）
  6. tap 选项坐标

倍速选项（5 档）:
  - 0.5X:  (684, 183)
  - 0.75X: (852, 183)
  - 1.0X:  (1020, 183)
  - 1.25X: (1187, 183)
  - 1.5X:  (684, 284)

用法:
  python Tencent/run-speed.py 1.5
  python Tencent/run-speed.py 0.75
  python Tencent/run-speed.py 1.0

前置: 已在腾讯视频播放页。
      设备已开 GUIAgent 无障碍，且 adb forward tcp:8322 tcp:8322。
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from send import send

# 让本脚本也能找到 common/utils.py（供 run() 使用）
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from common.utils import success, error as make_error  # noqa: E402


# 倍速按钮坐标
SPEED_BTN_X = 1027   # (995+1059)//2
SPEED_BTN_Y = 749    # (728+771)//2

# 唤出控制条的坐标（顶部）
WAKE_X = 640
WAKE_Y = 200

# 倍速选项坐标映射
SPEED_OPTIONS = {
    "0.5":  (684, 183),
    "0.75": (852, 183),
    "1.0":  (1020, 183),
    "1.25": (1187, 183),
    "1.5":  (684, 284),
}

# 倍速选项文本
SPEED_TEXTS = {
    "0.5":  "0.5X",
    "0.75": "0.75X",
    "1.0":  "1.0X",
    "1.25": "1.25X",
    "1.5":  "1.5X",
}


def op(i, name, **args):
    r = send({"id": str(i), "op": name, "args": args})
    print(f"[{i}] {name} -> ok={r.get('ok')} "
          f"{json.dumps(r.get('data', r.get('err')), ensure_ascii=False)}")
    return r


def run(params=None):
    """腾讯视频调倍速（可编程接口）。

    对标 Java: TencentSetSpeedCommand → tencent.set_speed

    Args:
        params: 可选 dict，支持 {"speed": "1.5"}
                可选值: 0.5, 0.75, 1.0, 1.25, 1.5

    Returns:
        dict: {"ok": True, "data": {"command": "tencent.set_speed", "result": "speed_1.5"}}
              或 {"ok": False, "error": {"code": "...", "message": "..."}}
    """
    if not params or "speed" not in params:
        return make_error("BAD_PARAMS", "Missing parameter: speed")

    target = str(params["speed"])
    if target not in SPEED_OPTIONS:
        return make_error("BAD_PARAMS",
                          f"Invalid speed: {target}. Valid: {', '.join(SPEED_OPTIONS.keys())}")

    try:
        # 1. tap 顶部唤出控制条
        send({"id": "rs1", "op": "tap", "args": {"x": WAKE_X, "y": WAKE_Y}})
        time.sleep(1.5)

        # 2. tap 倍速按钮
        send({"id": "rs2", "op": "tap", "args": {"x": SPEED_BTN_X, "y": SPEED_BTN_Y}})
        time.sleep(1.0)

        # 3. tap 目标倍速选项坐标
        tx, ty = SPEED_OPTIONS[target]
        send({"id": "rs3", "op": "tap", "args": {"x": tx, "y": ty}})
        return success("tencent.set_speed", f"speed_{target}")
    except Exception as e:
        return make_error("EXECUTION_FAILED", str(e))


def main():
    if len(sys.argv) < 2:
        sys.exit("用法: python Tencent/run-speed.py <倍速>\n"
                 "可选: 0.5, 0.75, 1.0, 1.25, 1.5")

    target = sys.argv[1]
    if target not in SPEED_OPTIONS:
        sys.exit(f"不支持的倍速: {target}\n可选: {', '.join(SPEED_OPTIONS.keys())}")

    # 1. ping 拿屏幕尺寸
    r1 = op(1, "ping")
    if not r1.get("ok"):
        sys.exit("ping 失败——确认无障碍服务已开且 adb forward 已建")

    # 2. tap 顶部唤出控制条
    op(2, "tap", x=WAKE_X, y=WAKE_Y)
    time.sleep(1.5)

    # 3. tap 倍速按钮
    op(3, "tap", x=SPEED_BTN_X, y=SPEED_BTN_Y)
    time.sleep(1.0)

    # 4. 用坐标 tap 目标倍速选项（比 find 更快更可靠）
    tx, ty = SPEED_OPTIONS[target]
    op(4, "tap", x=tx, y=ty)
    print(f"\n已切换到 {target}X 倍速(坐标 {tx},{ty})")


if __name__ == "__main__":
    main()
