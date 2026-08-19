# -*- coding: utf-8 -*-
"""VLM 执行命令 — Agent 兜底通用操作。

对应 Cursor 任务书 §9。
当没有匹配的专属命令、专属命令失败、或需要操作无 UI 节点的界面时，
Agent 调用此命令，由 VLM 主导完成单步闭环。
"""
import os
import sys

# 确保能找到上级模块
_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from common.utils import success_with_data, error  # noqa: E402
from observation.harness.action_loop import run_vlm_loop  # noqa: E402


CMD_NAME = "vlm_execute"


def run(params: dict | None = None) -> dict:
    """执行 VLM 主导的通用操作。

    Args:
        params: {
            "goal": "用户目标的简短描述",      # 必填
            "expected": "可观察成功条件",      # 必填
            "app_hint": "可选 App 包名/名称",  # 可选
        }

    Returns:
        dict: {"ok": true/false, "data": {...}} 或 {"ok": false, "error": {...}}
    """
    if not params:
        return error("BAD_PARAMS", "Missing params")

    goal = params.get("goal", "").strip()
    expected = params.get("expected", "").strip()

    if not goal:
        return error("BAD_PARAMS", "Missing required param: goal")
    if not expected:
        return error("BAD_PARAMS", "Missing required param: expected")

    # 调用 VLM Loop
    try:
        result = run_vlm_loop(
            subgoal=goal,
            expected=expected,
            initial_context={"app_hint": params.get("app_hint")},
            max_steps=int(params.get("max_steps", 6)),
            max_observations=int(params.get("max_observations", 3)),
        )
    except Exception as e:
        return error("EXECUTION_FAILED", f"VLM loop error: {e}")

    # 返回结果
    data = {
        "command": CMD_NAME,
        "goal": goal,
        "status": result.status,
        "final_message": result.final_message,
        "steps": len(result.steps),
    }

    if result.verification:
        data["verification"] = result.verification.model_dump()

    if result.ok:
        return success_with_data(CMD_NAME, data)
    else:
        # 失败时仍返回 data，但 ok=false
        return {
            "ok": False,
            "error": {
                "code": result.status.upper(),
                "message": result.final_message,
            },
            "data": data,
        }


if __name__ == "__main__":
    # CLI 测试
    import json
    test_params = {
        "goal": "描述当前屏幕状态",
        "expected": "返回当前页面的详细描述",
    }
    result = run(test_params)
    print(json.dumps(result, ensure_ascii=False, indent=2))
