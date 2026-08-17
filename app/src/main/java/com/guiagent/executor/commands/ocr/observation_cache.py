# -*- coding: utf-8 -*-
"""观察缓存 — 存储最近一次 observe_screen 的结果。

用于 click_element 校验 element_id 和 screen_version。

缓存策略：
  - 只保留最近一次观察结果
  - 任何动作（click、swipe、input）后自动失效
  - screen_version 不匹配时拒绝点击
"""
import threading
import time


# 全局缓存
_cache_lock = threading.Lock()
_cache = {
    "screen_version": None,
    "elements": {},  # element_id -> element
    "timestamp": 0,
}

# 缓存有效期（秒）
CACHE_TTL = 30


def update_observation(screen_version, elements):
    """更新观察缓存。

    Args:
        screen_version: 屏幕版本标识
        elements: 元素列表
    """
    global _cache
    with _cache_lock:
        _cache = {
            "screen_version": screen_version,
            "elements": {e["element_id"]: e for e in elements},
            "timestamp": time.time(),
        }


def get_observation():
    """获取当前观察缓存。

    Returns:
        dict or None: 缓存未命中或已过期时返回 None
    """
    with _cache_lock:
        if not _cache["screen_version"]:
            return None

        # 检查是否过期
        if time.time() - _cache["timestamp"] > CACHE_TTL:
            return None

        return {
            "screen_version": _cache["screen_version"],
            "elements": _cache["elements"].copy(),
        }


def get_element(element_id):
    """获取指定 element_id 的元素。

    Returns:
        dict or None: 元素不存在时返回 None
    """
    obs = get_observation()
    if not obs:
        return None
    return obs["elements"].get(element_id)


def invalidate():
    """失效缓存（任何动作后调用）。"""
    global _cache
    with _cache_lock:
        _cache = {
            "screen_version": None,
            "elements": {},
            "timestamp": 0,
        }


def check_screen_version(expected_version):
    """校验 screen_version 是否匹配。

    Returns:
        bool: 匹配返回 True，否则 False
    """
    obs = get_observation()
    if not obs:
        return False
    return obs["screen_version"] == expected_version
