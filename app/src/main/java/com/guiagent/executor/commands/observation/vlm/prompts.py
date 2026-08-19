# -*- coding: utf-8 -*-
"""VLM Prompt 模板 — 固定 Prompt 函数。

对应 Cursor 任务书 §4。
两个 Prompt：
  - build_observe_prompt(): 观察器，根据截图选单步动作
  - build_verify_prompt(): 验证器，判断动作是否达成预期
"""


# ─────────────── Observe Prompt ───────────────

OBSERVE_SYSTEM_PROMPT = """你是 Android 中屏 GUI 操作的视觉观察器。
根据当前截图，为完成用户子目标选择唯一的下一步原子动作。

**必须严格返回以下 JSON 格式，不要有任何其他文字：**

```json
{
  "page_type": "player 或 detail 或 search 或 list 或 grid 或 dialog 或 overlay 或 unknown",
  "control_bar_visible": true 或 false,
  "overlay": "speed_panel 或 quality_panel 或 episode_panel 或 null",
  "task_status": "in_progress 或 done 或 blocked 或 unknown",
  "next_action": {
    "type": "tap 或 swipe 或 remote_key 或 media_key 或 wait 或 back 或 reveal_controls 或 done 或 ask_user",
    "target_label": "目标按钮的文字标签，或 null",
    "bbox_normalized": {"x1": 0.0-1.0, "y1": 0.0-1.0, "x2": 0.0-1.0, "y2": 0.0-1.0} 或 null,
    "direction": "up 或 down 或 left 或 right" 或 null,
    "key": "按键名" 或 null,
    "wait_ms": 整数 或 null
  },
  "target_evidence": "你在截图中看到什么支持这个动作的文字或视觉证据",
  "confidence": 0.0 到 1.0 的数字
}
```

约束：
- 只能判断截图中可见的控件；看不到的控件不能猜位置。
- 若在播放器页面且控制条不可见、而目标需要设置/选集/倍速/清晰度，next_action.type 返回 "reveal_controls"。
- 若任务已完成，next_action.type 返回 "done"。
- 若存在登录、验证码、付款、删除、发送、订阅、退出登录、授权、密码输入等敏感操作，next_action.type 返回 "ask_user"。
- tap 时必须给出 target_label 和 bbox_normalized；无法可靠定位时返回 ask_user 或 wait。
- 不要输出解释性文本，只输出上述 JSON。"""

OBSERVE_USER_TEMPLATE = """用户子目标：{subgoal}
已执行动作：{trajectory_summary}
允许动作：{allowed_actions}"""


def build_observe_prompt(
    subgoal: str,
    trajectory: list[dict] | None = None,
    allowed_actions: list[str] | None = None,
) -> list[dict]:
    """构造 Observe 消息列表。

    Args:
        subgoal: 用户子目标（如"点击 1.5 倍速"）
        trajectory: 已执行动作列表（用于上下文）
        allowed_actions: 允许的动作类型列表

    Returns:
        [{"role": "system", "content": "..."}, {"role": "user", "content": [...]}]
    """
    trajectory = trajectory or []
    allowed_actions = allowed_actions or [
        "tap", "swipe", "remote_key", "media_key",
        "wait", "back", "reveal_controls", "done", "ask_user"
    ]

    trajectory_summary = "无" if not trajectory else "; ".join(
        f"[{i+1}] {t.get('action', {}).get('type', '?')}: {t.get('action', {}).get('target_label', '')}"
        for i, t in enumerate(trajectory[-5:])  # 只取最近 5 步
    )

    allowed_text = ", ".join(allowed_actions)

    return [
        {"role": "system", "content": OBSERVE_SYSTEM_PROMPT},
        {"role": "user", "content": OBSERVE_USER_TEMPLATE.format(
            subgoal=subgoal,
            trajectory_summary=trajectory_summary,
            allowed_actions=allowed_text,
        )},
    ]


# ─────────────── Verify Prompt ──────────────

VERIFY_SYSTEM_PROMPT = """你是 GUI 操作验证器。
比较用户目标、刚执行的动作和操作后截图，判断该动作是否实现了预期。

**必须严格返回以下 JSON 格式，不要有任何其他文字：**

```json
{
  "verification": "success 或 not_yet 或 failed 或 unknown",
  "reason": "简要说明为什么这样判断",
  "observed_state": {"字段": "值"}
}
```

- success：目标已达成
- not_yet：动作有效但任务还未完成
- failed：动作未产生预期结果或进入错误页面
- unknown：截图不足以判断"""

VERIFY_USER_TEMPLATE = """目标：{subgoal}
刚执行动作：{action}
预期结果：{expected}"""


def build_verify_prompt(
    subgoal: str,
    action: dict | None = None,
    expected: str = "",
) -> list[dict]:
    """构造 Verify 消息列表。

    Args:
        subgoal: 用户子目标
        action: 刚执行的动作（dict 或 str）
        expected: 预期结果描述

    Returns:
        [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
    """
    action_text = "无" if not action else (
        action if isinstance(action, str)
        else f"{action.get('type', '?')}: {action.get('target_label', '')}"
    )

    return [
        {"role": "system", "content": VERIFY_SYSTEM_PROMPT},
        {"role": "user", "content": VERIFY_USER_TEMPLATE.format(
            subgoal=subgoal,
            action=action_text,
            expected=expected,
        )},
    ]
