# -*- coding: utf-8 -*-
"""爱奇艺播放/暂停 — v2 重构版。

新流程:
  1. resolve_state() 检查 page_type == 'player'
  2. 期望的播放状态 = not 当前状态
  3. action(): 控制条未显 → reveal_controls；然后 click_node(btn_pause)
  4. verify_after_action(predicate=playing_state_changed(expected))
  5. 返回 success_with_data 包含 verification 信息

外部 API 完全保持兼容: run(params) → dict
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
    # 1. 拿当前状态
    state = resolve_state()
    if not state.is_player_page:
        return error("WRONG_PAGE",
                     f"Not on player page (current: {state.page_type}, pkg: {state.pkg})")

    # 2. 决定期望的播放状态
    current_playing = (
        state.player.is_playing if state.player and state.player.is_playing is not None
        else None
    )
    # 如果当前状态未知，假设期望切换（toggle 语义）
    expected_playing = not current_playing if current_playing is not None else None

    # 3. 定义 action
    def action():
        # 控制条未显 → 先唤出
        current_state = resolve_state()
        if current_state.player and not current_state.player.control_bar_visible:
            reveal_result = reveal_controls(app=S.APP_NAME)
            if not reveal_result.get("ok"):
                return reveal_result
        # 节点点击（优先），失败降级到坐标
        r = click_node_by_id(S.BTN_PAUSE_ID)
        if not r.get("ok"):
            r = tap(S.BTN_PAUSE_X, S.BTN_PAUSE_Y)
        return r

    # 4. 带验证的执行
    result = verify_after_action(
        action_fn=action,
        predicate=playing_state_changed(expected_playing) if expected_playing is not None
                  else None,  # 状态未知时跳过验证
        recover_fn=re_reveal(app=S.APP_NAME),
        max_retries=1,
        verify_timeout_ms=3000,
    )

    # 5. 返回
    data = {
        "result": "toggled",
        "expected_playing": expected_playing,
    }
    if result.verification:
        data["verification"] = result.verification.to_dict()
    data["recovered"] = result.recovered
    return success_with_data("aiqiyi.toggle_play", data)
