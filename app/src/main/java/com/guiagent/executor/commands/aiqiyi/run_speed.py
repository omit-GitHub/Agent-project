# -*- coding: utf-8 -*-
"""爱奇艺调倍速 — v2 重构版。

新流程:
  1. resolve_state() 检查 page_type == 'player'
  2. 解析期望倍速
  3. action(): 控制条未显 → reveal；tap 倍速按钮打开面板 → find 目标节点 → tap
  4. verify_after_action(predicate=speed_changed(expected))
  5. 返回 success_with_data 含 verification

外部 API 完全保持兼容。
"""
import os
import sys
import time

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from common.utils import success_with_data, error, tap, find_nodes  # noqa: E402
from observation.state import resolve_state                          # noqa: E402
from observation.reveal import reveal_controls                       # noqa: E402
from observation.verify import verify_after_action                   # noqa: E402
from observation.verify.predicates import speed_changed              # noqa: E402
from observation.verify.recovery import re_reveal                    # noqa: E402

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

    res_id = S.SPEED_OPTIONS.get(speed)
    if not res_id:
        return error("UNSUPPORTED_SPEED", f"Unsupported speed: {speed}. Options: {list(S.SPEED_OPTIONS.keys())}")

    state = resolve_state()
    if not state.is_player_page:
        return error("WRONG_PAGE", f"Not on player page (current: {state.page_type})")

    def action():
        # 控制条未显 → 先唤出
        if state.player and not state.player.control_bar_visible:
            reveal_controls(app=S.APP_NAME)

        # 检测 TV / Movie 模式，点倍速按钮
        from common.utils import dump
        r = dump(depth=5, include=["id"])
        tree = r.get("data", {}).get("window", {}) if r.get("ok") else {}
        has_tv_indicator = _find_in_tree(tree, "tv_change_episode")
        speed_btn = S.TV_SPEED_BTN if has_tv_indicator else S.MOVIE_SPEED_BTN
        tap(*speed_btn)
        time.sleep(1.0)

        # 找目标倍速节点并点击
        nodes = find_nodes(res_id, limit=1)
        if nodes.get("ok"):
            items = nodes.get("data", {}).get("nodes", [])
            if items:
                b = items[0].get("bounds", {})
                cx = (b.get("l", 0) + b.get("r", 0)) // 2
                cy = (b.get("t", 0) + b.get("b", 0)) // 2
                return tap(cx, cy)
        return error("NODE_NOT_FOUND", f"Speed node '{res_id}' not found")

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


def _find_in_tree(tree, id_substring):
    """在 UI 树里递归找含 id_substring 的节点。"""
    if not tree:
        return False
    if id_substring in (tree.get("id") or ""):
        return True
    for child in tree.get("children", []) or []:
        if _find_in_tree(child, id_substring):
            return True
    return False
