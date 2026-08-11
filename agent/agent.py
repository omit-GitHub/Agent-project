# -*- coding: utf-8 -*-
"""核心 Agent — 通义千问 function calling + 设备控制。

VideoAgent 类:
  - 维护多轮对话上下文
  - 将用户消息 + 工具调用发送给 Qwen
  - 自动执行设备命令并回传结果
  - 生成自然语言回复
"""
import json
import re
import requests
from openai import OpenAI

from . import config
from .commands import build_tools_schema, fetch_available_commands, get_command_description


# ─────────────── 搜索关键词归一化 ───────────────

# 中文数字 → 阿拉伯数字 映射
_CN_NUM_MAP = {
    "零": "0", "一": "1", "二": "2", "两": "2", "三": "3", "四": "4",
    "五": "5", "六": "6", "七": "7", "八": "8", "九": "9", "十": "10",
    "壹": "1", "贰": "2", "叁": "3", "肆": "4", "伍": "5",
    "陆": "6", "柒": "7", "捌": "8", "玖": "9",
}


def _normalize_search_keyword(keyword):
    """归一化搜索关键词：中文数字→阿拉伯数字，去掉冗余修饰。

    示例:
      "喜剧之王单口季第三季" → "喜剧之王单口季第3季"
      "帮我找一下战狼2"    → "战狼2"
      "第二集"             → "第2集"
    """
    # 1. 中文数字替换（只在"第X"、"X季"、"X集"等上下文中替换，避免误改片名）
    result = keyword
    # "第X" 模式
    result = re.sub(
        r"第([" + "".join(_CN_NUM_MAP.keys()) + r"])",
        lambda m: "第" + _CN_NUM_MAP[m.group(1)],
        result,
    )
    # "X季" / "X部" / "X期" 模式（前面是中文数字）
    for cn, ar in _CN_NUM_MAP.items():
        result = result.replace(f"{cn}季", f"{ar}季")
        result = result.replace(f"{cn}部", f"{ar}部")
        result = result.replace(f"{cn}期", f"{ar}期")

    # 2. 去掉常见开头冗余词（按长度从长到短匹配，避免短前缀先截取）
    prefixes = ["帮我找一下", "帮我搜索一下", "帮我搜索", "帮我找", "帮我搜", "搜一下", "搜索", "找一下", "看一下", "播放"]
    for prefix in sorted(prefixes, key=len, reverse=True):
        if result.startswith(prefix) and len(result) > len(prefix):
            result = result[len(prefix):]
            break

    return result.strip()


# ─────────────── System Prompt ───────────────

SYSTEM_PROMPT = """你是一个智能电视助手，连接了一台客厅电视设备。你可以通过 control_device 工具控制设备上的视频应用。

## 支持的应用
- **爱奇艺** (com.qiyi.video.speaker) — 命令前缀 aiqiyi.
- **腾讯视频** (com.tencent.qqlive.audiobox) — 命令前缀 tencent.
- **夸克网盘** (com.quark.yun.tv) — 命令前缀 quark.
- **通用命令** — 不区分应用（音量、返回、主页、搜索等）

## 工作流程
1. 收到用户指令后，先用 get_state 确认当前在哪个应用
2. 根据应用选择对应的命令（如在爱奇艺就用 aiqiyi.xxx）
3. 调用 control_device 执行操作
4. 根据返回的 state 判断操作结果，简洁地告知用户

## 回复规范
- 用中文回复，简洁友好，像真人助手一样说话
- 操作成功：简短确认即可（"好的，已为您暂停" / "音量已调大"）
- 操作失败：说明原因并建议替代方案（"当前是电影没有选集功能" / "设备未响应，要再试一次吗？"）
- 不要暴露技术细节（命令名、ID 等），只说用户能理解的话
- 用户问"在放什么"时，根据 get_state 返回的 pkg 和 summary 推断

## 搜索关键词优化
用户说的片名常常和设备里的标题不完全一致。调用 launcher_search 前，请做以下归一化：
- **中文数字 → 阿拉伯数字**：用户说"第三季"应搜"第3季"，"第一集"搜"第1集"
- **去掉冗余修饰词**：用户说"帮我找一下xxx"只搜"xxx"
- **保留季数/集数**：不要主动去掉"第X季"等限定词，先完整搜索
- **仅当搜索返回 0 结果时**，再去掉季数/集数重搜一次作为兜底
- **常见映射**：一→1, 二→2, 三→3, 四→4, 五→5, 六→6, 七→7, 八→8, 九→9, 十→10

## 注意
- 每次调用 control_device 后会自动返回设备状态（state 字段），包含前台应用包名和页面可见文本
- 如果 get_state 返回的 pkg 为空，说明设备可能未就绪
- 遥控器按键类命令（prev_episode 等）偶尔会超时，这属于正常现象"""


# ─────────────── Agent 类 ───────────────

class VideoAgent:
    """智能视频助手 Agent。"""

    def __init__(self, device_url=None, api_key=None, model=None):
        """初始化 Agent。

        Args:
            device_url: 设备 HTTP API 地址（默认从 config 读取）
            api_key: DashScope API Key（默认从 config 读取）
            model: 模型名称（默认从 config 读取）
        """
        self.device_url = device_url or config.DEVICE_URL
        api_key = api_key or config.DASHSCOPE_API_KEY
        self.model = model or config.MODEL_NAME

        if not api_key:
            raise ValueError(
                "缺少 DASHSCOPE_API_KEY！\n"
                "请设置环境变量或在 agent/.env 文件中配置:\n"
                "  DASHSCOPE_API_KEY=sk-xxx"
            )

        # 初始化 OpenAI 客户端（DashScope 兼容模式）
        self.client = OpenAI(
            api_key=api_key,
            base_url=config.DASHSCOPE_BASE_URL,
        )

        # 对话历史
        self.history = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

        # 加载可用命令和 tools schema
        self.available_commands = fetch_available_commands()
        self.tools = build_tools_schema(self.available_commands)

        # 统计
        self.total_tool_calls = 0
        self.total_turns = 0

    def chat(self, user_message):
        """处理一条用户消息，返回 Agent 回复。

        流程:
        1. 追加 user message 到 history
        2. 调 Qwen（带 tools）
        3. 如果返回 tool_calls → 执行命令 → 追加结果 → 再调一次
        4. 返回文字回复

        Args:
            user_message: 用户输入文本

        Returns:
            str: Agent 回复文本
        """
        self.history.append({"role": "user", "content": user_message})
        self.total_turns += 1

        # 裁剪过长的历史
        self._trim_history()

        # 调用 LLM（可能需要多轮 tool call）
        return self._chat_loop()

    def _chat_loop(self):
        """LLM 调用循环（处理可能的连续 tool calls）。"""
        for _ in range(config.MAX_TOOL_CALLS_PER_TURN):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
                tools=self.tools,
                tool_choice="auto",
            )

            message = response.choices[0].message

            # 如果没有 tool_calls，直接返回文字回复
            if not message.tool_calls:
                reply = message.content or ""
                self.history.append({"role": "assistant", "content": reply})
                return reply

            # 有 tool_calls → 执行命令
            # 先把 assistant 的 message（含 tool_calls）追加到 history
            self.history.append(message.model_dump())

            # 执行每个 tool call
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)

                if func_name == "control_device":
                    cmd = func_args.get("command", "")
                    params = func_args.get("params", {})
                    result = self._execute_command(cmd, params)
                    result_str = json.dumps(result, ensure_ascii=False)
                else:
                    result_str = json.dumps({
                        "ok": False,
                        "error": {"code": "UNKNOWN_TOOL", "message": f"未知工具: {func_name}"}
                    })

                # 追加 tool 结果到 history
                self.history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_str,
                })
                self.total_tool_calls += 1

            # 继续循环，让 LLM 根据 tool 结果生成回复
            # （可能继续调 tool，也可能直接回复）

        # 超过最大 tool call 次数
        fallback = "抱歉，操作执行次数过多，已停止。请重新描述您的需求。"
        self.history.append({"role": "assistant", "content": fallback})
        return fallback

    def _execute_command(self, command, params):
        """执行设备命令。

        调用 HTTP POST /v1/compound。
        执行前自动归一化搜索关键词（中文数字→阿拉伯数字）。
        """
        # 归一化搜索关键词（兜底，system prompt 已要求 LLM 做同样的事）
        if command in ("launcher_search", "search") and isinstance(params, dict):
            kw = params.get("keyword", "")
            if kw:
                params = dict(params)  # 避免修改原始 dict
                params["keyword"] = _normalize_search_keyword(kw)

        try:
            resp = requests.post(
                f"{self.device_url}/v1/compound",
                json={"command": command, "params": params},
                timeout=20,
            )
            resp.raise_for_status()
            result = resp.json()

            # 打印调试信息
            if config.DEBUG:
                status = "✅" if result.get("ok") else "❌"
                desc = get_command_description(command)
                print(f"  {status} {command} → {desc}")

            return result

        except requests.exceptions.ConnectionError:
            return {
                "ok": False,
                "error": {
                    "code": "CONNECTION_FAILED",
                    "message": f"无法连接设备 {self.device_url}，请确认设备 HTTP 服务已启动"
                }
            }
        except requests.exceptions.Timeout:
            return {
                "ok": False,
                "error": {
                    "code": "TIMEOUT",
                    "message": "设备响应超时"
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "EXECUTION_FAILED",
                    "message": str(e)
                }
            }

    def get_device_state(self):
        """获取设备当前状态（快捷方法）。"""
        return self._execute_command("get_state", {})

    def reset(self):
        """重置对话历史。"""
        self.history = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        self.total_turns = 0

    def _trim_history(self):
        """裁剪过长的对话历史（保留 system prompt + 最近 N 轮）。"""
        max_messages = config.MAX_HISTORY_TURNS * 2 + 1  # user+assistant 各一条 * 轮数 + system
        if len(self.history) > max_messages:
            # 保留 system prompt + 最近的消息
            self.history = [self.history[0]] + self.history[-(max_messages - 1):]

    def get_stats(self):
        """获取统计信息。"""
        return {
            "total_turns": self.total_turns,
            "total_tool_calls": self.total_tool_calls,
            "history_length": len(self.history),
            "available_commands": len(self.available_commands),
        }
