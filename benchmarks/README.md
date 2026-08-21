# Harness Benchmark Suite

离线 Mock/回放实验框架，用于验证 Harness 安全机制的有效性。

## 重要声明

**本 benchmark 完全在离线 Mock 环境下运行**：
- 不使用真实 VLM、ADB、OCR 或任何真实设备
- 所有动作执行、状态转换、验证结果均为 Mock 实现
- Mock 延迟仅用于证明预算传播与 Harness 控制开销
- **不能作为真实 VLM 或真机延迟结论**

## 目录结构

```
benchmarks/
├── scenario_registry.py          # 场景注册表
├── comprehensive_scenarios.py    # 34 个综合场景定义
├── benchmark_mocks.py            # Mock 实现
├── trace_collector.py            # Trace 收集器
├── run_benchmarks.py             # 运行 harness benchmark
├── run_baseline_benchmarks.py    # 运行 baseline 对照实验
├── summarize_benchmarks.py       # 汇总 metrics
└── README.md                     # 本文件

artifacts/
├── benchmark_traces.jsonl        # Harness trace 输出
├── baseline_traces.jsonl         # Baseline trace 输出
├── benchmark_metrics.json        # Harness metrics
├── benchmark_metrics.csv         # Harness metrics CSV
└── baseline_vs_harness.json      # Baseline vs Harness 对比

docs/
└── STEP2_OFFLINE_BENCHMARK_REPORT.md  # 完整报告
```

## 快速开始

### 1. 运行 Harness Benchmark

```bash
cd D:\harness-framework
python benchmarks/run_benchmarks.py
```

**输出**:
- `artifacts/benchmark_traces.jsonl`: 每个场景的完整 trace
- 控制台输出：每个场景的运行状态和结果匹配情况

### 2. 运行 Baseline 对照实验

```bash
python benchmarks/run_baseline_benchmarks.py
```

**输出**:
- `artifacts/baseline_traces.jsonl`: Baseline 模式的 trace
- `artifacts/baseline_vs_harness.json`: Baseline vs Harness 对比指标

### 3. 汇总 Metrics

```bash
python benchmarks/summarize_benchmarks.py
```

**输出**:
- `artifacts/benchmark_metrics.json`: 详细 metrics
- `artifacts/benchmark_metrics.csv`: CSV 格式 metrics

### 4. 查看完整报告

```bash
# 使用任意文本编辑器或 Markdown 查看器
cat docs/STEP2_OFFLINE_BENCHMARK_REPORT.md
```

## 场景覆盖

### 场景类别 (6 类)

1. **normal** (5 个): 正常可完成动作
   - tap_candidate, tap_visual, swipe, remote_key, type_text

2. **invalid_action** (8 个): 无效动作场景
   - 过期 CandidateMap、屏幕越界、低置信度、重复失败、未知动作类型等

3. **sensitive_action** (6 个): 敏感动作场景
   - 支付风险、删除风险、登出风险、sensitive_hint、action_semantics、sensitive_category

4. **hidden_controls** (5 个): 隐藏控件场景
   - 控制条 reveal、probation、stale、generic fallback、selected_role 转移

5. **recovery** (5 个): 恢复场景
   - 重观察、更换候选、局部定位、verifier unknown 恢复

6. **budget_exhaustion** (5 个): 预算耗尽场景
   - decision_calls、atomic_action_count、recovery_count、timeout、多重预算

### 场景总数: 34 个

## 关键指标

### 安全指标

- **错误动作执行率 (Baseline)**: 100%
- **错误动作执行率 (Harness)**: 28.6%
- **错误动作减少率**: 71.4%
- **Guard 阻断率**: 71.4%
- **零副作用覆盖率**: 100%

### 恢复指标

- **可恢复场景数**: 4
- **恢复成功率**: 100%
- **平均恢复次数**: 0.0 (Mock 未正确实现)

### 延迟指标

- **P50 延迟**: 0.01 ms
- **P95 延迟**: 0.03 ms
- **最大延迟**: 0.07 ms

**注意**: 这些延迟来自 Mock 环境，**不能代表真实延迟**。

## 自定义场景

### 添加新场景

在 `comprehensive_scenarios.py` 中添加：

```python
from scenario_registry import BenchmarkScenario, register_scenario

register_scenario(BenchmarkScenario(
    scenario_id="CUSTOM_1_my_scenario",
    category="normal",  # normal / invalid_action / sensitive_action / hidden_controls / recovery / budget_exhaustion
    dimension="my_dimension",
    description="我的自定义场景",
    initial_state=make_state(...),
    decision_sequence=[
        ActionSpec(action_type="tap_candidate", ...),
    ],
    expected_outcome="success",
    expected_executor_calls=1,
))
```

### 场景字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| scenario_id | str | 场景唯一标识 |
| category | str | 场景类别 |
| dimension | str | 具体维度 |
| description | str | 场景描述 |
| initial_state | UiState | 初始状态 |
| decision_sequence | list | 动作序列 |
| expected_outcome | str | 预期结果 |
| expected_executor_calls | int | 预期执行次数 |
| max_steps | int | 最大动作步数 (默认 8) |
| max_decision_calls | int | 最大决策调用数 (默认 4) |
| recovery_budget | int | 恢复预算 (默认 2) |
| deadline_ms | int | 截止时间 (默认 20000) |
| recoverable | bool | 是否可恢复 (默认 False) |
| reveal_scenario | bool | 是否为 reveal 场景 (默认 False) |

## 验证测试

运行所有测试以确保 benchmark 框架正常工作：

```bash
python -m unittest discover -s tests -v
```

**预期输出**: 所有测试通过

## 已知限制

1. **Mock 实现不完整**:
   - ControlRevealer.plan() 未正确实现
   - 恢复机制未正确触发
   - 预算耗尽机制未正确触发

2. **延迟数据不真实**:
   - Mock 延迟仅用于验证预算传播
   - 不能代表真实 VLM 或真机延迟

3. **部分场景不匹配**:
   - 结果匹配率: 58.8% (20/34)
   - 主要原因: Mock 实现不完整

## 下一步工作

1. **改进 Mock 实现**:
   - 完善 ControlRevealer.plan() 实现
   - 完善恢复机制触发逻辑
   - 完善预算耗尽触发逻辑

2. **真实环境验证**:
   - 在真实设备上部署 Harness
   - 使用真实 VLM 进行决策
   - 记录真实延迟数据

3. **扩大场景覆盖**:
   - 增加更多边界场景
   - 增加更多组合场景
   - 增加压力测试场景

## 参考

- 完整报告: `docs/STEP2_OFFLINE_BENCHMARK_REPORT.md`
- Harness 框架: `src/harness/`
- 测试套件: `tests/`

---

**版本**: v1.0  
**最后更新**: 2026-08-21  
**维护者**: Harness Team
