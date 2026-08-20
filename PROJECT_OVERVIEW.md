# GUIAgent 项目概述

> **智能电视视频助手的 AI Agent 框架**
>
> 面向 Android 9 中屏视频盒，通过自然语言控制爱奇艺、腾讯视频、夸克网盘等 App，
> 解决 Accessibility 节点缺失、自绘播放器控件难定位问题。

---

## 核心架构

```
用户自然语言输入
    ↓
VideoAgent (LLM 意图理解)
    ↓
Harness 执行安全层
    ├─ Action Guard (6 重校验)
    ├─ Control Revealer (显式唤出隐藏控件)
    ├─ DPAD Executor (焦点感知导航)
    └─ Verifier (分层验证)
    ↓
Android 无障碍服务
    ↓
视频 App 响应
```

---

## 关键模块

### 1. Observation 子系统 (`commands/observation/`)

| 模块 | 功能 | Phase |
|------|------|-------|
| `state/` | UI 状态解析器 | 0-1 |
| `reveal/` | 控制条显式唤出 | 2 |
| `dpad/` | DPAD 焦点导航 | 3 |
| `verify/` | 动作验证框架 | 4 |
| `harness/` | Action Guard + 时序追踪 | 4-5 |
| `screen/` | 屏幕观察命令 | 6 |
| `vlm/` | VLM 客户端 | 1 |
| `candidates/` | 候选地图 + 指纹 | A |

### 2. App 命令层 (`commands/aiqiyi/`, `Tencent/`, `quark/`)

- **爱奇艺**: 播放控制、倍速、清晰度、选集、详情页
- **腾讯视频**: 同上
- **夸克网盘**: 搜索、导航、文件选择

### 3. 基础设施 (`commands/common/`)

- `registry.py`: 命令注册表
- `server.py`: HTTP 服务
- `utils.py`: 共享工具函数

---

## 技术亮点

### 1. 无 Dump 操作链路

传统方案依赖 UI dump 获取节点信息，但：
- 自绘控件无节点
- 播放器控制条隐藏时不可见
- dump 性能差 (200-500ms)

**本方案**：
- 使用 `observe_screen()` 获取候选列表
- 基于文本/位置匹配候选
- 性能提升 3-5x (50-100ms)

### 2. Harness 执行安全层

```python
# Action Guard 6 重校验
1. 候选归属验证
2. Bbox 越界检查
3. 页面版本兼容
4. 敏感操作拦截
5. 重复失败排除
6. OCR-only 低置信度细化

# 实测指标
- 拦截率：58% (7/12 异常动作)
- 误拦截率：<5%
```

### 3. 控制条显式唤出

```python
# 三态状态机
active → probation → stale

# 策略序列 (per-App)
1. tap(640, 200)  # 顶部中央
2. DPAD_CENTER    # 遥控器确认
3. MENU           # 菜单键

# 实测成功率：97% (29/30)
```

### 4. 分层验证机制

```
Level 1: 本地信号 (包名/Activity 变化)
Level 2: OCR 文字出现/消失
Level 3: 候选布局变化
Level 4: 控制条状态
Level 5: VLM 视觉验证 (最后手段)

# 实测：100% 验证不需调用 VLM
```

### 5. DPAD 焦点感知导航

```python
# 4 级 API
Level 1: dpad_press(key)           # 单次按键
Level 2: dpad_navigate(dir, count) # 连续导航
Level 3: focus_element(target)     # 目标导向
Level 4: dpad_confirm()            # 确认选择

# 焦点追踪算法
- 记录按幁前焦点位置
- 执行按键
- 检测焦点是否移动
- 返回焦点变化信息
```

---

## 性能指标

| 指标 | 结果 | 目标 |
|------|------|------|
| Action Guard 拦截率 | **58%** | 50-70% |
| Verifier 本地命中率 | **100%** | 60-70% |
| Reveal 策略成功率 | **97%** | 80-90% |
| 端到端 p50 延迟 | **862ms** | ≤2000ms |
| 端到端 p95 延迟 | **972ms** | ≤5000ms |
| 单元测试数 | **86 个** | - |

---

## 快速开始

### 1. 环境准备

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
export DASHSCOPE_API_KEY=your_key_here
export DEVICE_IP=192.168.1.100  # 设备 IP
```

### 2. 启动服务

```bash
# 启动 HTTP 命令服务
python commands/server.py

# 启动 Web 前端 (可选)
python web.py
```

### 3. 使用示例

```python
from commands import execute_command

# 播放控制
execute_command("aiqiyi.set_speed", {"speed": "1.5"})

# 选集
execute_command("aiqiyi.open_episode_panel")
execute_command("aiqiyi.select_episode", {"episode": 5})

# 搜索
execute_command("quark.search", {"keyword": "庆余年"})
```

---

## 项目结构

```
D:\GUIAPP-main/
├── app/src/main/java/com/guiagent/executor/commands/
│   ├── observation/          # 核心子系统
│   │   ├── state/           # UI 状态解析
│   │   ├── reveal/          # 控制条唤出
│   │   ├── dpad/            # DPAD 导航
│   │   ├── verify/          # 验证框架
│   │   ├── harness/         # 安全层
│   │   ├── screen/          # 屏幕观察
│   │   ├── vlm/             # VLM 客户端
│   │   └── candidates/      # 候选管理
│   ├── aiqiyi/              # 爱奇艺命令
│   ├── Tencent/             # 腾讯视频命令
│   ├── quark/               # 夸克网盘命令
│   ├── common/              # 共享工具
│   ├── server.py            # HTTP 服务
│   └── registry.py          # 命令注册
├── agent/                   # Agent 层
├── tests/                   # 测试
└── docs/                    # 文档
```

---

## 文档索引

| 文档 | 内容 |
|------|------|
| `PROJECT_OVERVIEW.md` | 项目概述 (本文档) |
| `PHASE_SUMMARY.md` | Phase 0-7 实施总结 |
| `MIGRATION_GUIDE.md` | 遗留代码迁移指南 |
| `GUIAgent_VLM_Cursor_Implementation_Plan.md` | VLM 集成设计方案 |
| `GUIAgent_VLM_Experience_Memory_Design.md` | 经验记忆设计 |

---

## 开发路线

### 已完成 (Phase 0-7)

- ✅ State Resolver
- ✅ Control Revealer
- ✅ DPAD Executor
- ✅ Verification Framework
- ✅ Integration Tests
- ✅ Dump 依赖移除 (12/12 文件)

### 进行中

- 🔄 `run_episode.py` 迁移 (2 文件，10 处调用)

### 规划中

-  经验记忆系统 (Experience Memory)
- 📋 VLM 视觉验证集成
- 📋 性能优化 (缓存、并行)

---

## 贡献指南

### 添加新 App 命令

1. 创建 `commands/<app_name>/` 目录
2. 实现 `run_*.py` 命令文件
3. 使用 `observe_screen()` 获取候选
4. 注册到 `registry.py`
5. 添加单元测试

### 代码规范

- 使用 `observe_screen()` 而非直接 `dump`
- 所有动作必须经过 Action Guard
- 验证使用分层 Verifier
- 敏感操作必须用户确认

---

## 许可证

MIT License

---

## 联系方式

- GitHub: https://github.com/omit-GitHub/Agent-project
- 问题反馈：提交 Issue

---

**最后更新**: 2026-08-20
**版本**: v1.0.0
