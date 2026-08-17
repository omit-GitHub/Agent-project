# -*- coding: utf-8 -*-
"""内置验证谓词 — 每个谓词是一个工厂函数，返回 () -> PredicateResult。

设计：
  - 谓词以"工厂"形式暴露：bar_visible() 返回一个 callable
  - callable 内部自己 resolve_state() 拿最新状态
  - 这样 verify() 每次 poll 都能拿到最新状态
  - 谓词之间互相独立，可组合

8 个内置谓词：
  1. bar_visible(app)               — 控制条是否可见
  2. playing_state_changed(expected)— is_playing 匹配期望
  3. episode_changed(expected_ep)   — 集数变化
  4. speed_changed(expected)        — 倍速变化
  5. quality_changed(expected)      — 清晰度变化
  6. overlay_appeared(type)         — 特定浮层出现
  7. node_present(id_substr)        — 节点 ID 存在
  8. text_present(text_substr)      — 可见文字包含
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

# 让本模块能找到 observation.state
import os
import sys
_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from state import resolve_state  # noqa: E402


# ─────────────── 结果数据类 ───────────────

@dataclass
class PredicateResult:
    """谓词检测结果。"""
    verified: bool                          # 是否满足
    evidence: Dict[str, Any] = field(default_factory=dict)  # 触发判定的证据
    confidence: str = "high"                # high / medium / low
    message: str = ""                       # 人可读说明

    def __bool__(self):
        """允许直接 if result: 判定。"""
        return self.verified


# ─────────────── 谓词 1: bar_visible ───────────────

def bar_visible(app: Optional[str] = None) -> Callable[[], PredicateResult]:
    """控制条是否可见。

    Args:
        app: 可选，用于校验是否处于目标 App
    """
    def check() -> PredicateResult:
        state = resolve_state()
        if not state.is_player_page:
            return PredicateResult(
                False,
                evidence={"page_type": state.page_type},
                confidence="high",
                message="not on player page",
            )
        if state.player is None:
            return PredicateResult(
                False,
                evidence={"reason": "no_player_state"},
                confidence="medium",
                message="player state unavailable",
            )
        visible = state.player.control_bar_visible
        return PredicateResult(
            visible,
            evidence={
                "control_bar_visible": visible,
                "pkg": state.pkg,
            },
            confidence="high",
            message="control bar visible" if visible else "control bar hidden",
        )
    return check


# ─────────────── 谓词 2: playing_state_changed ───────────────

def playing_state_changed(expected: bool) -> Callable[[], PredicateResult]:
    """is_playing 是否匹配期望。

    Args:
        expected: True=期望正在播放，False=期望已暂停
    """
    def check() -> PredicateResult:
        state = resolve_state()
        if state.player is None:
            return PredicateResult(
                False,
                evidence={"reason": "no_player_state"},
                confidence="low",
                message="player state unavailable",
            )
        actual = state.player.is_playing
        if actual is None:
            return PredicateResult(
                False,
                evidence={"reason": "is_playing_unknown"},
                confidence="low",
                message="play state cannot be determined",
            )
        matched = (actual == expected)
        return PredicateResult(
            matched,
            evidence={
                "expected_playing": expected,
                "actual_playing": actual,
            },
            confidence="high",
            message=f"playing={'yes' if actual else 'no'} (expected {'yes' if expected else 'no'})",
        )
    return check


# ─────────────── 谓词 3: episode_changed ───────────────

def episode_changed(expected_episode: Optional[str] = None) -> Callable[[], PredicateResult]:
    """当前集数是否等于期望。

    Args:
        expected_episode: 期望的集数文本（如"第3集"）。None 表示"任何集数变化即可"。
    """
    # 初始基线（调用方在动作前应该先调用 resolve_state() 拿 baseline）
    baseline_state = resolve_state()
    baseline_episode = (
        baseline_state.player.current_episode
        if baseline_state.player else None
    )

    def check() -> PredicateResult:
        state = resolve_state()
        current = state.player.current_episode if state.player else None
        if expected_episode is not None:
            matched = current == expected_episode
            return PredicateResult(
                matched,
                evidence={"expected": expected_episode, "current": current},
                confidence="medium",
                message=f"episode={current} (expected {expected_episode})",
            )
        else:
            # 任何变化即可
            changed = (current is not None and current != baseline_episode)
            return PredicateResult(
                changed,
                evidence={"baseline": baseline_episode, "current": current},
                confidence="medium",
                message=f"episode changed from {baseline_episode} to {current}",
            )
    return check


# ─────────────── 谓词 4: speed_changed ───────────────

def speed_changed(expected: str) -> Callable[[], PredicateResult]:
    """当前倍速是否等于期望。

    Args:
        expected: "0.75" / "1.0" / "1.5" / "2.0" 等
    """
    def check() -> PredicateResult:
        state = resolve_state()
        current = state.player.current_speed if state.player else None
        matched = (current == expected)
        return PredicateResult(
            matched,
            evidence={"expected_speed": expected, "current_speed": current},
            confidence="medium",
            message=f"speed={current} (expected {expected})",
        )
    return check


# ─────────────── 谓词 5: quality_changed ───────────────

def quality_changed(expected: str) -> Callable[[], PredicateResult]:
    """当前清晰度是否等于期望。"""
    def check() -> PredicateResult:
        state = resolve_state()
        current = state.player.current_quality if state.player else None
        # 容错：用户可能传 "720" 或 "720P"，都接受
        exp_norm = expected.upper().replace("P", "")
        cur_norm = (current or "").upper().replace("P", "")
        matched = (cur_norm == exp_norm)
        return PredicateResult(
            matched,
            evidence={"expected_quality": expected, "current_quality": current},
            confidence="medium",
            message=f"quality={current} (expected {expected})",
        )
    return check


# ─────────────── 谓词 6: overlay_appeared ───────────────

def overlay_appeared(overlay_type: str) -> Callable[[], PredicateResult]:
    """特定浮层是否出现。

    Args:
        overlay_type: "speed_panel" | "quality_panel" | "episode_panel" | "detail_panel"
    """
    def check() -> PredicateResult:
        state = resolve_state()
        matched = (state.overlay == overlay_type)
        return PredicateResult(
            matched,
            evidence={"expected_overlay": overlay_type, "current_overlay": state.overlay},
            confidence="high",
            message=f"overlay={state.overlay} (expected {overlay_type})",
        )
    return check


# ─────────────── 谓词 7: node_present ───────────────

def node_present(id_substring: str) -> Callable[[], PredicateResult]:
    """UI 树中是否存在包含指定子串的节点 ID。"""
    import os
    import sys
    _HERE2 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _HERE2 not in sys.path:
        sys.path.insert(0, _HERE2)
    from send import send  # noqa: E402

    def check() -> PredicateResult:
        try:
            r = send({
                "id": "pred_find",
                "op": "find",
                "args": {"id": id_substring, "limit": 1},
            })
            if not r.get("ok"):
                return PredicateResult(False, evidence={"reason": "find_failed"})
            nodes = r.get("data", {}).get("nodes", [])
            matched = len(nodes) > 0
            return PredicateResult(
                matched,
                evidence={
                    "id_substring": id_substring,
                    "match_count": len(nodes),
                },
                confidence="high",
                message=f"found {len(nodes)} node(s) matching '{id_substring}'",
            )
        except Exception as e:
            return PredicateResult(False, evidence={"error": str(e)})
    return check


# ─────────────── 谓词 8: text_present ───────────────

def text_present(text_substring: str) -> Callable[[], PredicateResult]:
    """可见文字中是否包含指定子串。"""
    def check() -> PredicateResult:
        state = resolve_state()
        for text in state.summary:
            if text_substring in text:
                return PredicateResult(
                    True,
                    evidence={"matched_text": text, "substring": text_substring},
                    confidence="medium",
                    message=f"found '{text_substring}' in summary",
                )
        return PredicateResult(
            False,
            evidence={"substring": text_substring, "summary_sample": state.summary[:5]},
            confidence="medium",
            message=f"'{text_substring}' not in summary",
        )
    return check
