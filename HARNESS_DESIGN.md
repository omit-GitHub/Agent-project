# Harness Framework 设计方案

> 原始版本来自 GUIAgent 项目的 `HARNESS_MINIMAL_INTERFACE_PLAN.md`，
> 后剥离为独立框架。本文档保留完整设计约束，供后续扩展参考。

## Context

让 Harness 三模块（Action Guard / Verifier / Control Revealer）在纯 Python 环境下独立 import / 独立测试，不依赖 VLM / ADB / OCR。本次仅交付"可 import + mock smoke tests"，后续再叠加异常注入测试、三态测试、真实设备接入。

用户确认的设计约束（v1 → v3 累计）：
1. `ActionResult` 显式携带 `after_state`，不依赖原地修改
2. `validate_action(action, state, subgoal, failed_candidate_keys, *, guard=None, config=None)`
3. 保留旧 `run_vlm_loop` / `run(params)` 作 deprecated 兼容入口
4. 本地 Verifier 只在明确目标信号下 success；单纯 layout/局部变化 → unknown/not_yet
5. `ActionSpec` 包含 `action_type / candidate_id / candidate_map_fingerprint / expected_screen_fingerprint / expected_package / expected_activity / target_role / bbox_px / sensitive_hint`
6. 仅交付"可 import + mock smoke tests"，不做后续测试扩展
7. `UiState`（生产级最小状态快照）放 `harness/schemas.py`；tests/ 下只构造 UiState 实例，不另定义 MockScreenState
8. `expected_screen_fingerprint` 只与 `state.fingerprint` 比较，**禁止**与 package 混用
9. `candidate_map_fingerprint` 与 `state.candidate_map.screen_version` 比较；UI fingerprint 与 `state.fingerprint` 比较；失败 key 用 `(state.fingerprint, candidate_id)`
10. `validate_action` 必须使用传入的 guard 实例
11. 敏感性判定优先来自候选显式字段（`risk_category` / `sensitive_category` / `action_semantics`），`sensitive_hint` 仅追加；明确敏感的候选无论 subgoal 如何都必须 ask_user 或 reject
12. `done` / `ask_user` 不是普通 safe action：`ask_user` → `needs_user_confirmation`；`done` 在未验证过 success 时 → `stopped_unverified`；ok=True 的唯一出口是 Verifier success
13. `run_action_loop` 状态更新：executor fail → 停止并记录；verifier failed → 停止并记录；verifier not_yet/unknown → `current_state = after_state` 继续；verifier success → 唯一成功出口；max_steps → timeout/budget_exhausted
14. smoke test 用 `expected_package` / `expected_activity` 测试"package 到达目标"，不用 `expected_screen_fingerprint`

## 已完成（v1 之前落地，需按 v3 修订）

| 文件 | 状态 |
|---|---|
| `observation/harness/action_guard.py` | 已追加 `InvalidBBoxError` / `ActionGuardConfig` / 旧版 `validate_action()` / `tap_to_pixel()` → 需按 v3 重写 `validate_action` 签名 |
| `observation/harness/__init__.py` | 已导出新符号 → 需补 `UiState` / `ActionSpec` / `ActionLoopResult` / `VerificationStatus` / `VerificationSource` |

v3 将替换已追加的 `validate_action` 签名；保留 `InvalidBBoxError` / `ActionGuardConfig` / `tap_to_pixel` / `ActionGuard` 类。

## 数据类型

### `observation/harness/schemas.py`（新建）

```python
@dataclass
class ActionSpec:
    action_type: str
    candidate_id: str | None = None
    candidate_map_fingerprint: str | None = None   # vs state.candidate_map.screen_version
    expected_screen_fingerprint: str | None = None # vs state.fingerprint
    expected_package: str | None = None            # vs state.package（Verifier 用）
    expected_activity: str | None = None           # vs state.activity（Verifier 用）
    target_role: str | None = None
    bbox_px: PixelBBox | None = None
    sensitive_hint: str | None = None              # 仅追加拦截信号
    key: str | None = None
    text: str | None = None
    direction: str | None = None
    distance: float | None = None
    wait_ms: int | None = None

@dataclass
class UiState:
    fingerprint: str
    package: str
    activity: str
    screen_size: tuple[int, int]
    candidate_map: CandidateMap | None
    control_bar_visible: bool
    ocr_tokens: set[str]
    selected_role: str | None = None

@dataclass
class ActionResult:
    ok: bool
    action: ActionSpec
    after_state: UiState                    # 显式携带（约束 #1）
    error_code: str | None = None
    detail: str | None = None

@dataclass
class ActionLoopResult:
    ok: bool
    status: str                             # success / blocked / failed / timeout / needs_user_confirmation / stopped_unverified
    steps: list[dict]
    final_message: str
    verification: VerificationResult | None = None
```

### `observation/candidates/schemas.py`（追加可选字段）

`UiCandidate` 新增（均 Optional，默认 None，向后兼容）：
```python
risk_category: Optional[str] = None        # "payment" / "delete" / "send" / "logout" / "password" / "authorization" / ...
sensitive_category: Optional[str] = None
action_semantics: Optional[str] = None
```

### Protocols（action_loop.py 内定义）

```python
class DecisionSource(Protocol):
    def next_action(self, state: UiState) -> ActionSpec: ...

class ActionExecutor(Protocol):
    def execute(self, action: ActionSpec, state: UiState) -> ActionResult: ...

class StateVerifier(Protocol):
    def verify(self, before: UiState, after: UiState, action: ActionSpec) -> VerificationResult: ...
```

## validate_action（v3 签名，约束 #2/#10）

```python
def validate_action(
    action: ActionSpec,
    state: UiState,
    subgoal: str,
    failed_candidate_keys: set[tuple[str, str]],  # (fingerprint, candidate_id)
    *,
    guard: ActionGuard | None = None,
    config: ActionGuardConfig | None = None,
) -> GuardDecision:
```

- `guard` 必须被使用；若为 None，内部创建默认 `ActionGuard()`；guard 用于敏感词扩展配置和状态查询
- `config` 为 None 时创建默认 `ActionGuardConfig()`

规则顺序：

1. **action_type 白名单**：不在白名单 → `UNKNOWN_ACTION`
2. **`ask_user`**：不在此函数内处理，由 run_action_loop 直接返回（约束 #12）
3. **`done`**：不在此函数内处理，由 run_action_loop 直接返回
4. **safe actions**（`wait` / `back` / `reveal_controls`）→ allow
5. **`tap_candidate`**：
   - 必须有 `candidate_id`，否则 `MISSING_CANDIDATE_ID`
   - `state.candidate_map` 必须非 None，否则 `NO_CANDIDATE_MAP`
   - 在 `state.candidate_map.candidates` 中查找 candidate，找不到 → `CANDIDATE_NOT_FOUND`
   - 若 `action.candidate_map_fingerprint` 提供，必须 == `state.candidate_map.screen_version`，否则 `FINGERPRINT_MISMATCH`
   - 若 `action.expected_screen_fingerprint` 提供，必须 == `state.fingerprint`，否则 `PAGE_MISMATCH`
   - candidate.bbox_px 必须在 `state.screen_size` 内，否则 `BBOX_OUT_OF_SCREEN`
   - `(state.fingerprint, action.candidate_id)` 在 `failed_candidate_keys` 中 → `PREVIOUSLY_FAILED`（约束 #9）
   - **敏感性判定**（约束 #11）：
     - 若 `candidate.risk_category` 在敏感集合 → `SENSITIVE_TARGET`
     - 若 `candidate.sensitive_category` 或 `candidate.action_semantics` 明确指示敏感动作 → `SENSITIVE_TARGET`
     - 若 `action.sensitive_hint` 提供 → `SENSITIVE_TARGET`（额外保守拦截）
     - **不**用 subgoal 关键词判定
6. **`tap_visual`**：bbox_px 必填 + 屏幕内 + 面积合理 + 敏感检查（用 sensitive_hint + target_role，不查 subgoal）
7. **`remote_key` / `media_key`**：key 必填且在允许列表
8. **`swipe`**：direction 必填且在 up/down/left/right
9. **`type_text`**：text 必填 + sensitive_hint 检查

旧 `ActionGuard.validate(...)` 保留作为兼容实现（被旧 `run_vlm_loop` 使用）；新 `validate_action` 不再调用它（独立实现，避免签名适配成本）。

## VerificationResult（约束 #4）

```python
class VerificationStatus(str, Enum):
    success = "success"
    not_yet = "not_yet"
    failed = "failed"
    unknown = "unknown"

class VerificationSource(str, Enum):
    local = "local"
    vlm = "vlm"

class VerificationResult(BaseModel):
    verification: VerificationStatus
    source: VerificationSource
    reason: str
    observed_state: dict[str, Any] = Field(default_factory=dict)
```

**Local Verifier 严格 success 条件**（其他全部 → not_yet/unknown）：
1. `action.expected_package` 提供且 `after.package == action.expected_package` → success（source=local）
2. `action.expected_activity` 提供且 `after.activity == action.expected_activity` 且 `after.package == before.package` → success
3. `before.control_bar_visible == False and after.control_bar_visible == True` → success
4. `action.target_role` 提供且 `after.selected_role == action.target_role`（两者均非 None）→ success
5. `action.target_role` 对应文字（约定：target_role 本身即目标 OCR token，或从 observed_state 提取）∈ `after.ocr_tokens - before.ocr_tokens` → success
6. **其他任何变化**（layout、非目标 OCR、局部图像）→ `verification=not_yet, source=local`；若本地完全无法判断 → `unknown`
7. `unknown` 累计超限 → VLM fallback；VLM 不可用 → `unknown`

**VLM Verifier**：接受可注入 callable；callable 不可用 → `verification=unknown, source=vlm`

**LayeredVerifier.verify(before, after, action)**：按上述顺序检查，命中即返回；都不命中返回 not_yet/unknown；最终兜底 VLM。

## run_action_loop（约束 #12/#13）

```python
def run_action_loop(
    decision_source: DecisionSource,
    executor: ActionExecutor,
    verifier: StateVerifier,
    *,
    initial_state: UiState,
    subgoal: str,
    guard: ActionGuard | None = None,
    config: ActionGuardConfig | None = None,
    max_steps: int = 8,
) -> ActionLoopResult:
    config = config or ActionGuardConfig()
    guard = guard or ActionGuard()
    current_state = initial_state
    steps = []
    last_verification = None

    for step_idx in range(max_steps):
        action = decision_source.next_action(current_state)
        before_state = current_state

        # 约束 #12：ask_user 不进 executor
        if action.action_type == "ask_user":
            return ActionLoopResult(ok=False, status="needs_user_confirmation",
                                    steps=steps, final_message="action asks for user input",
                                    verification=last_verification)

        # 约束 #12：done 不自动 ok
        if action.action_type == "done":
            if last_verification is not None and last_verification.verification == VerificationStatus.success:
                return ActionLoopResult(ok=True, status="success", steps=steps,
                                        final_message=last_verification.reason, verification=last_verification)
            return ActionLoopResult(ok=False, status="stopped_unverified", steps=steps,
                                    final_message="done without prior verified success",
                                    verification=last_verification)

        # Guard 校验
        decision = validate_action(action, current_state, subgoal,
                                    guard.failed_candidates,
                                    guard=guard, config=config)
        if not decision.allowed:
            return ActionLoopResult(ok=False, status="blocked", steps=steps,
                                    final_message=f"blocked: {decision.reason}",
                                    verification=last_verification)

        # 执行
        result = executor.execute(action, current_state)
        steps.append({"step": step_idx, "action": action.action_type,
                      "target": action.candidate_id or action.target_role,
                      "ok": result.ok, "detail": result.detail})

        # 约束 #13：executor fail → 记录失败并停止
        if not result.ok:
            if action.candidate_id:
                guard.record_failure(current_state.fingerprint, action.candidate_id)
            return ActionLoopResult(ok=False, status="failed", steps=steps,
                                    final_message=result.error_code or "execution failed")

        after_state = result.after_state
        verification = verifier.verify(before_state, after_state, action)
        last_verification = verification
        steps[-1]["verify"] = verification.verification.value

        # 约束 #13：verifier success → 唯一 ok=True 出口
        if verification.verification == VerificationStatus.success:
            return ActionLoopResult(ok=True, status="success", steps=steps,
                                    final_message=verification.reason, verification=verification)

        # 约束 #13：verifier failed → 记录并停止（本阶段不恢复）
        if verification.verification == VerificationStatus.failed:
            if action.candidate_id:
                guard.record_failure(current_state.fingerprint, action.candidate_id)
            return ActionLoopResult(ok=False, status="failed", steps=steps,
                                    final_message=verification.reason, verification=verification)

        # 约束 #13：not_yet / unknown → 状态推进继续
        current_state = after_state

    return ActionLoopResult(ok=False, status="timeout", steps=steps,
                            final_message=f"max_steps={max_steps} reached",
                            verification=last_verification)
```

### ActionGuard 扩展

`ActionGuard` 类新增：
- `failed_candidates: set[tuple[str, str]]` 改为公开属性（带 getter）
- `record_failure(fingerprint: str, candidate_id: str)` 接收 fingerprint（不是 screen_version）
- 旧 `record_failure(screen_version, candidate_id)` 标 deprecated 但仍可调用（兼容旧 run_vlm_loop）

## 保留 run_vlm_loop（约束 #3）

- 在 `action_loop.py` 中保留 `run_vlm_loop(...)` 与 `run(params)` 签名
- VLM / ADB / common.utils 的 import 改为 **lazy**（函数体内 `import`）
- 函数开头加 `warnings.warn("run_vlm_loop is deprecated; use run_action_loop", DeprecationWarning, stacklevel=2)`
- 修复 `from .control_revealer import reveal_controls`（该符号不存在）→ 改为 `from .control_revealer import ControlRevealer`，并在函数内实例化使用

## control_revealer.py（修复）

- 删除第一个 `RevealStrategyManager`（line 80–119 段），保留第二个含 `_load/_save` 的版本
- 简化 `record_success` 中的冗余判断：`if self.state == "probation" and self.consecutive_failures == 0:` → `if self.state == "probation":`

## Mock 基础设施（`observation/tests/harness_mocks.py`，新建）

- **`MockDecisionSource`**：接受预设 `list[ActionSpec]`，按顺序返回；耗尽后返回 `ActionSpec(action_type="done")`
- **`FakeExecutor`**：
  - 不执行真实操作
  - `calls: list[ActionSpec]` 记录所有调用
  - 接受 `state_transitions: dict[str, Callable[[UiState], UiState]]` 按 action_type 触发预设转移；或单一 `after_state` 静态返回
  - `execute(action, state)` 返回 `ActionResult(ok=True, action=action, after_state=<新构造的 UiState>)`，**显式构造新对象**（约束 #1）
- **`FakeVlmVerifier`**：按预设顺序返回 VerificationResult
- **`FakeClock`**（可选）：替换 time.sleep/time.time
- **`make_candidate_map(...)`**：快速构造 CandidateMap 测试桩
- **`make_state(...)`**：快速构造 UiState 测试桩

## Smoke Tests（`observation/tests/test_harness_smoke.py`，新建）

至少 6 个测试用例：

1. **`test_modules_import_cleanly`** — `action_guard / verifier / control_revealer / action_loop / schemas` 全部可 import
2. **`test_fake_executor_no_device`** — `FakeExecutor` 无设备环境下可实例化并记录调用；`result.after_state` 是新对象（`is not state`）
3. **`test_action_loop_tap_candidate_success`** — `MockDecisionSource([tap_candidate])` + `FakeExecutor(ok=True, after_state=...)` + `FakeVlmVerifier([success])` → `ActionLoopResult(ok=True, status="success")`
4. **`test_local_verifier_success_on_explicit_signals`** — 四种 success 路径（package 到达目标用 `expected_package` / control_bar false→true / selected_role 匹配 / 特定 OCR 出现）；并验证 layout 变化返回 not_yet/unknown
5. **`test_guard_rejection_blocks_executor`** — Guard 拒绝（candidate_id 不在 map / fingerprint 不匹配 / 失败重放）→ `FakeExecutor.calls` 长度为 0，`ActionLoopResult.status == "blocked"`
6. **`test_done_without_verification_is_unverified`** — 约束 #12：decision_source 直接返回 done 且无 prior success → `status="stopped_unverified"`；`ask_user` → `status="needs_user_confirmation"`

运行：
```bash
cd D:\GUIAPP-main\app\src\main\java\com\guiagent\executor\commands
python -m unittest observation.tests.test_harness_smoke -v
```

回归：
```bash
python -m unittest observation.tests.test_verify -v
```

## 关键文件清单

| 文件 | 修改类型 |
|---|---|
| `observation/harness/schemas.py` | **新建**：`ActionSpec` / `UiState` / `ActionResult` / `ActionLoopResult` |
| `observation/candidates/schemas.py` | 追加 UiCandidate 可选字段：`risk_category` / `sensitive_category` / `action_semantics` |
| `observation/harness/action_guard.py` | 替换已追加的 `validate_action` 签名；ActionGuard 暴露 `failed_candidates`；`record_failure(fingerprint, candidate_id)` |
| `observation/harness/verifier.py` | 重写：`VerificationStatus` / `VerificationSource` Enum；Pydantic `VerificationResult`；`LocalVerifier.verify(before, after, action)` 严格 success 条件；`VlmVerifier(callable)`；`LayeredVerifier` 串接 |
| `observation/harness/control_revealer.py` | 删除重复 RevealStrategyManager；简化 record_success |
| `observation/harness/action_loop.py` | 新增协议 + `run_action_loop`；旧 `run_vlm_loop`/`run` lazy imports + deprecation；修 reveal_controls import |
| `observation/harness/__init__.py` | 导出新符号：`ActionSpec` / `UiState` / `ActionResult` / `ActionLoopResult` / `VerificationStatus` / `VerificationSource` |
| `observation/tests/harness_mocks.py` | **新建**：mock 基础设施 |
| `observation/tests/test_harness_smoke.py` | **新建**：6 个 smoke 测试 |

## 复用既有资源

- `observation/candidates/schemas.py::CandidateMap / UiCandidate / PixelBBox` — UiState、ActionSpec 直接复用
- `action_guard.py::ActionGuard` 类 — 保留，扩展 `failed_candidates` 与 `record_failure(fingerprint, candidate_id)`
- `action_guard.py::ActionGuardConfig / InvalidBBoxError / tap_to_pixel` — 保留
- `vlm/schemas.py::NextAction` — **不**被 harness 新代码依赖；旧 `run_vlm_loop` 仍使用

## 不在本次范围

- Guard 五类异常注入测试（等用户确认）
- Control Revealer 三态状态机测试（等用户确认）
- 真实 VLM / ADB / OCR 接入
- 经验记忆 / 双通路候选
- `observation/verify/` 旧框架

## Verification

```bash
cd D:\GUIAPP-main\app\src\main\java\com\guiagent\executor\commands

# Smoke tests
python -m unittest observation.tests.test_harness_smoke -v

# 回归
python -m unittest observation.tests.test_verify -v

# Import 链
python -c "from observation.harness import action_guard, verifier, control_revealer, action_loop, schemas; print('ok')"
```

预期：
- Smoke tests 6/6 通过
- `test_verify` 无新增失败
- import 链输出 `ok`

## 最终交付物

1. 文件修改清单 + diff 摘要
2. 数据模型与接口签名（`ActionSpec` / `UiState` / `ActionResult` / `ActionLoopResult` / `VerificationResult` / 各 Protocol）
3. 运行命令
4. Smoke test 实际输出
5. **不会**继续实现 Guard 五类注入测试或 Revealer 三态测试 — 等用户确认
