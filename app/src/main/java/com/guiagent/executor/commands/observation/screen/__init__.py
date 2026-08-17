# -*- coding: utf-8 -*-
"""observation.screen — 屏幕观察命令（从原 ocr/ 迁移而来）。

对外暴露:
  - observe_screen(params) → dict  观察当前屏幕，返回元素列表
  - click_element(params) → dict   点击已观察的元素
"""
from .cmd_observe_screen import observe_screen
from .cmd_click_element import click_element

__all__ = ["observe_screen", "click_element"]
