# -*- coding: utf-8 -*-
"""腾讯视频调清晰度 — v2 重构版。"""
import os
import sys
import time

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from common.utils import success_with_data, error, tap  # noqa: E402
from observation.state import resolve_state               # noqa: E402
from observation.reveal import reveal_controls            # noqa: E402
from observation.verify import verify_after_action        # noqa: E402
from observation.verify.predicates import quality_changed # noqa: E402
from observation.verify.recovery import re_reveal         # noqa: E402

from . import _shared as S  # noqa: E402


def run(params=None):
    """设置清晰度。"""
    params = params or {}
    quality = str(params.get("quality", "")).strip()
    if not quality:
        return error("BAD_ARGS", "quality param required")
    quality_key = quality.upper().replace("P", "")

    coords = S.RESOLUTION_OPTIONS.get(quality_key)
    if not coords:
        return error("UNSUPPORTED_QUALITY",
                     f"Unsupported quality: {quality}. "
                     f"Verified options: {list(S.RESOLUTION_OPTIONS.keys())}")

    state = resolve_state()
    if not state.is_player_page:
        return error("WRONG_PAGE", f"Not on player page (current: {state.page_type})")

    def action():
        if state.player and not state.player.control_bar_visible:
            reveal_controls(app=S.APP_NAME)
        # 打开清晰度面板
        tap(S.DEFINITION_BTN_X, S.DEFINITION_BTN_Y)
        time.sleep(1.0)
        # 点击目标清晰度坐标
        return tap(*coords)

    result = verify_after_action(
        action_fn=action,
        predicate=quality_changed(quality_key),
        recover_fn=re_reveal(app=S.APP_NAME),
        max_retries=1,
        verify_timeout_ms=3000,
    )

    data = {"result": f"set to {quality}", "quality": quality}
    if result.verification:
        data["verification"] = result.verification.to_dict()
    data["recovered"] = result.recovered
    return success_with_data("tencent.set_quality", data)
