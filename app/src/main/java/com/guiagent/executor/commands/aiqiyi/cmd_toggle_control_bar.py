# -*- coding: utf-8 -*-
"""爱奇艺打开/关闭控制条 — v2 重构版。

新流程：直接调用 reveal_controls(app="aiqiyi")，
返回其完整结果（包含 steps_tried + detection 信息）。

外部 API 完全保持兼容。
"""
import sys
import os

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from observation.reveal import reveal_controls  # noqa: E402

from . import _shared as S  # noqa: E402


def run(params=None):
    """显示/隐藏控制条（通过 reveal_controls）。"""
    return reveal_controls(app=S.APP_NAME)
