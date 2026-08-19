# -*- coding: utf-8 -*-
"""截图数据模型。"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class ScreenshotFrame:
    """单次截图的完整上下文。"""
    path: str               # 本地 PNG 路径
    width: int              # 屏幕宽度（像素）
    height: int             # 屏幕高度（像素）
    sha256: str             # 文件 hash（用于 trace 去重）
    captured_at: float      # 截图时间戳
    request_id: Optional[str] = None  # 请求 ID
