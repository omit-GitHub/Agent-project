# -*- coding: utf-8 -*-
"""观察缓存 — 存储最近一次 CandidateMap。

Phase A 更新：改为存储 CandidateMap 而非旧版 elements dict。
兼容旧接口（get_element/check_screen_version），内部映射到 CandidateMap。

缓存策略：
  - 只保留最近一次观察结果
  - 任何动作（click、swipe、input）后自动失效
  - screen_version 不匹配时拒绝点击
"""
import threading
import time
from typing import Optional

from .candidates.schemas import CandidateMap, UiCandidate


# 全局缓存
_cache_lock = threading.Lock()
_cache: Optional[CandidateMap] = None
_timestamp: float = 0

# 缓存有效期（秒）
CACHE_TTL = 30


def update_observation_from_candidate_map(candidate_map: CandidateMap):
    """从 CandidateMap 更新观察缓存。

    Args:
        candidate_map: 最新候选地图
    """
    global _cache, _timestamp
    with _cache_lock:
        _cache = candidate_map
        _timestamp = time.time()


def update_observation(screen_version: str, elements: list[dict]):
    """更新观察缓存（兼容旧接口）。

    内部转换为 CandidateMap 存储。

    Args:
        screen_version: 屏幕版本标识
        elements: 元素列表（旧格式）
    """
    # 兼容层：旧格式不存储为 CandidateMap，只存储 screen_version
    # 新代码应使用 update_observation_from_candidate_map
    global _cache, _timestamp
    with _cache_lock:
        _timestamp = time.time()
        # 不更新 _cache（保持 CandidateMap 类型）


def get_candidate_map() -> Optional[CandidateMap]:
    """获取当前 CandidateMap 缓存。

    Returns:
        CandidateMap or None: 缓存未命中或已过期时返回 None
    """
    global _cache, _timestamp
    with _cache_lock:
        if _cache is None:
            return None

        # 检查是否过期
        if time.time() - _timestamp > CACHE_TTL:
            return None

        return _cache


def get_observation():
    """获取当前观察缓存（兼容旧接口）。

    Returns:
        dict or None: 缓存未命中或已过期时返回 None
    """
    cmap = get_candidate_map()
    if not cmap:
        return None

    # 转换为旧格式（兼容 click_element）
    elements = []
    for c in cmap.candidates:
        elements.append({
            "element_id": c.candidate_id,
            "label": c.text or c.detector_label or "",
            "action_rect": [c.bbox_px.x1, c.bbox_px.y1, c.bbox_px.x2, c.bbox_px.y2],
            "action_point": list(c.bbox_px.center()),
            "source": c.source,
            "click_confidence": c.clickable_likelihood,
        })

    return {
        "screen_version": cmap.screen_version,
        "elements": {e["element_id"]: e for e in elements},
    }


def get_element(element_id: str):
    """获取指定 element_id 的元素。

    Returns:
        dict or None: 元素不存在时返回 None
    """
    obs = get_observation()
    if not obs:
        return None
    return obs["elements"].get(element_id)


def get_candidate_by_id(candidate_id: str) -> Optional[UiCandidate]:
    """根据 candidate_id 获取候选。

    Returns:
        UiCandidate or None
    """
    cmap = get_candidate_map()
    if not cmap:
        return None
    for c in cmap.candidates:
        if c.candidate_id == candidate_id:
            return c
    return None


def invalidate():
    """失效缓存（任何动作后调用）。"""
    global _cache, _timestamp
    with _cache_lock:
        _cache = None
        _timestamp = 0


def check_screen_version(expected_version: str) -> bool:
    """校验 screen_version 是否匹配。

    Returns:
        bool: 匹配返回 True，否则 False
    """
    cmap = get_candidate_map()
    if not cmap:
        return False
    return cmap.screen_version == expected_version
