# -*- coding: utf-8 -*-
"""Agent 配置 — 从环境变量或 .env 文件读取。

用法:
  1. 复制 .env.example 为 .env，填入你的 API Key
  2. 或在终端设置环境变量:
     set DASHSCOPE_API_KEY=sk-xxx
     set DEVICE_IP=192.168.1.10
"""
import os

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    # 从 agent/ 目录找 .env
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
    else:
        load_dotenv()  # 从当前目录找
except ImportError:
    pass  # python-dotenv 未安装，只用环境变量


# ─────────────── DashScope API ───────────────

# 通义千问 API Key（文本模型，必填）
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")

# VLM API Key（视觉模型，可选独立账号；留空则复用 DASHSCOPE_API_KEY）
VLM_API_KEY = os.environ.get("VLM_API_KEY", "") or DASHSCOPE_API_KEY

# DashScope OpenAI 兼容端点（文本 + VLM 共用）
DASHSCOPE_BASE_URL = os.environ.get(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1"
)

# 文本模型名称（qwen-plus 性价比高，qwen-max 能力最强）
# 可选: qwen-turbo, qwen-plus, qwen-max, qwen-long, qwen3.7-plus
MODEL_NAME = os.environ.get("MODEL_NAME", "qwen-plus")

# VLM 模型名称（视觉语言模型）
# 可选: qwen-vl-plus (便宜), qwen-vl-max (精度更高)
VLM_MODEL_NAME = os.environ.get("VLM_MODEL_NAME", "qwen-vl-plus")


# ─────────────── 设备连接 ───────────────

# 设备 IP（Agent 运行在设备上时用 127.0.0.1）
DEVICE_IP = os.environ.get("DEVICE_IP", "127.0.0.1")

# HTTP 复合命令端口
DEVICE_PORT = int(os.environ.get("DEVICE_PORT", "8765"))

# 设备 API 基础 URL
DEVICE_URL = f"http://{DEVICE_IP}:{DEVICE_PORT}"


# ─────────────── Agent 行为 ───────────────

# 最大连续 function call 次数（防止死循环）
# v2: 5 → 8。observe-reveal-act-verify 链需要 4-6 次调用，8 给 recovery 留余量
MAX_TOOL_CALLS_PER_TURN = int(os.environ.get("MAX_TOOL_CALLS", "8"))

# 对话历史最大轮数（超过后截断旧消息）
MAX_HISTORY_TURNS = int(os.environ.get("MAX_HISTORY_TURNS", "20"))

# 是否显示调试日志（命令调用详情）
DEBUG = os.environ.get("AGENT_DEBUG", "").lower() in ("1", "true", "yes")
