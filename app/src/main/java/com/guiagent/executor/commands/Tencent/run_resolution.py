# -*- coding: utf-8 -*-
"""腾讯视频调清晰度。

包名: com.tencent.qqlive.audiobox (中屏定制版)

策略:
  1. ping 拿屏幕尺寸
  2. tap 顶部 (640, 200) 唤出控制条
  3. 等 1.5s 后 tap 清晰度按钮 (1138, 749)
  4. 等 1s 让面板渲染
  5. find 目标清晰度选项（文本匹配）
  6. tap 选项坐标

清晰度选项（res-id: voice_quality_iv）:
  - 270P: (757, 170)
  - 480P: (906, 170)
  - 更高清晰度取决于影片是否支持

用法:
  python Tencent/run-resolution.py 480
  python Tencent/run-resolution.py 270

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


# 清晰度按钮坐标
DEFINITION_BTN_X = 1138   # (1095+1182)//2
DEFINITION_BTN_Y = 749    # (725+773)//2

# 唤出控制条的坐标（顶部）
WAKE_X = 640
WAKE_Y = 200

# 清晰度选项坐标映射
RESOLUTION_OPTIONS = {
    "270": (757, 170),
    "480": (906, 170),
    # 720P, 1080P 等需要根据实际影片测试后添加
}

# 清晰度选项文本
RESOLUTION_TEXTS = {
    "270": "270P",
    "480": "480P",
    "720": "720P",
    "1080": "1080P",
}


def op(i, name, **args):
    r = send({"id": str(i), "op": name, "args": args})
    print(f"[{i}] {name} -> ok={r.get('ok')} "
          f"{json.dumps(r.get('data', r.get('err')), ensure_ascii=False)}")
    return r


def run(params=None):
    """腾讯视频调清晰度（可编程接口）。

    对标 Java: TencentSetQualityCommand → tencent.set_quality

    Args:
        params: 可选 dict，支持 {"quality": "480P"} 或 {"quality": "480"}
                已实测: 270P, 480P (720P/1080P 需实测后添加)

    Returns:
        dict: {"ok": True, "data": {"command": "tencent.set_quality", "result": "quality_480P"}}
              或 {"ok": False, "error": {"code": "...", "message": "..."}}
    """
    if not params or "quality" not in params:
        return make_error("BAD_PARAMS", "Missing parameter: quality")

    raw = str(params["quality"]).strip().upper()
    # 兼容 "480" 和 "480P" 两种写法 → 统一去掉尾部 "P" 查 RESOLUTION_OPTIONS
    target_key = raw[:-1] if raw.endswith("P") else raw
    if target_key not in RESOLUTION_OPTIONS:
        verified = ', '.join(k + 'P' for k in RESOLUTION_OPTIONS.keys())
        return make_error("BAD_PARAMS",
                          f"Invalid quality: {raw}. Verified: {verified}"
                          f" (720P/1080P need device testing)")

    try:
        # 1. tap 顶部唤出控制条
        send({"id": "rr1", "op": "tap", "args": {"x": WAKE_X, "y": WAKE_Y}})
        time.sleep(1.5)

        # 2. tap 清晰度按钮
        send({"id": "rr2", "op": "tap", "args": {"x": DEFINITION_BTN_X, "y": DEFINITION_BTN_Y}})
        time.sleep(1.0)

        # 3. tap 目标清晰度选项坐标
        tx, ty = RESOLUTION_OPTIONS[target_key]
        send({"id": "rr3", "op": "tap", "args": {"x": tx, "y": ty}})
        return success("tencent.set_quality", f"quality_{target_key}P")
    except Exception as e:
        return make_error("EXECUTION_FAILED", str(e))


def main():
    if len(sys.argv) < 2:
        sys.exit("用法: python Tencent/run-resolution.py <清晰度>\n"
                 "可选: 270, 480, 720, 1080（取决于影片支持）")

    target = sys.argv[1]
    if target not in RESOLUTION_OPTIONS:
        sys.exit(f"不支持的清晰度: {target}\n"
                 f"已知选项: {', '.join(RESOLUTION_OPTIONS.keys())}\n"
                 f"注意: 更高清晰度需要影片支持，可能需要先测试确认坐标")

    # 1. ping 拿屏幕尺寸
    r1 = op(1, "ping")
    if not r1.get("ok"):
        sys.exit("ping 失败——确认无障碍服务已开且 adb forward 已建")

    # 2. tap 顶部唤出控制条
    op(2, "tap", x=WAKE_X, y=WAKE_Y)
    time.sleep(1.5)

    # 3. tap 清晰度按钮
    op(3, "tap", x=DEFINITION_BTN_X, y=DEFINITION_BTN_Y)
    time.sleep(1.0)

    # 4. 用坐标 tap 目标清晰度选项
    tx, ty = RESOLUTION_OPTIONS[target]
    op(4, "tap", x=tx, y=ty)
    print(f"\n已切换到 {target}P 清晰度(坐标 {tx},{ty})")


if __name__ == "__main__":
    main()
