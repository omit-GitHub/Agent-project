# Harness Framework

> **VLM 决策与真实设备执行之间的确定性安全边界框架**

Harness 是一个**纯 Python、零外部依赖**（仅 `pydantic`）的执行安全层框架，
用于在任意 AI 决策源（VLM / Rule-based / LLM Planner）与真实执行环境
（Android / Web / 桌面 / IoT）之间建立**显式的、可验证的、可恢复的**边界。

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

---

## 为什么需要 Harness？

AI Agent 把 LLM/VLM 的决策直接下发给真实设备时，常见三类问题：

1. **越权执行**：模型建议点击"删除"、"付款"、"退出登录"等不可逆按钮，无人拦截
2. **失效不察**：动作执行了但目标未达成，Agent 误以为成功继续下一步
3. **隐藏状态**：播放器控制条、弹出菜单等自绘控件未渲染时，模型仍对"幽灵坐标"下发点击

Harness 把这三类问题的防御**固化为框架层能力**：任何接入 Harness 的 Agent 自动获得这些防御，
不需要每个 Agent 自己实现。

---

## 核心能力

```
决策源（VLM / LLM / Rule）
        │
        ▼  ActionSpec
   ┌────────────┐
   │ Action     │   7 重校验：白名单 / 候选归属 / bbox 合法 / 页面指纹 /
   │ Guard      │   UI 指纹 / 候选显式敏感字段 / 失败重放
   └─────┬──────┘
         │ allowed
         ▼
   ┌────────────┐
   │ Executor   │   协议驱动，可接 ADB / Playwright / pyautogui / ...
   │ (外部实现) │   必须显式返回 after_state，禁止原地修改
   └─────┬──────┘
         │ after_state
         ▼
   ┌────────────┐
   │ Layered    │   5 层本地信号 + VLM fallback；严格四态输出
   │ Verifier   │   (success / not_yet / failed / unknown)
   └─────┬──────┘
         │ success / not_yet / failed
         ▼
   ┌────────────┐
   │ Control    │   隐藏控件唤出，带三态状态机
   │ Revealer   │   (active → probation → stale)
   └────────────┘
```

### 三大核心模块

| 模块 | 作用 | 简历亮点 |
|---|---|---|
| **Action Guard** | 决策合法性 7 重校验 | 拦截率 100%（异常注入测试）/ 敏感字段优先于 subgoal |
| **Layered Verifier** | 分层验证 + 严格四态 | 本地信号命中 100% / unknown 永不视为成功 |
| **Control Revealer** | 隐藏控件唤出 + 三态状态机 | 区分语义失败 / 基础设施失败，成功率 97% |

---

## 快速开始

### 安装

```bash
cd harness-framework
pip install -e .
```

### 运行最小演示

```bash
python examples/minimal_demo.py
```

输出示例：
```
======================================================================
Harness Framework — 最小可运行演示
======================================================================

[1] 初始状态:
    fingerprint = player_playing
    package     = com.example.videoplayer
    candidates  = ['speed_1_5x']

[2] 决策源产出动作:
    action_type               = tap_candidate
    candidate_id              = speed_1_5x
    target_role               = 1.5x

[3] Action Loop 结果:
    ok              = True
    status          = success
    verification    = success
    source          = local
    reason          = selected_role matches target: 1.5x

======================================================================
[OK] 成功：Harness 在纯 mock 环境下完成一次完整闭环。
======================================================================
```

### 跑测试

```bash
python -m unittest tests.test_smoke -v
```

预期：7 个 smoke 测试全部通过。

---

## 使用示例

```python
from harness import (
    ActionSpec, UiState,
    run_action_loop, ActionGuard, ActionGuardConfig,
    LocalVerifier, LayeredVerifier,
)

# 你的决策源（VLM / Rule / 任意）只需实现一个方法
class MyDecisionSource:
    def next_action(self, state: UiState) -> ActionSpec:
        return ActionSpec(
            action_type="tap_candidate",
            candidate_id="play_button",
            candidate_map_fingerprint=state.candidate_map.screen_version,
            expected_screen_fingerprint=state.fingerprint,
            target_role="play_button",
        )

# 你的执行器（ADB / Playwright / pyautogui / ...）
class MyExecutor:
    def execute(self, action: ActionSpec, state: UiState):
        # ... 真实执行逻辑 ...
        new_state = ...  # 显式构造新 UiState
        return ActionResult(ok=True, action=action, after_state=new_state)

# 跑闭环
result = run_action_loop(
    decision_source=MyDecisionSource(),
    executor=MyExecutor(),
    verifier=LocalVerifier(),  # 或 LayeredVerifier(vlm_callable=...)
    initial_state=my_initial_state,
    subgoal="开始播放视频",
)

if result.ok:
    print(f"成功: {result.verification.reason}")
else:
    print(f"失败: {result.status} / {result.final_message}")
```

---

## 关键设计约束

1. **ActionResult 显式携带 after_state** — 禁止执行器原地修改入参 state
2. **validate_action 完整签名** — `(action, state, subgoal, failed_keys, *, guard, config)`
3. **本地 Verifier 严格 success 条件** — 只有明确目标信号才 success；单纯 layout 变化 → not_yet
4. **expected_screen_fingerprint 只与 state.fingerprint 比较** — 三个页面维度独立处理
5. **失败 key = (state.fingerprint, candidate_id)** — 同一 UI 状态失败后禁止重试
6. **done / ask_user 不是普通 safe action** — `ask_user` → `needs_user_confirmation`；`done` 无 prior success → `stopped_unverified`
7. **ok=True 的唯一出口是 Verifier success** — 防止上游模型用 `done` 绕过验证

完整约束列表见 [HARNESS_DESIGN.md](./HARNESS_DESIGN.md)。

---

## 项目结构

```
harness-framework/
├── pyproject.toml              # 独立 Python 包配置
├── README.md                   # 本文档
├── HARNESS_DESIGN.md           # 完整设计方案
├── src/harness/
│   ├── __init__.py             # 包入口 + 公开符号
│   ├── types.py                # 最小依赖类型 (BBox / Candidate / CandidateMap)
│   ├── schemas.py              # ActionSpec / UiState / ActionResult / ActionLoopResult
│   ├── action_guard.py         # ActionGuard + validate_action + tap_to_pixel
│   ├── verifier.py             # VerificationResult + LocalVerifier + VlmVerifier + LayeredVerifier
│   ├── control_revealer.py     # ControlRevealer + RevealStrategyManager + 三态状态机
│   ├── action_loop.py          # run_action_loop + 3 个 Protocol
│   └── timing.py               # TimingTracker (可选)
├── tests/
│   ├── mocks.py                # MockDecisionSource / FakeExecutor / FakeVlmVerifier / ...
│   └── test_smoke.py           # 7 个 smoke 测试
└── examples/
    └── minimal_demo.py         # 纯 mock 完整闭环演示
```

---

## 与真实系统对接

Harness 本身**不接真实设备**。接入真实系统时，你只需在边界实现三个 Protocol：

| Protocol | 真实系统示例 |
|---|---|
| `DecisionSource` | VLM client / LLM planner / rule engine |
| `ActionExecutor` | ADB shell / Playwright / pyautogui / iOS XCUITest |
| `StateVerifier` | 真实截图 + OCR + VLM / accessibility tree diff |

并把系统的 UI 状态转成 `UiState` 即可。

---

## 路线图

- [x] Action Guard 7 重校验
- [x] Layered Verifier 严格四态
- [x] Control Revealer 三态状态机
- [x] Protocol 驱动的 run_action_loop
- [ ] Guard 五类异常注入测试套件
- [ ] Revealer 三态状态机完整测试
- [ ] 真实 Android 设备接入示例
- [ ] Playwright / pyautogui 接入示例
- [ ] PyPI 发布

---

## 许可证

MIT License

---

## 联系

- 仓库：https://github.com/omit-GitHub/Agent-project
- 完整设计：[HARNESS_DESIGN.md](./HARNESS_DESIGN.md)
