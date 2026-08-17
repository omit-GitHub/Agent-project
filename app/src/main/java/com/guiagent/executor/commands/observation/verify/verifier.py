# -*- coding: utf-8 -*-
"""验证器核心 — verify() + verify_after_action()。

职责：
  - verify(predicate, timeout, poll_interval):
      反复调用 predicate() 直到返回 PredicateResult.verified=True 或超时
  - verify_after_action(action_fn, predicate, recover_fn, max_retries):
      执行 action → 验证 → 失败则 recover + 重试 → 返回完整结果

设计要点：
  - predicate 是 callable: () -> PredicateResult（允许内部刷新状态）
  - action_fn 是 callable: () -> dict（命令的实际执行逻辑）
  - recover_fn 是 callable: () -> dict（失败后的恢复动作）
  - 所有异常都被捕获并包装成结果 dict，不抛出

使用示例：
    from observation.verify import verify_after_action
    from observation.verify.predicates import playing_state_changed
    from observation.verify.recovery import re_reveal

    result = verify_after_action(
        action_fn=lambda: click_node_by_id("btn_pause"),
        predicate=playing_state_changed(expected=False),
        recover_fn=re_reveal(app="aiqiyi"),
        max_retries=1,
    )
"""
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from .predicates import PredicateResult


# ─────────────── 结果数据类 ───────────────

@dataclass
class VerificationResult:
    """verify() 的结果。"""
    verified: bool
    attempts: int = 0
    duration_ms: int = 0
    last_predicate_result: Optional[PredicateResult] = None
    timed_out: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "verified": self.verified,
            "attempts": self.attempts,
            "duration_ms": self.duration_ms,
            "timed_out": self.timed_out,
        }
        if self.last_predicate_result:
            d["evidence"] = self.last_predicate_result.evidence
            d["confidence"] = self.last_predicate_result.confidence
            d["message"] = self.last_predicate_result.message
        return d


@dataclass
class AfterActionResult:
    """verify_after_action() 的结果。"""
    ok: bool
    action_result: Optional[Dict[str, Any]] = None
    verification: Optional[VerificationResult] = None
    recovered: bool = False
    recovery_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "ok": self.ok,
            "recovered": self.recovered,
        }
        if self.action_result is not None:
            d["action_result"] = self.action_result
        if self.verification:
            d["verification"] = self.verification.to_dict()
        if self.recovery_result:
            d["recovery_result"] = self.recovery_result
        if self.error:
            d["error"] = self.error
        return d


# ─────────────── verify() ───────────────

def verify(
    predicate: Callable[[], PredicateResult],
    timeout_ms: int = 3000,
    poll_interval_ms: int = 300,
) -> VerificationResult:
    """反复调用 predicate 直到满足或超时。

    Args:
        predicate: callable 返回 PredicateResult
        timeout_ms: 总超时时间（毫秒）
        poll_interval_ms: 两次 poll 之间的等待

    Returns:
        VerificationResult
    """
    start = time.time()
    attempts = 0
    last_result = None

    deadline = start + timeout_ms / 1000.0

    while time.time() < deadline:
        attempts += 1
        try:
            last_result = predicate()
            if last_result.verified:
                elapsed_ms = int((time.time() - start) * 1000)
                return VerificationResult(
                    verified=True,
                    attempts=attempts,
                    duration_ms=elapsed_ms,
                    last_predicate_result=last_result,
                )
        except Exception as e:
            # 谓词本身抛错 — 记录并继续尝试
            last_result = PredicateResult(
                False,
                evidence={"predicate_exception": str(e)},
                confidence="low",
                message=f"predicate raised: {e}",
            )
            traceback.print_exc()

        # 等待下次 poll
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        time.sleep(min(poll_interval_ms / 1000.0, remaining))

    # 超时
    elapsed_ms = int((time.time() - start) * 1000)
    return VerificationResult(
        verified=False,
        attempts=attempts,
        duration_ms=elapsed_ms,
        last_predicate_result=last_result,
        timed_out=True,
    )


# ─────────────── verify_after_action() ───────────────

def verify_after_action(
    action_fn: Callable[[], Dict[str, Any]],
    predicate: Callable[[], PredicateResult],
    recover_fn: Optional[Callable[[], Dict[str, Any]]] = None,
    max_retries: int = 1,
    verify_timeout_ms: int = 3000,
    verify_poll_ms: int = 300,
) -> AfterActionResult:
    """执行动作 → 验证 → 失败则恢复+重试。

    流程:
      1. 执行 action_fn()，拿到 action_result
      2. 用 verify() 等待 predicate 满足
      3. 如果验证通过：返回 ok=True
      4. 否则：调 recover_fn() 恢复，再重试一次 action_fn + verify
      5. 重试仍失败：返回 ok=False，但保留所有 evidence

    Args:
        action_fn: 实际执行动作的 callable，返回 dict
        predicate: 验证谓词（工厂返回的 callable）
        recover_fn: 失败恢复 callable（可选）
        max_retries: 最大重试次数（默认 1）
        verify_timeout_ms: 每次验证的超时
        verify_poll_ms: 验证 poll 间隔

    Returns:
        AfterActionResult
    """
    # ── 第一次尝试 ──
    try:
        action_result = action_fn()
    except Exception as e:
        traceback.print_exc()
        return AfterActionResult(
            ok=False,
            action_result=None,
            error=f"action_fn raised: {e}",
        )

    verification = verify(predicate, timeout_ms=verify_timeout_ms,
                          poll_interval_ms=verify_poll_ms)
    if verification.verified:
        return AfterActionResult(
            ok=True,
            action_result=action_result,
            verification=verification,
            recovered=False,
        )

    # ── 没通过，尝试恢复 ──
    if max_retries <= 0 or recover_fn is None:
        return AfterActionResult(
            ok=False,
            action_result=action_result,
            verification=verification,
            recovered=False,
        )

    # 恢复
    recovery_result = None
    try:
        recovery_result = recover_fn()
    except Exception as e:
        traceback.print_exc()
        return AfterActionResult(
            ok=False,
            action_result=action_result,
            verification=verification,
            recovered=False,
            error=f"recover_fn raised: {e}",
        )

    # 重试 action + verify（剩余 retries 次）
    remaining_retries = max_retries - 1
    for attempt in range(1, max_retries + 1):
        try:
            retry_result = action_fn()
        except Exception as e:
            return AfterActionResult(
                ok=False,
                action_result=retry_result if 'retry_result' in dir() else action_result,
                verification=verification,
                recovered=True,
                recovery_result=recovery_result,
                error=f"retry action_fn raised on attempt {attempt}: {e}",
            )

        retry_verification = verify(predicate, timeout_ms=verify_timeout_ms,
                                    poll_interval_ms=verify_poll_ms)
        if retry_verification.verified:
            return AfterActionResult(
                ok=True,
                action_result=retry_result,
                verification=retry_verification,
                recovered=True,
                recovery_result=recovery_result,
            )

        # 这次没通过，更新 verification 继续
        verification = retry_verification
        action_result = retry_result

        # 如果还有重试机会，再恢复一次
        if attempt < max_retries and recover_fn is not None:
            try:
                recovery_result = recover_fn()
            except Exception as e:
                return AfterActionResult(
                    ok=False,
                    action_result=action_result,
                    verification=verification,
                    recovered=True,
                    recovery_result=recovery_result,
                    error=f"retry recover_fn raised: {e}",
                )

    # 所有重试都失败
    return AfterActionResult(
        ok=False,
        action_result=action_result,
        verification=verification,
        recovered=True,
        recovery_result=recovery_result,
    )
