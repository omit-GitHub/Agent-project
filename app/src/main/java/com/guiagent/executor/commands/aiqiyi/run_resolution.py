# -*- coding: utf-8 -*-
"""爱奇艺调清晰度 — Phase 6 无 dump 版。

新流程:
  1. resolve_state() 检查 page_type == 'player'
  2. 解析期望清晰度
  3. 唤出控制条（如需要）
  4. observe_screen() 找"清晰度"候选 → tap
  5. 再次 observe_screen() 找目标清晰度 → tap
  6. verify_after_action(predicate=quality_changed(expected))
"""
import os
import sys
import time

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from common.utils import success_with_data, error, tap  # noqa: E402
from observation.state import resolve_state  # noqa: E402
from observation.reveal import reveal_controls  # noqa: E402
from observation.verify import verify_after_action  # noqa: E402
from observation.verify.predicates import quality_changed  # noqa: E402
from observation.verify.recovery import re_reveal  # noqa: E402
from observation.screen.cmd_observe_screen import observe_screen  # noqa: E402

from . import _shared as S  # noqa: E402


def run(params=None):
    """设置清晰度。

    params: {"quality": "720P"} 或 {"quality": "720"}
    """
    params = params or {}
    quality = params.get("quality", "")
    if not quality:
        return error("BAD_ARGS", "quality param required")
    quality = str(quality).upper().replace("P", "")

    state = resolve_state()
    if not state.is_player_page:
        return error("WRONG_PAGE", f"Not on player page (current: {state.page_type})")

    def action():
        # 控制条未显 → 先唤出
        if state.player and not state.player.control_bar_visible:
            reveal_controls(app=S.APP_NAME)
            time.sleep(0.5)

        # 观察屏幕，找"清晰度"按钮
        obs_result = observe_screen()
        if not obs_result.get("ok"):
            return error("OBSERVE_FAILED", "Failed to observe screen")

        quality_btn = None
        for c in obs_result.get("data", {}).get("candidates", []):
            if c.get("text") and "清晰度" in c.get("text"):
                quality_btn = c
                break

        if not quality_btn:
            return error("QUALITY_BUTTON_NOT_FOUND", "Quality button not found")

        # 点击清晰度按钮
        bbox = quality_btn.get("bbox_px", {})
        cx = (bbox.get("x1", 0) + bbox.get("x2", 0)) // 2
        cy = (bbox.get("y1", 0) + bbox.get("y2", 0)) // 2
        tap_result = tap(cx, cy)
        if not tap_result.get("ok"):
            return error("TAP_FAILED", "Failed to tap quality button")

        time.sleep(0.8)

        # 再次观察，找目标清晰度
        obs_result2 = observe_screen()
        if not obs_result2.get("ok"):
            return error("OBSERVE_FAILED", "Failed to observe screen after tapping quality button")

        # 找目标清晰度候选
        target_candidate = None
        target_texts = [f"{quality}P", quality]
        for c in obs_result2.get("data", {}).get("candidates", []):
            c_text = c.get("text", "").upper()
            if any(t in c_text for t in target_texts):
                target_candidate = c
                break

        if not target_candidate:
            return error("QUALITY_OPTION_NOT_FOUND", f"Quality option '{quality}P' not found")

        # 点击目标清晰度
        bbox2 = target_candidate.get("bbox_px", {})
        cx2 = (bbox2.get("x1", 0) + bbox2.get("x2", 0)) // 2
        cy2 = (bbox2.get("y1", 0) + bbox2.get("y2", 0)) // 2
        return tap(cx2, cy2)

    result = verify_after_action(
        action_fn=action,
        predicate=quality_changed(quality),
        recover_fn=re_reveal(app=S.APP_NAME),
        max_retries=1,
        verify_timeout_ms=3000,
    )

    data = {"result": f"set to {quality}P", "quality": quality}
    if result.verification:
        data["verification"] = result.verification.to_dict()
    data["recovered"] = result.recovered
    return success_with_data("aiqiyi.set_quality", data)
