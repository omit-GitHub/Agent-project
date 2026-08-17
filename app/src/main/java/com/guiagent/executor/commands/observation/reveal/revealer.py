# -*- coding: utf-8 -*-
"""Control Revealer — 播放器隐藏控件显式唤出器。

职责:
  给定当前 App 和上下文，按优先级尝试一系列唤出动作，
  每个动作后检测控制条是否出现；一旦成功立即停止并返回。

这是播放器场景的基础原子能力。不同于旧 ocr/cmd_reveal_controls.py
（只做一次硬编码 tap 中心），本模块：
  - per-App 动作序列（数据驱动）
  - 每步后检测（三级：容器 ID → 按钮 ID → OCR 文字）
  - 支持自定义 context（player / episode_panel / speed_panel）
  - 返回详细的尝试过程和最终状态

用法:
    from observation.reveal import reveal_controls
    result = reveal_controls(app="aiqiyi")
    if result["ok"] and result["data"]["revealed"]:
        # 控制条已出现，可以继续操作
        ...
"""
import os
import sys
import time
import traceback
from typing import Optional, Dict, Any, List

# 让本模块能找到 common / send
_HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from send import send                                            # noqa: E402
from common.utils import success_with_data, error               # noqa: E402

from .strategies import get_strategy                            # noqa: E402
from .detectors import detect_control_bar                       # noqa: E402


# ─────────────── App 名自动检测 ───────────────

# pkg → app 名 映射（来自 State Resolver 的 pkg 列表）
_PKG_TO_APP = {
    "com.qiyi.video.speaker": "aiqiyi",
    "com.qiyi.video": "aiqiyi",
    "com.qiyi.video.pad": "aiqiyi",
    "com.tencent.qqlive": "tencent",
    "com.tencent.qqlive.speaker": "tencent",
    " com.tencent.video": "tencent",
    "com.quark.browser": "quark",
}


def detect_app_from_pkg(pkg: str) -> Optional[str]:
    """根据包名推断 App 名。返回 None 表示未知。"""
    if not pkg:
        return None
    return _PKG_TO_APP.get(pkg)


def _get_current_pkg() -> str:
    """从 WS ping 拿当前前台包名。"""
    try:
        r = send({"id": "rv_ping", "op": "ping", "args": {}})
        if r.get("ok"):
            data = r.get("data", {})
            return data.get("package", "") or data.get("pkg", "")
    except Exception:
        pass
    return ""


# ─────────────── 主入口 ───────────────

def reveal_controls(
    app: Optional[str] = None,
    context: Optional[str] = None,
    max_steps: int = 4,
) -> Dict[str, Any]:
    """显式唤出播放器隐藏控件。

    Args:
        app: "aiqiyi" | "tencent" | "quark" | None（None 时从当前 pkg 推断）
        context: 可选提示（"player" / "episode_panel" / "speed_panel"）
                 当前实现暂不区分 context，保留扩展点
        max_steps: 最多尝试几个动作（防止死循环）

    Returns:
        success_with_data("reveal_controls", {
            "revealed": True/False,
            "app": "aiqiyi" | ...,
            "context": ...,
            "steps_tried": [{"action": ..., "desc": ..., "wait_ms": ..., "result": ...}, ...],
            "control_bar_visible": True/False,
            "detection": {"visible": ..., "confidence": ..., "method": ..., "evidence": ...},
            "method": "step_1" | "step_2" | ... | "already_visible" | "all_failed",
        })
        或 error(...)
    """
    try:
        return _do_reveal(app, context, max_steps)
    except Exception as e:
        traceback.print_exc()
        return error("REVEAL_FAILED", f"reveal_controls exception: {e}")


def _do_reveal(app, context, max_steps):
    """内部实现。"""
    steps_tried: List[Dict[str, Any]] = []

    # 1. 自动检测 app（如果未指定）
    if not app:
        pkg = _get_current_pkg()
        app = detect_app_from_pkg(pkg) or "_default"

    # 2. 预先检测：可能控制条已经可见了
    pre_detection = detect_control_bar(run_ocr_if_needed=False)
    if pre_detection["visible"]:
        return success_with_data("reveal_controls", {
            "revealed": True,
            "app": app if app != "_default" else None,
            "context": context,
            "steps_tried": [],
            "control_bar_visible": True,
            "detection": pre_detection,
            "method": "already_visible",
        })

    # 3. 取策略
    strategy = get_strategy(app)
    if not strategy:
        return error("NO_STRATEGY", f"No reveal strategy for app: {app}")

    # 4. 依次尝试每个动作
    for i, step in enumerate(strategy[:max_steps]):
        step_record = {
            "step": i + 1,
            "action": step.get("action"),
            "desc": step.get("desc", ""),
            "wait_ms": step.get("wait_ms", 500),
        }

        # 执行动作
        action_result = _execute_action(step)
        step_record["result"] = action_result

        # 等待动画
        wait_ms = step.get("wait_ms", 500)
        if wait_ms > 0:
            time.sleep(wait_ms / 1000.0)

        # 检测（第一次用轻量检测，最后一次用带 OCR 的完整检测）
        is_last = (i == len(strategy[:max_steps]) - 1)
        detection = detect_control_bar(run_ocr_if_needed=is_last)
        step_record["detection"] = detection

        steps_tried.append(step_record)

        if detection["visible"]:
            return success_with_data("reveal_controls", {
                "revealed": True,
                "app": app if app != "_default" else None,
                "context": context,
                "steps_tried": steps_tried,
                "control_bar_visible": True,
                "detection": detection,
                "method": f"step_{i + 1}",
            })

    # 5. 所有步骤都失败
    return success_with_data("reveal_controls", {
        "revealed": False,
        "app": app if app != "_default" else None,
        "context": context,
        "steps_tried": steps_tried,
        "control_bar_visible": False,
        "detection": steps_tried[-1]["detection"] if steps_tried else {"visible": False},
        "method": "all_failed",
    })


# ─────────────── 动作执行 ───────────────

def _execute_action(step: Dict[str, Any]) -> Dict[str, Any]:
    """执行单个唤出动作。返回 WS 响应 dict。"""
    action = step.get("action")
    args = step.get("args", {})

    if action == "tap":
        return send({
            "id": f"rv_tap_{id(step)}",
            "op": "tap",
            "args": {"x": int(args.get("x", 640)), "y": int(args.get("y", 400))},
        })

    if action == "remote_key":
        return send({
            "id": f"rv_key_{id(step)}",
            "op": "remote_key",
            "args": {"key": args.get("key", "ENTER")},
        })

    if action == "swipe":
        return send({
            "id": f"rv_swipe_{id(step)}",
            "op": "swipe",
            "args": {
                "x1": int(args.get("x1", 0)),
                "y1": int(args.get("y1", 0)),
                "x2": int(args.get("x2", 0)),
                "y2": int(args.get("y2", 0)),
                "duration": int(args.get("duration", 300)),
            },
        })

    if action == "wait":
        ms = int(args.get("ms", 500))
        time.sleep(ms / 1000.0)
        return {"ok": True, "data": {"waited_ms": ms}}

    return {"ok": False, "err": {"code": "UNKNOWN_ACTION", "msg": action}}


# ─────────────── 命令封装（给 registry 注册用）───────────────

def run(params=None):
    """命令入口（被 registry 调用）。

    params: {"app": "aiqiyi", "context": "player", "max_steps": 4}
    """
    params = params or {}
    return reveal_controls(
        app=params.get("app"),
        context=params.get("context"),
        max_steps=int(params.get("max_steps", 4)),
    )
