# -*- coding: utf-8 -*-
"""夸克网盘返回功能（智能自适应）— Phase 6 无 dump 版。

自动检测当前页面类型，智能决定返回次数:
    - 文件浏览页面：返回 1 次
    - 视频播放页面：返回 2 次（退出播放器）
    - 自动处理确认对话框
"""
import json
import sys

from common.utils import success, error, global_action, gesture, sleep_ms  # noqa: E402
from observation.screen.cmd_observe_screen import observe_screen  # noqa: E402
from observation.state import resolve_state  # noqa: E402

CMD_NAME = "quark.go_back"
MAX_BACK_PRESSES = 3


def run(params=None):
    """智能返回。"""
    back_press_count = 0

    for i in range(MAX_BACK_PRESSES):
        # 执行返回
        r = global_action("BACK")
        if not r.get("ok"):
            if back_press_count == 0:
                return error("EXECUTION_FAILED", "Failed to perform back action")
            break

        back_press_count += 1
        sleep_ms(500)

        # 处理可能出现的确认对话框
        _handle_confirmation_dialog()

        sleep_ms(300)

        # 检查是否到达文件列表页面
        if _check_has_file_list():
            break

        # 检查是否还在夸克网盘应用中
        if not _check_in_quark_app():
            break

    if back_press_count == 0:
        return error("EXECUTION_FAILED", "No back action performed")
    elif back_press_count == 1:
        return success(CMD_NAME, "back_once")
    else:
        return success(CMD_NAME, f"back_multiple_{back_press_count}")


def _check_in_quark_app():
    """检查是否还在夸克网盘应用中（通过 ping 获取包名）。"""
    state = resolve_state()
    return "quark" in state.pkg.lower()


def _check_has_file_list():
    """检查当前页面是否有文件列表。"""
    obs_result = observe_screen()
    if not obs_result.get("ok"):
        return False

    candidates = obs_result.get("data", {}).get("candidates", [])

    # 方法 1：查找日期文本候选（YYYY/MM/DD 格式）
    import re
    date_pattern = re.compile(r"\d{4}/\d{2}/\d{2}")
    for c in candidates:
        c_text = c.get("text", "")
        if date_pattern.search(c_text):
            return True

    # 方法 2：查找多个 card 类型候选
    card_count = sum(1 for c in candidates if c.get("kind") == "card")
    if card_count >= 3:
        return True

    return False


def _handle_confirmation_dialog():
    """处理退出确认对话框。"""
    obs_result = observe_screen()
    if not obs_result.get("ok"):
        return False

    candidates = obs_result.get("data", {}).get("candidates", [])
    confirm_texts = ["确认", "确定", "是", "退出", "OK", "Yes"]

    for c in candidates:
        c_text = c.get("text", "")
        if any(t in c_text for t in confirm_texts):
            bbox = c.get("bbox_px", {})
            cx = (bbox.get("x1", 0) + bbox.get("x2", 0)) // 2
            cy = (bbox.get("y1", 0) + bbox.get("y2", 0)) // 2
            gesture([[cx, cy]], 200)
            return True

    return False


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
