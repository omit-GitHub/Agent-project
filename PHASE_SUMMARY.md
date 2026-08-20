# GUIAgent Phase 0-7 实施总结

## 项目概述

面向 Android 9 中屏视频盒的自然语言 GUI 操作框架，解决 Accessibility 节点缺失、自绘播放器控件难定位问题。

---

## 阶段成果

### Phase 0: State Resolver 基础 ✅
**文件**: `observation/state/{schema,resolver,page_classifier,player_state}.py`
- StateSnapshot 数据模型
- 页面分类器（包名 + 启发式）
- 播放器状态检测

### Phase 1: State Resolver 集成 ✅
**文件**: `registry.py`, `common/cmd_get_state.py`
- registry 改用 resolve_state() 返回富状态
- get_state 命令返回 ~12 字段增强 schema

### Phase 2: Control Revealer ✅
**文件**: `observation/reveal/{strategies,detectors,revealer}.py`
- per-App 优先级动作序列
- 三级控制条检测（容器 ID / 按钮 ID / OCR 文字）
- 删除旧 `ocr/cmd_reveal_controls.py`

### Phase 3: DPAD Executor ✅
**文件**: `observation/dpad/{executor,focus_tracker,keymaps}.py`
- 4 级 API（press / navigate / focus_element / confirm）
- 焦点追踪算法
- per-App 键位映射

### Phase 4: Verification Framework ✅
**文件**: `observation/verify/{verifier,predicates,recovery}.py`
- 8 个内置谓词
- verify_after_action() 封装
- 恢复策略（re_reveal / retry_dpad_enter / wait_and_retry）

### Phase 5: 集成测试 ✅
**文件**: `tests/{harness_benchmark,integration_test}.py`
- Action Guard 拦截率：58%
- Verifier 本地命中率：100%
- Reveal 策略成功率：97%
- 端到端 p95 延迟：972ms

### Phase 6: 移除 dump 依赖 ✅
**迁移文件**:
- aiqiyi: `run_speed.py`, `run_resolution.py`, `cmd_open_detail.py`
- quark: `cmd_go_back.py`, `cmd_launch_app.py`, `cmd_click_navigation.py`, `cmd_search.py`
- common: `cmd_launcher_search.py`
- observation: `dpad/executor.py`
- registry.py: capture_state() 改用 ping

**保留向后兼容**:
- `common/utils.py`: dump()/find_nodes() 保留
- `quark/__init__.py`: 内部工具函数保留

### Phase 7: 标记遗留接口 ✅
**文件**: `Protocol.java`
- dump/find 添加 @Deprecated 注释
- 说明新代码应使用 observe_screen()
- 保留操作供旧代码向后兼容

---

## 架构变更

### 新增 observation/ 子系统

```
observation/
├── state/          # State Resolver (Phase 0-1)
── reveal/         # Control Revealer (Phase 2)
├── dpad/           # DPAD Executor (Phase 3)
├── verify/         # Verification Framework (Phase 4)
── harness/        # Action Guard + Timing (Phase 4-5)
├── screen/         # observe_screen 命令 (Phase 6)
├── vlm/            # VLM Client (Phase 1)
└── candidates/     # CandidateMap + Fingerprint (Phase A)
```

### 命令注册变化

| 命令 | 旧实现 | 新实现 |
|------|--------|--------|
| get_state | dump → pkg+summary | ping → StateSnapshot |
| reveal_controls | 硬编码 tap(640,400) | 策略序列 + 三级检测 |
| vlm_execute | 不存在 | VLM 主导闭环 |
| aiqiyi.set_speed | dump 找节点 | observe_screen 候选匹配 |
| aiqiyi.set_quality | dump 找节点 | observe_screen 候选匹配 |

---

## 关键指标

| 指标 | 结果 |
|------|------|
| Action Guard 拦截率 | 58% (7/12 异常动作) |
| Verifier 本地命中率 | 100% (不需 VLM) |
| Reveal 策略成功率 | 97% (29/30) |
| 端到端 p95 延迟 | 972ms (目标 ≤5000ms) |
| 迁移命令数 | 10 个 |
| 单元测试数 | 86 个 |

---

## 遗留技术债务

1. **旧 App 命令直接调用 dump/find**
   - `aiqiyi/run_episode.py` (4 处)
   - `Tencent/run_episode.py` (5 处)
   - `aiqiyi/run_detail.py` (1 处)
   - `aiqiyi/detect.py` (1 处)
   - 完全移除需迁移这些调用

2. **Protocol.java dump/find 注册**
   - 已标记 @Deprecated
   - 待所有直接调用迁移后可移除

3. **common/utils.py dump()/find_nodes()**
   - 保留供 quark/__init__.py 内部使用
   - 新代码不应使用

---

## 简历可用描述

```
面向 Android 9 中屏视频 App 中 Accessibility 节点缺失和自绘控件难定位问题，
设计无 Dump 的多模态 GUI Agent：

- 并行融合 OCR 文字锚点与视觉交互区域检测，通过 Set-of-Mark 将 VLM 自由坐标
  预测转化为候选选择
- 构建 Harness 完成动作白名单、页面版本校验、隐藏控件唤出、结果验证与有限恢复
- 首次成功轨迹沉淀为带前置条件、视觉指纹和自动失效机制的可复用技能
- 主导 Phase 6 架构迁移：将 10 个 App 命令从 UI dump 依赖迁移到
  observe_screen() 候选匹配模式

实测指标：
- Action Guard 拦截 58% 异常动作
- Verifier 100% 本地验证不需调用 VLM
- Reveal 策略成功率 97%
- 端到端 p95 延迟 972ms
```

---

**文档版本**: 2026-08-20
**Git 提交**: `c641374` (Phase 7 完成)
