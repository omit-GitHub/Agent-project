# -*- coding: utf-8 -*-
"""腾讯视频调倍速 — v2 重构版。

腾讯视频目前倍速选项直接用坐标点击（无节点 ID 可查）。
新流程: resolve → reveal → tap 倍速按钮 → tap 坐标 → verify。
"""
import os
import sys
import time

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from common.utils import success_with_data, error, tap  # noqa: E402
from observation.state import resolve_state              # noqa: E402
from observation.reveal import reveal_controls           # noqa: E402
from observation.verify import verify_after_action       # noqa: E402
from observation.verify.predicates import speed_changed  # noqa: E402
from observation.verify.recovery import re_reveal        # noqa: E402

from . import _shared as S  # noqa: E402


def run(params=None):
    """设置倍速。"""
    params = params or {}
    speed = params.get("speed") or (params.get("values", [None])[0] if params.get("values") else None)
    if not speed:
        return error("BAD_ARGS", "speed param required")
    speed = str(speed)

    coords = S.SPEED_OPTIONS.get(speed)
    if not coords:
        return error("UNSUPPORTED_SPEED",
                     f"Unsupported speed: {speed}. Options: {list(S.SPEED_OPTIONS.keys())}")

    state = resolve_state()
    if not state.is_player_page:
        return error("WRONG_PAGE", f"Not on player page (current: {state.page_type})")

    def action():
        if state.player and not state.player.control_bar_visible:
            reveal_controls(app=S.APP_NAME)
        # 打开倍速面板
        tap(S.SPEED_BTN_X, S.SPEED_BTN_Y)
        time.sleep(1.0)
        # 点击目标倍速坐标
        return tap(*coords)

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
    return success_with_data("tencent.set_speed", data)
