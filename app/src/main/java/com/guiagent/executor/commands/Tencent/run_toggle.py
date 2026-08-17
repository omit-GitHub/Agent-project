# -*- coding: utf-8 -*-
"""腾讯视频播放/暂停 — v2 重构版。

新流程同 aiqiyi/run_toggle: resolve → reveal → click_node → verify。
"""
import os
import sys

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from common.utils import success_with_data, error, click_node_by_id, tap  # noqa: E402
from observation.state import resolve_state                                 # noqa: E402
from observation.reveal import reveal_controls                              # noqa: E402
from observation.verify import verify_after_action                          # noqa: E402
from observation.verify.predicates import playing_state_changed             # noqa: E402
from observation.verify.recovery import re_reveal                           # noqa: E402

from . import _shared as S  # noqa: E402


def run(params=None):
    """切换播放/暂停。"""
    state = resolve_state()
    if not state.is_player_page:
        return error("WRONG_PAGE",
                     f"Not on player page (current: {state.page_type}, pkg: {state.pkg})")

    current_playing = (
        state.player.is_playing if state.player and state.player.is_playing is not None
        else None
    )
    expected_playing = not current_playing if current_playing is not None else None

    def action():
        if state.player and not state.player.control_bar_visible:
            reveal_result = reveal_controls(app=S.APP_NAME)
            if not reveal_result.get("ok"):
                return reveal_result
        # 腾讯视频优先节点点击
        r = click_node_by_id(S.PLAY_BTN_ID)
        if not r.get("ok"):
            r = tap(S.PLAY_BTN_X, S.PLAY_BTN_Y)
        return r

    result = verify_after_action(
        action_fn=action,
        predicate=playing_state_changed(expected_playing) if expected_playing is not None
                  else None,
        recover_fn=re_reveal(app=S.APP_NAME),
        max_retries=1,
        verify_timeout_ms=3000,
    )

    data = {"result": "toggled", "expected_playing": expected_playing}
    if result.verification:
        data["verification"] = result.verification.to_dict()
    data["recovered"] = result.recovered
    return success_with_data("tencent.toggle_play", data)
