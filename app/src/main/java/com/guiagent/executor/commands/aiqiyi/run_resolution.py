# -*- coding: utf-8 -*-
"""爱奇艺调清晰度 — v2 重构版。

新流程同 run_speed: resolve → reveal → tap → find by text → tap → verify。
"""
import os
import sys
import time

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from common.utils import success_with_data, error, tap, dump, collect_texts  # noqa: E402
from observation.state import resolve_state                                  # noqa: E402
from observation.reveal import reveal_controls                               # noqa: E402
from observation.verify import verify_after_action                           # noqa: E402
from observation.verify.predicates import quality_changed                    # noqa: E402
from observation.verify.recovery import re_reveal                            # noqa: E402

from . import _shared as S  # noqa: E402


def run(params=None):
    """设置清晰度。

    params: {"quality": "720P"} 或 {"quality": "720"}
    """
    params = params or {}
    quality = str(params.get("quality", "")).strip()
    if not quality:
        return error("BAD_ARGS", "quality param required")
    # 去掉 "P" 后缀以便查表
    quality_key = quality.upper().replace("P", "")

    patterns = S.RESOLUTION_PATTERNS.get(quality_key)
    if not patterns:
        return error("UNSUPPORTED_QUALITY",
                     f"Unsupported quality: {quality}. Options: {list(S.RESOLUTION_PATTERNS.keys())}")

    state = resolve_state()
    if not state.is_player_page:
        return error("WRONG_PAGE", f"Not on player page (current: {state.page_type})")

    def action():
        if state.player and not state.player.control_bar_visible:
            reveal_controls(app=S.APP_NAME)

        r = dump(depth=5, include=["id"])
        tree = r.get("data", {}).get("window", {}) if r.get("ok") else {}
        has_tv_indicator = _find_in_tree(tree, "tv_change_episode")
        res_btn = S.TV_RESOLUTION_BTN if has_tv_indicator else S.MOVIE_RESOLUTION_BTN
        tap(*res_btn)
        time.sleep(1.0)

        # 在全树里找匹配文字
        r = dump(depth=8, include=["text", "id", "bounds"])
        tree = r.get("data", {}).get("window", {}) if r.get("ok") else {}
        texts = []
        _collect_all_texts(tree, texts)
        for text, node in texts:
            for pattern in patterns:
                if pattern.lower() in text.lower():
                    b = node.get("bounds", {})
                    cx = (b.get("l", 0) + b.get("r", 0)) // 2
                    cy = (b.get("t", 0) + b.get("b", 0)) // 2
                    return tap(cx, cy)
        return error("TEXT_NOT_FOUND", f"Quality text {patterns} not found")

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
    return success_with_data("aiqiyi.set_quality", data)


def _find_in_tree(tree, id_substring):
    if not tree:
        return False
    if id_substring in (tree.get("id") or ""):
        return True
    for child in tree.get("children", []) or []:
        if _find_in_tree(child, id_substring):
            return True
    return False


def _collect_all_texts(node, out, max_depth=10):
    """DFS 收集所有 (text, node) 对。"""
    if not node or max_depth <= 0:
        return
    text = (node.get("text") or "").strip()
    if text:
        out.append((text, node))
    for child in node.get("children", []) or []:
        _collect_all_texts(child, out, max_depth - 1)
