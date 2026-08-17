# -*- coding: utf-8 -*-
"""恢复策略 — 验证失败后如何恢复。

设计：
  - 恢复策略是 callable: () -> dict
  - 每个策略封装一个具体的恢复动作
  - 与 predicates 解耦：verifier 调用 recover_fn() 不关心具体是什么策略

内置策略：
  - re_reveal(app)          — 重新唤出控制条
  - retry_dpad_enter()      — 再按一次 ENTER（焦点丢失场景）
  - wait_and_retry(seconds) — 等待后重试（动画未完成场景）
  - noop()                  — 什么都不做（用于测试）
"""
import os
import sys
import time
from typing import Callable, Dict, Any, Optional

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


# ─────────────── 策略 1: 重新唤出控制条 ───────────────

def re_reveal(app: Optional[str] = None) -> Callable[[], Dict[str, Any]]:
    """重新唤出控制条。

    Args:
        app: "aiqiyi" | "tencent" | "quark" | None（自动检测）
    """
    def recover() -> Dict[str, Any]:
        from reveal import reveal_controls
        return reveal_controls(app=app)
    return recover


# ─────────────── 策略 2: 再按一次 DPAD ENTER ───────────────

def retry_dpad_enter() -> Callable[[], Dict[str, Any]]:
    """再按一次 DPAD ENTER（焦点丢失或点击未响应场景）。"""
    def recover() -> Dict[str, Any]:
        from dpad import dpad_confirm
        return dpad_confirm()
    return recover


# ─────────────── 策略 3: 等待后重试 ───────────────

def wait_and_retry(seconds: float = 1.0) -> Callable[[], Dict[str, Any]]:
    """等待 N 秒后让 verifier 自然重试。

    用于动画未完成、UI 渲染延迟等场景。
    """
    def recover() -> Dict[str, Any]:
        time.sleep(seconds)
        return {"ok": True, "data": {"waited_seconds": seconds}}
    return recover


# ─────────────── 策略 4: 无操作（测试用）───────────────

def noop() -> Callable[[], Dict[str, Any]]:
    """什么都不做。用于测试 recover_fn 接口。"""
    def recover() -> Dict[str, Any]:
        return {"ok": True, "data": {"noop": True}}
    return recover


# ─────────────── 策略组合器 ───────────────

def chain(*recover_fns: Callable[[], Dict[str, Any]]) -> Callable[[], Dict[str, Any]]:
    """按顺序执行多个恢复策略，任一失败即停止。

    用法：chain(re_reveal("aiqiyi"), wait_and_retry(0.5))
    """
    def recover() -> Dict[str, Any]:
        results = []
        for fn in recover_fns:
            try:
                r = fn()
                results.append(r)
                if not r.get("ok"):
                    break
            except Exception as e:
                results.append({"ok": False, "error": str(e)})
                break
        return {
            "ok": all(r.get("ok", False) for r in results),
            "data": {"chain_results": results},
        }
    return recover


# ─────────────── 预置策略映射（给命令层用）───────────────

# 命令类型 → 默认恢复策略
# 命令在调用 verify_after_action 时可以传 recovery_key 而不是具体 recover_fn
DEFAULT_RECOVERY_MAP = {
    "player_control": lambda app=None: re_reveal(app),
    "overlay_open": lambda app=None: re_reveal(app),
    "focus_lost": lambda: retry_dpad_enter(),
    "animation_pending": lambda: wait_and_retry(1.0),
}


def get_default_recovery(key: str, **kwargs) -> Optional[Callable[[], Dict[str, Any]]]:
    """按 recovery_key 取默认恢复策略。"""
    factory = DEFAULT_RECOVERY_MAP.get(key)
    if factory is None:
        return None
    return factory(**kwargs)
