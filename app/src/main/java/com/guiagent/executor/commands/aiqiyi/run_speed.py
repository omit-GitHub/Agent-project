# -*- coding: utf-8 -*-
"""爱奇艺调倍速 — Phase 6 无 dump 版。

新流程:
  1. resolve_state() 检查 page_type == 'player'
  2. 解析期望倍速
  3. 唤出控制条（如需要）
  4. observe_screen() 获取候选列表
  5. 找到"倍速"候选 → tap_candidate
  6. 再次 observe_screen() 找到目标倍率 → tap_candidate
  7. verify_after_action(predicate=speed_changed(expected))

外部 API 完全保持兼容。
"""
import os
import sys
import time

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from common.utils import success_with_data, error  # noqa: E402
from observation.state import resolve_state  # noqa: E402
from observation.reveal import reveal_controls  # noqa: E402
from observation.verify import verify_after_action  # noqa: E402
from observation.verify.predicates import speed_changed  # noqa: E402
from observation.verify.recovery import re_reveal  # noqa: E402
from observation.screen.cmd_observe_screen import observe_screen  # noqa: E402
from observation.observation_cache import get_candidate_map, get_candidate_by_id  # noqa: E402

from . import _shared as S  # noqa: E402


def run(params=None):
    """设置倍速。

    params: {"speed": "1.5"} 或 {"values": ["1.5"]}
    """
    params = params or {}
    speed = params.get("speed") or (params.get("values", [None])[0] if params.get("values") else None)
    if not speed:
        return error("BAD_ARGS", "speed param required (e.g., '1.5')")
    speed = str(speed)

    state = resolve_state()
    if not state.is_player_page:
        return error("WRONG_PAGE", f"Not on player page (current: {state.page_type})")

    def action():
        # 控制条未显 → 先唤出
        if state.player and not state.player.control_bar_visible:
            reveal_controls(app=S.APP_NAME)
            time.sleep(0.5)

        # 观察屏幕，找"倍速"候选
        obs_result = observe_screen()
        if not obs_result.get("ok"):
            return error("OBSERVE_FAILED", "Failed to observe screen")

        # 找到"倍速"按钮
        speed_entry_candidate = None
        for c in obs_result.get("data", {}).get("candidates", []):
            if c.get("text") and "倍速" in c.get("text"):
                speed_entry_candidate = c
                break

        if not speed_entry_candidate:
            return error("SPEED_BUTTON_NOT_FOUND", "Speed button not found in candidates")

        # 点击倍速按钮
        from common.utils import tap
        bbox = speed_entry_candidate.get("bbox_px", {})
        cx = (bbox.get("x1", 0) + bbox.get("x2", 0)) // 2
        cy = (bbox.get("y1", 0) + bbox.get("y2", 0)) // 2
        tap_result = tap(cx, cy)
        if not tap_result.get("ok"):
            return error("TAP_FAILED", "Failed to tap speed button")

        time.sleep(0.8)

        # 再次观察，找目标倍率
        obs_result2 = observe_screen()
        if not obs_result2.get("ok"):
            return error("OBSERVE_FAILED", "Failed to observe screen after tapping speed button")

        # 找到目标倍率候选（如 "1.5x" 或 "1.5 倍"）
        target_candidate = None
        target_texts = [f"{speed}x", f"{speed}倍", speed]
        for c in obs_result2.get("data", {}).get("candidates", []):
            c_text = c.get("text", "")
            if any(t in c_text for t in target_texts):
                target_candidate = c
                break

        if not target_candidate:
            return error("SPEED_OPTION_NOT_FOUND", f"Speed option '{speed}' not found")

        # 点击目标倍率
        bbox2 = target_candidate.get("bbox_px", {})
        cx2 = (bbox2.get("x1", 0) + bbox2.get("x2", 0)) // 2
        cy2 = (bbox2.get("y1", 0) + bbox2.get("y2", 0)) // 2
        return tap(cx2, cy2)

    result = verify_after_action(
        action_fn=action,
        predicate=speed_changed(speed),
        recover_fn=re_reveal(app=S.APP_NAME),
        max_retries=1,
        verify_timeout_ms=3000,
    )

    data = {"result": f"set to {speed}", "speed": speed}
    if result.verification:
        data["verification"] = result.verification.to_dict()
    data["recovered"] = result.recovered
    return success_with_data("aiqiyi.set_speed", data)
