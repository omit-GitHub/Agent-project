# 🎬 GUIAgent 智能视频助手 — Agent 框架

基于通义千问 (DashScope) 的 AI Agent，通过自然语言控制电视设备上的视频应用。

## 快速开始

### 1. 安装依赖

```bash
pip install -r agent/requirements.txt
# 或使用清华镜像
pip install -r agent/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
```

### 2. 配置 API Key

```bash
# 方式 A: 复制配置文件
copy agent\.env.example agent\.env
# 编辑 agent\.env，填入你的 DashScope API Key

# 方式 B: 直接设置环境变量
set DASHSCOPE_API_KEY=sk-你的key
```

> API Key 在 [DashScope 控制台](https://dashscope.console.aliyun.com/apiKey) 获取

### 3. 确保设备 HTTP 服务运行

```bash
# 在设备端（或同一网络）启动 HTTP 复合命令服务
python app/src/main/java/com/guiagent/executor/commands/server.py
```

### 4. 启动 Agent

```bash
# 在 PC 上（需设置 DEVICE_IP 为设备 IP）
set DEVICE_IP=192.168.1.10
python agent/main.py

# 或在设备上（默认 127.0.0.1）
python agent/main.py
```

## 使用示例

```
========================================================
  🎬 GUIAgent 智能视频助手
   Powered by 通义千问 (DashScope)
========================================================

  📺 当前设备: com.qiyi.video.speaker

  👤 > 帮我暂停播放
  🤖 > 好的，已为您暂停播放。

  👤 > 声音大一点
  🤖 > 已将音量调大。

  👤 > 现在在放什么
  🤖 > 当前在爱奇艺，正在播放《庆余年》。

  👤 > 切到第3集
  🤖 > 好的，已切换到第3集。

  👤 > 1.5倍速
  🤖 > 已设置为1.5倍速播放。
```

## 文件说明

| 文件 | 功能 |
|---|---|
| `config.py` | 配置管理（API Key、设备地址、模型选择）|
| `commands.py` | 命令管理 — 从设备获取命令列表，生成 LLM tools schema |
| `agent.py` | 核心 Agent — 多轮对话 + function calling + 命令执行 |
| `main.py` | CLI 入口 — 交互式终端对话 |
| `requirements.txt` | Python 依赖 |
| `.env.example` | 配置模板 |

## 配置项

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `DASHSCOPE_API_KEY` | (必填) | DashScope API Key |
| `DEVICE_IP` | `127.0.0.1` | 设备 IP |
| `DEVICE_PORT` | `8765` | HTTP 端口 |
| `MODEL_NAME` | `qwen-plus` | 模型 (qwen-turbo/plus/max/long) |
| `MAX_TOOL_CALLS` | `5` | 每轮最大 function call 次数 |
| `MAX_HISTORY_TURNS` | `20` | 对话历史最大轮数 |
| `AGENT_DEBUG` | `0` | 调试模式 (1=开启) |

## 架构

```
用户文字输入 → Qwen LLM (function calling)
                   │
                   ▼ control_device(command, params)
                   │
              HTTP POST :8765/v1/compound
                   │
                   ▼
              GUIAgent 设备端 (54 个命令)
                   │
                   ▼ 返回 state
                   │
              Qwen LLM 生成自然语言回复
                   │
                   ▼
              用户看到回复
```

## 扩展方向

- **语音输入**: 接入 Whisper/讯飞 ASR，替换终端输入
- **语音输出**: 接入 edge-tts/讯飞 TTS，实现语音回复
- **更多设备**: 扩展 commands.py 的 COMMAND_DOCS 适配新应用
- **多模态**: 截图发图片给 Qwen-VL，实现"看到什么说什么"
