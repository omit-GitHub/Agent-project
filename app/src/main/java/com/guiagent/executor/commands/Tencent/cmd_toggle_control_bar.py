# -*- coding: utf-8 -*-
"""腾讯视频控制条显示/隐藏 — v2 重构版。"""
import sys
import os

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from observation.reveal import reveal_controls  # noqa: E402

from . import _shared as S  # noqa: E402


def run(params=None):
    """显示/隐藏控制条。"""
    return reveal_controls(app=S.APP_NAME)
