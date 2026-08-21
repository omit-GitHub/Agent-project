# Harness B1 — 可量化安全验证与受限恢复闭环

## Context

Harness 框架已实现基础三模块（ActionGuard / LayeredVerifier / ControlRevealer）+ action_loop，但存在多个关键缺陷，需要在不接入真实 VLM/ADB 的前提下补齐可量化安全验证与受限恢复闭环。

**核心问题**：
1. LayeredVerifier VLM fallback 从不触发（`_unknown_count` 跟踪 unknown，但 LocalVerifier 只返回 success/not_yet，永远不返回 unknown）
2. expected_package/activity 在 before 已满足时误判 success（缺状态转移验证）
3. ActionGuard 缺 CandidateMap 一致性校验、confidence/clickable 检查、结构化敏感决策
4. ControlRevealer 允许 raw action dict 绕过 Harness、成功条件依赖 candidate 数量 > 5 而非状态转移、状态机不完整
5. action_loop 无恢复机制、无预算控制、无结构化 trace

---

## 工作目录

`/c/Users/p30068177/AppData/Local/Temp/harness-backup/`

---

## 实施计划

### 阶段 1：修复 `src/harness/verifier.py`

#### 1a. LayeredVerifier fallback 修复

**根因**：`_unknown_count` 在 local 返回 `unknown` 时递增，但 `LocalVerifier` 只返回 `success` 或 `not_yet`，所以 `_unknown_count` 永远为 0，VLM fallback 死代码。

**修复方案**：
- 参数 `max_unknown_before_vlm` → `max_local_observations`（默认 3）
- 用 `_consecutive_not_yet` 计数器替换 `_unknown_count`
- local 返回 `not_yet` → `_consecutive_not_yet += 1`
- local 返回 `success`/`failed` → 重置为 0
- `_consecutive_not_yet >= max_local_observations` 且 VLM callable 存在 → 调 VLM
- VLM 返回 `unknown` → `_vlm_unknown_count += 1`，返回 `not_yet`（允许继续观察）
- `_vlm_unknown_count > _max_vlm_unknown`（默认 1）→ 返回 `unknown` 停止
- VLM 不可用 + 观测耗尽 → 返回 `unknown`
- `unknown` 不得视为 success

#### 1b. expected_package/activity 状态转移验证

**根因**：`after.package == expected_package` 不检查 before 是否已满足。

**修复**：
```
# expected_package: 要求 before.package ≠ expected_package AND after.package == expected_package
# expected_activity: 要求 before.activity ≠ expected_activity AND after.activity == expected_activity
```

#### 向后兼容

- 现有 test_smoke.py 的 expected_package 测试：before="com.a" → expected="com.b"，本身是状态转移，不受影响
- 现有 expected_activity 测试：before="A" → expected="B"，同理
- minimal_demo.py 不设 expected_package/activity，通过 target_role 验证，不受影响

---

### 阶段 2：完善 `src/harness/action_guard.py`

#### 2a. ActionGuardConfig 新增字段
```python
min_candidate_confidence: float = 0.5
min_clickable_likelihood: float = 0.3
allow_ocr_only_tap: bool = True
```

#### 2b. GuardDecision 新增 decision 字段
```python
decision: str = "allow"  # "allow" | "ask_user" | "reject"
```

#### 2c. CandidateMap 一致性校验（_validate_tap_candidate 开头）
```
cm.package vs state.package → CANDIDATE_MAP_PACKAGE_MISMATCH
cm.activity vs state.activity → CANDIDATE_MAP_ACTIVITY_MISMATCH
cm.width/height vs state.screen_size → CANDIDATE_MAP_SIZE_MISMATCH
```

#### 2d. tap_candidate confidence/clickable_likelihood 校验
```
candidate.confidence < min_candidate_confidence → LOW_CONFIDENCE, requires_refinement=True
candidate.clickable_likelihood < min_clickable_likelihood → LOW_CLICKABLE_LIKELIHOOD, requires_refinement=True
not allow_ocr_only_tap and source=="ocr" and not kind → OCR_ONLY_NOT_ALLOWED
```

#### 2e. tap_visual allow_tap_visual_fallback
```
not allow_tap_visual_fallback → TAP_VISUAL_NOT_ALLOWED, decision="reject"
无来源信息或低置信 → requires_refinement=True（但仍 allowed=True if allow_tap_visual_fallback）
```

#### 2f. 敏感操作结构化决策
```
risk_category in {"payment","delete"} → decision="reject"（绝不进 executor）
其他敏感（sensitive_hint/sensitive_category/action_semantics 含敏感词）→ decision="ask_user"
```

#### 校验顺序调整

1. action_type 白名单
2. ask_user / done
3. safe ops (wait/back/reveal_controls)
4. **CandidateMap 一致性**（新增）
5. tap_candidate: candidate 查找 → fingerprint → bbox → 失败重放 → **confidence/clickable**（新增）→ 敏感性（结构化 decision）
6. tap_visual: bbox → fingerprint → **allow_tap_visual_fallback**（新增）→ 敏感性
7. remote_key / media_key / type_text / swipe

---

### 阶段 3：重构 `src/harness/control_revealer.py`

#### 3a. 不允许 raw action dict 绕过

移除 `set_action_executor(executor)` 和旧的 `reveal(app, screenshot_provider, candidate_builder)`。

新 API：
```python
def reveal(self, app, executor, verifier, current_state, *,
           activity="", orientation="landscape",
           target_role=None, expected_ocr_tokens=None, max_steps=5) -> tuple
```

- `executor` 必须符合 `ActionExecutor` Protocol（execute(ActionSpec, UiState) → ActionResult）
- `verifier` 必须符合 `StateVerifier` Protocol（verify(before, after, action) → VerificationResult）
- 内部将策略 action dict 转换为 `ActionSpec`（tap → tap_visual, remote_key → remote_key）

#### 3b. 正确成功条件

不再用 `len(candidate_map.candidates) > 5`。成功后通过以下条件证明：
1. `control_bar_visible`: false → true
2. 目标候选角色出现（`after.selected_role == target_role`）
3. 指定 OCR token 出现（`expected_ocr_tokens ⊂ (after.ocr_tokens - before.ocr_tokens)`）

#### 3c. 策略按 app + activity_pattern + orientation 过滤

`get_active_strategies(app, activity, orientation)` 使用 fnmatch 匹配 activity_pattern。

#### 3d. RevealStrategyRecord 完整字段 + save/load

新增字段：`activity_pattern`、`orientation`、`version`、`history`（list）、`_recent_outcomes`（rolling window，max 5）。
_load/_save 序列化全部字段。

#### 3e. 状态机完善

- `active → probation`: consecutive_failures >= 2
- `probation → active`: rolling window 中最近 2 次均为 success
- `probation → stale`: consecutive_failures >= 3
- `active → stale`: consecutive_failures >= 3，或 rolling window 5 次中 >= 4 次 failure
- `record_infrastructure_failure()`: 不修改任何计数器，不写入 rolling window
- stale 后 register 新版本：`strategy_id += "_v{N}"`，旧版本保留 history

---

### 阶段 4：action_loop 受限恢复 — `src/harness/action_loop.py`

#### 4a. 新增参数
```python
max_steps: int = 8            # 总动作预算
max_decision_calls: int = 4   # 总决策调用预算
recovery_budget: int = 2      # 恢复次数预算
control_revealer = None       # 可选 ControlRevealer
```

#### 4b. 结构化 trace

每步写入 `trace` 列表：
```python
{
    "step": int,
    "action_type": str,
    "target": str,
    "guard_reason": str,
    "guard_allowed": bool,
    "guard_decision": str,        # "allow" | "ask_user" | "reject"
    "executor_ok": bool | None,
    "verification": str | None,   # "success" | "not_yet" | "failed" | "unknown"
    "verification_source": str | None,
    "recovery_count": int,
    "strategy_id": str | None,
}
```

#### 4c. 恢复逻辑

```
verifier failed → guard.record_failure → 排除 (fingerprint, candidate_id)
  → recovery_count < budget → recovery_count++ → 继续
  → 否则 → status="failed"

verifier unknown → recovery_count < budget → recovery_count++ → 继续
  → 否则 → status="unknown_exhausted"

guard blocked (非敏感) → recovery_count < budget → recovery_count++ → 继续
guard blocked (ask_user) → status="guard_ask_user"（不进 executor）
guard blocked (reject) → status="guard_reject"（不进 executor）

reveal_controls 动作 → 调 control_revealer.reveal()
  → 失败 → stale 策略必须走 generic reveal
  → recovery_count < budget → recovery_count++ → 继续
  → 否则 → status="reveal_failed"
```

#### 4d. 预算控制
```
decision_calls >= max_decision_calls → status="decision_budget_exhausted"
action_count >= max_steps → status="timeout"（已有）
```

#### 4e. ActionLoopResult 扩展（schemas.py）
```python
trace: list = field(default_factory=list)
recovery_count: int = 0
decision_calls: int = 0
action_count: int = 0
```

---

### 阶段 5：更新 `src/harness/__init__.py`

导出新增类型和字段。

### 阶段 6：扩展 `tests/mocks.py`

新增：
- `FakeStateObserver`：模拟 observe_current_state()，返回预设 state 序列
- `FakeScreenshotProvider` / `FakeCandidateBuilder`：用于 ControlRevealer 测试

### 阶段 7：三套独立测试

#### 7a. `tests/test_action_guard_injection.py`（≥ 50 条）

**5 类异常 + 正常放行**，通过 run_action_loop 验证被拒绝时 `executor_calls == 0`：

| 类别 | 条数 | 代表场景 |
|------|------|----------|
| 未知动作类型 | 5 | invalid/empty/numeric/long/spaces |
| 候选不可达 | 10 | missing_id/no_map/not_found/stale_fingerprint/page_mismatch/bbox 越界×4/previously_failed |
| 置信度不足 | 7 | low_confidence/low_clickable/both/ocr_only/ocr_disabled/edge_values |
| 敏感操作 | 14 | payment/delete/logout/password/send/submit/sensitive_hint/password_role/text_sensitive/visual_sensitive |
| CandidateMap 不一致 | 6 | package_mismatch/activity_mismatch/width_mismatch/height_mismatch/both/all_three |
| 正常放行 | 12 | tap_candidate/tap_visual/swipe/remote_key/media_key/type_text/wait/back/reveal/done/ask_user/visual_fallback |

**关键断言**：所有被拒绝样本的 `executor.calls` 长度为 0。

#### 7b. `tests/test_verifier_four_state.py`

| 场景 | 断言 |
|------|------|
| success: expected_package 转移 | verification=success |
| success: expected_activity 转移 | verification=success |
| success: control_bar false→true | verification=success |
| success: target_role match | verification=success |
| success: OCR token 出现 | verification=success |
| not_yet: 无目标信号 | verification=not_yet |
| not_yet: layout-only 变化 | verification=not_yet |
| failed: VLM 显式返回 failed | verification=failed |
| unknown: VLM 不可用 + 观测耗尽 | verification=unknown |
| fallback: consecutive not_yet → VLM 被调用 | VLM callable 被调用 |
| unknown 不得成功: action_loop 中 unknown → 不 ok=True | status ≠ "success" |
| VLM unknown 后允许有限重观察 | 第 1 次 unknown 返回 not_yet，第 2 次返回 unknown |
| expected_package 无转移 → 不 success | before.package == expected → not_yet |
| expected_activity 无转移 → 不 success | before.activity == expected → not_yet |

#### 7c. `tests/test_control_revealer_state_machine.py`

| 场景 | 断言 |
|------|------|
| active → probation | consecutive_failures=2 后 state=probation |
| probation → active | 连续 2 次 success 后 state=active |
| probation → stale | consecutive_failures=3 后 state=stale |
| active → stale (consecutive) | consecutive_failures=3 后 state=stale |
| active → stale (rolling window) | 5 次中 4 次 failure → state=stale |
| 基础设施失败不污染 | record_infrastructure_failure 后 success_rate/count 不变 |
| stale generic fallback | 无匹配策略时使用 default |
| 新版本保留历史 | stale 后 register 新版本，旧版本 history 非空 |
| 策略过滤 activity_pattern | fnmatch 匹配/不匹配 |
| 策略过滤 orientation | 匹配/不匹配 |
| 完整字段 save/load | JSON 序列化/反序列化所有字段 |
| reveal: control_bar_visible 成功 | 验证成功条件 |
| reveal: target_role 成功 | 验证成功条件 |
| reveal: OCR token 成功 | 验证成功条件 |
| reveal: 不允许 raw dict 绕过 | reveal() 签名不接受 action_executor callable |

---

### 阶段 8：metrics 汇总脚本 — `scripts/generate_metrics.py`

运行所有测试（unittest），解析输出，生成：
- `metrics.json`：总数/通过/失败/错误/按 suite 统计/关键安全断言
- `metrics.csv`：每行一个测试（suite, test, status, duration_ms）

**指标来自实际运行**，脚本执行时收集真实结果。

---

## 实施顺序

| 步骤 | 文件 | 改动类型 |
|------|------|----------|
| 1 | `src/harness/schemas.py` | 新增 ActionLoopResult 字段 |
| 2 | `src/harness/verifier.py` | 修复 fallback + 状态转移 |
| 3 | `src/harness/action_guard.py` | 新增配置/一致性/confidence/structured decision |
| 4 | `src/harness/control_revealer.py` | 重构注入/成功条件/状态机/save-load |
| 5 | `src/harness/action_loop.py` | 恢复/预算/trace/reveal 集成 |
| 6 | `src/harness/__init__.py` | 更新导出 |
| 7 | `tests/mocks.py` | 扩展 mock 基础设施 |
| 8 | `tests/test_action_guard_injection.py` | ≥ 50 条 |
| 9 | `tests/test_verifier_four_state.py` | 四态 + fallback |
| 10 | `tests/test_control_revealer_state_machine.py` | 状态机 |
| 11 | `scripts/generate_metrics.py` | 汇总脚本 |
| 12 | 运行测试 + 生成 metrics | 实际数据 |

---

## 验证方案

1. `python -m unittest discover -s tests -v` — 所有测试通过（含原有 test_smoke.py）
2. `python scripts/generate_metrics.py` — 生成 metrics.json + metrics.csv
3. 检查 metrics 中数字来自实际运行（非手工填写）
4. 被拒绝样本 `executor_calls == 0`（assertIn 测试）
5. `unknown` 从未导致 `ok=True`（verifier 测试）
6. `expected_package` 在 before 已满足时不返回 success（verifier 测试）
7. ControlRevealer 不接受 raw action dict（签名变更 + 测试）
8. stale 策略产生新版本，旧版本 history 保留（revealer 测试）
