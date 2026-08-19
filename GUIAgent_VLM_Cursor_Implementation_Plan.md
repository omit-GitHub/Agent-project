# GUIAgent VLM 主导通用操作框架：Cursor 实施任务书

> 目标：在现有 GUIAgent 项目中，将 VLM 作为主观测和单步动作选择器，构建"截图 → VLM 单步 JSON → Harness 校验 → Android 执行 → 截图验证"的通用闭环。UI dump/OCR 不得成为主路径依赖。

## 0. 已有架构与改造边界

### 0.1 现有代码资产（Phase 0-7 已完成）

当前项目已完成 v2 架构重构，以下模块已落地并经过测试：

```
commands/
├── observation/
│   ├── state/               # Phase 0: StateSnapshot + resolve_state()
│   │   ├── schema.py        #   StateSnapshot / PlayerState 数据类
│   │   ├── page_classifier.py
│   │   ├── player_state.py
│   │   ── resolver.py      #   resolve_state() 主入口
│   ├── reveal/              # Phase 2: Control Revealer（per-App 策略 + 三级检测）
│   │   ├── strategies.py
│   │   ├── detectors.py
│   │   └── revealer.py
│   ├── dpad/                # Phase 3: Focus-Aware DPAD Executor（4 级 API）
│   │   ├── executor.py
│   │   ├── focus_tracker.py
│   │   └── keymaps.py
│   ├── verify/              # Phase 4: Verification Framework（8 谓词 + 恢复策略）
│   │   ├── verifier.py
│   │   ├── predicates.py
│   │   └── recovery.py
│   ├── screen/              # Phase 6: 从 ocr/ 迁移的 observe_screen + click_element
│   ├── observation_cache.py
│   └── tests/               # 86 个单元测试全通过
├── aiqiyi/                  # Phase 5: 重构为 reveal→verify→click 模式
├── Tencent/                 # Phase 5: 同上
├── common/                  # 通用命令（get_state, go_back, volume 等）
├── registry.py              # 命令注册表（单线程 + 15s 超时 + 自动 attach 富状态）
├── server.py                # HTTP 服务 :8765
└── send.py                  # WebSocket 客户端 → :8322
```

此外 Agent 层已完成：
- `SYSTEM_PROMPT` 重写（3 类页面模型 + 状态感知 + 验证工作流）
- `COMMAND_DOCS` 新增 6 个命令文档
- `MAX_TOOL_CALLS` 5→10

**本次 VLM 集成不重写上述模块**，而是在 `observation/` 下新增子模块，并注册一个通用命令 `vlm_execute` 作为 Agent 的兜底工具。

### 0.2 本次改造范围

新增 3 个子模块到 `observation/`：

```
commands/observation/
├── vlm/                     # 新增：VLM Client + Prompt + Schema
│   ├── __init__.py
│   ├── client.py            #   QwenVlmClient（observe / verify）
│   ├── schemas.py           #   Pydantic 数据模型（NextAction / ObserveResult / VerifyResult）
│   ├── prompts.py           #   build_observe_prompt / build_verify_prompt
│   └── screenshot.py        #   capture_screenshot() 封装
── harness/                 # 新增：Action Guard + 执行循环 + Control Revealer VLM 版
│   ├── __init__.py
│   ├── action_guard.py      #   validate_action() 白名单 + bbox 校验
│   ├── action_loop.py       #   run_vlm_loop() 单步闭环
│   └── control_revealer.py  #   reveal_controls() VLM 感知版（复用 observation/reveal/ 降级）
└── memory/                  # Phase 2 新增：经验记忆
    ├── models.py
    ├── repository.py
    ├── matcher.py
    └── skill_extractor.py
```

同时在 `commands/common/` 下新增一个命令入口：
```
commands/common/
└── cmd_vlm_execute.py       # 注册为 vlm_execute，Agent 兜底调用
```

**保留全部现有模块**。现有 App 专属命令（`aiqiyi.*` / `tencent.*`）、dump/OCR 辅助、DPAD 执行器全部保留，作为降级路径和辅助验证信号。VLM 闭环在任何 dump/OCR 均为空的场景下必须仍可运行。

## 1. 实施原则

1. VLM 每次只选择 **一个** 原子动作，不能生成连续多步自然语言计划。
2. 所有动作必须经 Harness 白名单校验；VLM 不得直接下发 shell、HTTP、安装、系统设置或无限循环。
3. 每个动作执行后必须截图；只有 VLM Verify 认为成功才能返回成功。
4. 隐藏播放器控件先走 `reveal_controls` 状态转换，控件出现后再让 VLM 定位。
5. 初期不做自动长期记忆；先完成通用闭环，后再添加技能沉淀。
6. 所有 VLM 返回必须使用 JSON schema，并记录原始响应、截图路径、动作和验证结果，便于回放调试。

## 2. 配置

在 `agent/.env` 和命令服务配置中增加：

```dotenv
DASHSCOPE_API_KEY=
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
VLM_MODEL=qwen-vl-plus
VLM_ENABLE_THINKING=false
VLM_MAX_TOKENS=300
VLM_TIMEOUT_SECONDS=15
VLM_MAX_STEPS=6
VLM_MAX_OBSERVATIONS=3
VLM_SCREENSHOT_DIR=./runtime/screenshots
VLM_TRACE_DIR=./runtime/vlm_traces
VLM_MIN_BBOX_AREA=0.0003
VLM_MAX_BBOX_AREA=0.80
VLM_SENSITIVE_CONFIRM=true
```

要求：

- 使用 OpenAI 兼容客户端调用千问；
- 所有 API key 仅从环境变量读取，禁止硬编码；
- 默认 `enable_thinking=false`；
- 每次只上传当前单张截图，历史操作以文本摘要传入；
- VLM 返回失败、超时或 JSON 解析失败时，返回结构化错误，不触发坐标点击。

## 3. 数据模型

在 `commands/observation/vlm/schemas.py` 使用 Pydantic 定义并导出以下模型。

```python
class BBox(BaseModel):
    x1: float = Field(ge=0.0, le=1.0)
    y1: float = Field(ge=0.0, le=1.0)
    x2: float = Field(ge=0.0, le=1.0)
    y2: float = Field(ge=0.0, le=1.0)

class NextAction(BaseModel):
    type: Literal[
        "tap", "swipe", "type_text", "remote_key", "media_key",
        "wait", "back", "reveal_controls", "done", "ask_user"
    ]
    target_label: str | None = None
    bbox_normalized: BBox | None = None
    direction: Literal["up", "down", "left", "right"] | None = None
    distance: float | None = Field(default=None, ge=0.05, le=0.95)
    text: str | None = None
    key: str | None = None
    wait_ms: int | None = Field(default=None, ge=100, le=3000)

class ObserveResult(BaseModel):
    page_type: Literal["player", "detail", "search", "list", "grid", "dialog", "overlay", "unknown"]
    control_bar_visible: bool | None = None
    overlay: str | None = None
    task_status: Literal["in_progress", "done", "blocked", "unknown"]
    next_action: NextAction
    target_evidence: str
    confidence: float = Field(ge=0.0, le=1.0)

class VerifyResult(BaseModel):
    verification: Literal["success", "not_yet", "failed", "unknown"]
    reason: str
    observed_state: dict[str, Any] = Field(default_factory=dict)
```

额外定义：

```python
class ActionExecutionResult(BaseModel):
    ok: bool
    action: NextAction
    error_code: str | None = None
    detail: str | None = None

class VlmLoopResult(BaseModel):
    ok: bool
    status: Literal["success", "blocked", "failed", "timeout"]
    steps: list[dict[str, Any]]
    final_message: str
    verification: VerifyResult | None = None
```

## 4. VLM Prompt

在 `commands/observation/vlm/prompts.py` 固化两个 Prompt 函数：`build_observe_prompt` 与 `build_verify_prompt`。必须要求模型只返回 JSON，且使用 `response_format` / JSON schema（若 API 支持）或 Pydantic 严格解析重试。

### 4.1 Observe Prompt

```text
你是 Android 中屏 GUI 操作的视觉观察器。根据当前截图，为完成用户子目标选择唯一的下一步原子动作。

约束：
- 只能判断截图中可见的控件；看不到的控件不能猜位置。
- 若在播放器页面且控制条不可见、而目标需要设置/选集/倍速/清晰度，返回 reveal_controls。
- 若任务已完成，返回 done。
- 若存在登录、验证码、付款、删除、发送、订阅、退出登录、授权、密码输入等敏感操作，返回 ask_user。
- 仅从允许动作集合中选择。
- tap 时必须给出目标标签和 0~1 归一化 bbox；无法可靠定位时返回 ask_user 或 wait。
- 不要输出解释性文本，只输出符合 schema 的 JSON。

用户子目标：{subgoal}
已执行动作：{trajectory_summary}
允许动作：{allowed_actions}
```

### 4.2 Verify Prompt

```text
你是 GUI 操作验证器。比较用户目标、刚执行的动作和操作后截图，判断该动作是否实现了预期。

只返回 JSON：
- success：目标已达成；
- not_yet：动作有效但任务还未完成；
- failed：动作未产生预期结果或进入错误页面；
- unknown：截图不足以判断。

目标：{subgoal}
刚执行动作：{action}
预期结果：{expected}
```

## 5. 截图与 VLM Client

### 5.1 `screenshot.py`

复用 Android 侧已有 `global SCREENSHOT` 或等价截图原子操作，提供：

```python
def capture_screenshot() -> Screenshot:
    # 返回本地 PNG 路径、宽、高、sha256、captured_at
```

要求：

- 目录自动创建；
- 文件名包含时间戳和 request_id；
- 统一使用 PNG；
- 返回真实 `width` / `height`，供 bbox 坐标换算；
- 截图失败应抛出可捕获的 `ScreenshotError`。

### 5.2 `client.py`

提供：

```python
class QwenVlmClient:
    def observe(self, screenshot: Screenshot, subgoal: str, trajectory: list[dict]) -> ObserveResult: ...
    def verify(self, screenshot: Screenshot, subgoal: str, action: NextAction, expected: str) -> VerifyResult: ...
```

实现要求：

- 用 `qwen-vl-plus`（已验证可用），模型名由环境变量 `VLM_MODEL` 覆盖；
- `enable_thinking=false`；
- `max_tokens=300`；
- 记录 response id、usage、原始模型输出和解析错误；
- 先做一次 JSON 提取与 Pydantic 校验；失败可用"仅修复为合法 JSON，不改变含义"的文本重试一次；第二次失败则报 `VLM_INVALID_OUTPUT`；
- 不将图片加入多轮 API history。

## 6. Action Guard 与执行器

### 6.1 `action_guard.py`

实现：

```python
def validate_action(
    action: NextAction,
    screen_width: int,
    screen_height: int,
    subgoal: str,
) -> GuardDecision: ...
```

校验规则：

1. `tap` 必须同时有 `target_label` 和合法 bbox；
2. `x1 < x2`、`y1 < y2`，bbox 面积在 `VLM_MIN_BBOX_AREA` 和 `VLM_MAX_BBOX_AREA` 之间；
3. 点击坐标取 bbox 中心，加入 2% 屏幕内边距；
4. 敏感词或敏感页面状态直接返回 `NEEDS_USER_CONFIRMATION`；
5. 不以 VLM `confidence` 作为唯一点击依据；只作日志与后续回归统计；
6. 不支持的 key、方向、动作类型直接拒绝；
7. `type_text` 仅允许在 Agent 已明确取得输入文本且不含密码/验证码场景时执行。

### 6.2 执行器

将白名单动作映射到现有 `common/utils.py`：

```python
tap_normalized → tap(x, y)
swipe → swipe(...)
remote_key → remote_key(...)
media_key → remote_key(...) 或已有媒体键封装
type_text → set_text_by_id / set_text_fallback
back → global_action("BACK")
wait → wait
reveal_controls → control_revealer.reveal_controls(...)  # 复用 observation/reveal/
```

执行器只返回执行层成功与否，绝不自行宣称用户目标完成。

## 7. Control Revealer

在 `harness/control_revealer.py` 实现：

```python
def reveal_controls(
    *,
    app_package: str | None,
    max_steps: int = 3,
    subgoal: str,
) -> ActionExecutionResult:
    ...
```

初始策略按顺序执行：

```python
GENERIC_REVEAL_STEPS = [
    {"type": "tap", "x": 0.50, "y": 0.50, "wait_ms": 700},
    {"type": "remote_key", "key": "DPAD_CENTER", "wait_ms": 700},
    {"type": "remote_key", "key": "MENU", "wait_ms": 900},
]
```

每步后截图并用一个轻量 VLM 观察判断 `control_bar_visible`。任一步成功立即返回；全部失败返回 `CONTROL_BAR_NOT_REVEALED`。后续将成功率写进 per-App 策略表，但 Phase 1 先用通用序列即可。

## 8. 通用 Action Loop

在 `harness/action_loop.py` 实现：

```python
def run_vlm_loop(
    *,
    subgoal: str,
    expected: str,
    initial_context: dict[str, Any] | None = None,
) -> VlmLoopResult:
    ...
```

伪代码：

```python
trajectory = []
for step_idx in range(MAX_STEPS):
    before = capture_screenshot()
    observe = vlm.observe(before, subgoal, trajectory)

    if observe.task_status == "done" or observe.next_action.type == "done":
        verify = vlm.verify(before, subgoal, observe.next_action, expected)
        return success only if verify.verification == "success"

    if observe.next_action.type == "ask_user":
        return blocked

    decision = validate_action(observe.next_action, before.width, before.height, subgoal)
    if not decision.allowed:
        return blocked or failed

    executed = execute_action(decision.action)
    after = capture_screenshot()

    verify = vlm.verify(after, subgoal, decision.action, expected)
    append screenshot/action/observe/verify to trajectory and trace

    if verify.verification == "success":
        return success
    if verify.verification == "failed":
        attempt one bounded recovery; otherwise return failed

return timeout
```

注意：

- `done` 不能跳过验证；
- `unknown` 仅允许一次重新观察；
- `failed` 不得无限重试；
- 所有步骤必须写 trace JSONL；
- 任何异常应释放当前请求的执行锁。

## 9. 暴露命令给 Agent

在 `common/cmd_vlm_execute.py` 新增 `run(params)`：

```python
def run(params: dict) -> dict:
    # params:
    #   goal: 用户目标的简短描述，必填
    #   expected: 可观察成功条件，必填
    #   app_hint: 可选 App 包名/名称
    return run_vlm_loop(
        subgoal=params["goal"],
        expected=params["expected"],
        initial_context={"app_hint": params.get("app_hint")},
    ).model_dump()
```

在 `server.py` 的 `register_all_commands()` 注册命令：

```text
common.vlm_execute
```

在 `agent/commands.py` 增加工具说明：

```text
当当前 App 没有匹配专属命令、专属命令失败，或需要操作可见但无 UI 节点的界面时，调用 common.vlm_execute。
params.goal 只描述一个可验证子目标，例如"打开播放器倍速面板""点击1.5x倍速选项"。
params.expected 必须是可在截图中验证的条件，例如"倍率面板中1.5x处于选中状态"。
禁止将完整长任务一次交给 common.vlm_execute；先由 Agent 拆成子目标。
```

初版可让 Agent 对"打开/搜索/进入详情/设置倍速"拆分调用；后续再由 Planner 自动拆分。

## 10. 控制策略优先级（与现有系统协同）

每个用户请求按下列优先级处理：

1. **系统语义动作**：播放、暂停、上一集、下一集、快进、后退、音量等，优先发媒体键或系统动作，不必打开控制条。
2. **高置信经验技能**：命中同 App、同页面状态和同意图参数的成功轨迹时，先检查前置条件，再回放。
3. **App 专属稳定技能**：例如 `tencent.set_speed`、`aiqiyi.select_episode`，使用已验证的唤出/进入面板路径。
4. **VLM 通用操作**：未知页面、可见自绘页面、App 变版或专属命令失败时，采用"截图→VLM单步动作→执行→验证"循环。
5. **安全退出**：探索预算耗尽或目标歧义时停止，并反馈当前页面与失败原因；不继续盲点。

**说明**：App 专属技能（第 3 级）本身是从通用探索沉淀出的高频加速路径，比 VLM 探索更快（0.2s vs 1-2s）且更可靠，因此优先级高于 VLM 通用操作。

## 11. Phase 1 测试

新增 `commands/observation/tests/test_vlm_schemas.py`、`commands/observation/tests/test_action_guard.py` 和 `commands/observation/tests/test_action_loop_mock.py`。

单元测试至少覆盖：

- 非法 bbox、越界 bbox、零面积 bbox 被拒绝；
- `tap` 缺少标签或 bbox 被拒绝；
- 不支持的动作被拒绝；
- `ask_user` 不触发 Executor；
- `done` 后仍会进入 Verify；
- `unknown` 不会无限循环；
- 第二次 `failed` 后停止；
- 轨迹文件包含 before/after 截图、观察结果、执行结果和验证结果。

真实设备冒烟测试：

```text
1. common.vlm_execute：播放页点击暂停/播放。
2. 控制条隐藏时，触发 reveal_controls 并确认控制条出现。
3. 设置 1.5x；截图验证选中态。
4. 点击下一集；验证标题或集数变化。
5. 搜索并打开指定内容；验证结果页/详情页出现。
```

每个用例至少连续跑 10 次，记录成功率、平均 VLM 调用数、平均步骤数、端到端时延和错误点击数。

## 12. Phase 2：经验记忆

Phase 1 稳定后再实现 `memory/`：

1. 首次任务成功后，写入包含 `app + page_signature + intent + params + trajectory + verification` 的 Shortcut；
2. 下次先做一次 VLM 前置检查；
3. 高置信 Shortcut 直接回放，只做最终 Verify；
4. 连续两次 Verify 失败将 Shortcut 标记 `stale`；
5. 不将付款、发送、删除、密码、验证码等任务写入 Shortcut。

初期存储用 `skills.jsonl`；所有读写加文件锁。后续可替换为 SQLite，不改变接口。

## 13. 完成定义

完成本任务后必须满足：

- 当 UI dump 与 OCR 均不可用时，可在真实中屏上完成上述 5 个冒烟用例；
- VLM 只产生单步建议，所有真实设备动作均经过 Harness；
- 不可逆操作会阻塞并请求用户确认；
- 每次任务有可回放 trace；
- 系统能明确区分"执行层成功"和"视觉验证成功"；
- 代码具备单元测试，且不破坏现有 App 专属命令链路。
