# -*- coding: utf-8 -*-
"""VLM Client — 调用 DashScope qwen-vl-plus。

对应 Cursor 任务书 §5.2。
提供两个方法：
  - observe(): 观察截图，返回单步动作建议
  - verify(): 验证动作结果
"""
import json
import os
import re
from typing import Optional
from openai import OpenAI

from .prompts import build_observe_prompt, build_verify_prompt
from .schemas import ObserveResult, NextAction, VerifyResult


class VlmClientError(Exception):
    """VLM 调用失败时抛出。"""
    pass


class VlmInvalidOutput(VlmClientError):
    """VLM 返回无法解析的输出时抛出。"""
    pass


class QwenVlmClient:
    """DashScope qwen-vl-plus 客户端。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        enable_thinking: bool = False,
        max_tokens: int = 300,
        timeout: int = 15,
    ):
        """初始化 VLM 客户端。

        Args:
            api_key: DashScope API Key（默认从环境变量 VLM_API_KEY 读取）
            base_url: API 端点（默认 https://dashscope.aliyuncs.com/compatible-mode/v1）
            model: 模型名（默认 qwen-vl-plus）
            enable_thinking: 是否启用思考模式（默认关闭）
            max_tokens: 最大输出 token 数（默认 300）
            timeout: 请求超时（秒，默认 15）
        """
        self.api_key = api_key or os.environ.get("VLM_API_KEY", "")
        if not self.api_key:
            raise VlmClientError("VLM_API_KEY not set in environment")

        self.base_url = base_url or os.environ.get(
            "DASHSCOPE_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.model = model or os.environ.get("VLM_MODEL", "qwen-vl-plus")
        self.enable_thinking = enable_thinking
        self.max_tokens = max_tokens
        self.timeout = timeout

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def observe(
        self,
        screenshot_path: str,
        subgoal: str,
        trajectory: list[dict] | None = None,
        allowed_actions: list[str] | None = None,
    ) -> ObserveResult:
        """观察截图，返回单步动作建议。

        Args:
            screenshot_path: 截图文件路径（PNG）
            subgoal: 用户子目标
            trajectory: 已执行动作列表
            allowed_actions: 允许的动作类型

        Returns:
            ObserveResult

        Raises:
            VlmClientError: 调用失败
            VlmInvalidOutput: 输出无法解析
        """
        messages = build_observe_prompt(subgoal, trajectory, allowed_actions)

        # 添加截图到 user 消息
        import base64
        with open(screenshot_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode("utf-8")

        messages[1]["content"] = [
            {"type": "text", "text": messages[1]["content"]},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
        ]

        # 调用 VLM
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                extra_body={"enable_thinking": self.enable_thinking},
            )
        except Exception as e:
            raise VlmClientError(f"VLM API call failed: {e}")

        content = response.choices[0].message.content
        if not content:
            raise VlmInvalidOutput("VLM returned empty content")

        # 解析 JSON
        return self._parse_observe_result(content)

    def verify(
        self,
        screenshot_path: str,
        subgoal: str,
        action: NextAction | dict | None = None,
        expected: str = "",
    ) -> VerifyResult:
        """验证动作结果。

        Args:
            screenshot_path: 操作后截图路径
            subgoal: 用户子目标
            action: 刚执行的动作
            expected: 预期结果

        Returns:
            VerifyResult
        """
        messages = build_verify_prompt(subgoal, action, expected)

        import base64
        with open(screenshot_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode("utf-8")

        messages[1]["content"] = [
            {"type": "text", "text": messages[1]["content"]},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                extra_body={"enable_thinking": self.enable_thinking},
            )
        except Exception as e:
            raise VlmClientError(f"VLM API call failed: {e}")

        content = response.choices[0].message.content
        if not content:
            raise VlmInvalidOutput("VLM returned empty content")

        return self._parse_verify_result(content)

    def _parse_observe_result(self, content: str) -> ObserveResult:
        """解析 VLM 返回的 Observe JSON。"""
        # 提取 JSON（可能被 markdown 包裹）
        json_str = self._extract_json(content)
        if not json_str:
            raise VlmInvalidOutput(f"Cannot extract JSON from: {content[:200]}")

        try:
            data = json.loads(json_str)
            return ObserveResult(**data)
        except json.JSONDecodeError as e:
            raise VlmInvalidOutput(f"Invalid JSON: {e}")
        except Exception as e:
            raise VlmInvalidOutput(f"Schema validation failed: {e}")

    def _parse_verify_result(self, content: str) -> VerifyResult:
        """解析 VLM 返回的 Verify JSON。"""
        json_str = self._extract_json(content)
        if not json_str:
            raise VlmInvalidOutput(f"Cannot extract JSON from: {content[:200]}")

        try:
            data = json.loads(json_str)
            return VerifyResult(**data)
        except json.JSONDecodeError as e:
            raise VlmInvalidOutput(f"Invalid JSON: {e}")
        except Exception as e:
            raise VlmInvalidOutput(f"Schema validation failed: {e}")

    @staticmethod
    def _extract_json(text: str) -> Optional[str]:
        """从文本中提取 JSON 字符串。

        支持：
        - 纯 JSON
        - ```json ... ``` 包裹
        - ``` ... ``` 包裹
        """
        # 尝试匹配 ```json ... ```
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            return match.group(1).strip()

        # 尝试匹配 {...}
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return match.group(0).strip()

        return None
