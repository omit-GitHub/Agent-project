# -*- coding: utf-8 -*-
"""Control Revealer 子包 — 隐藏控件显式唤出。

对外暴露:
  - reveal_controls(app, context, max_steps) → dict  (主入口，在 revealer.py)
  - detect_control_bar(tree, ocr_texts, run_ocr_if_needed) → dict  (在 detectors.py)
  - get_strategy(app) → list  (在 strategies.py)
"""
from .revealer import reveal_controls, detect_app_from_pkg
from .detectors import detect_control_bar
from .strategies import get_strategy, list_apps, STRATEGIES

__all__ = [
    "reveal_controls",
    "detect_app_from_pkg",
    "detect_control_bar",
    "get_strategy",
    "list_apps",
    "STRATEGIES",
]
