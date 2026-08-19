# -*- coding: utf-8 -*-
"""observe_screen — 无 dump 的统一观察入口。

Phase A 重写：
- 移除 dump 依赖
- 使用 ScreenshotProvider + CandidateBuilder
- 返回 CandidateMap（兼容旧 elements 格式）

工作流：
  1. 获取当前包名、Activity（从 ping）
  2. 截图
  3. OCR 候选生成
  4. 构建 CandidateMap
  5. 返回兼容格式

返回格式（兼容旧版 + 新增字段）：
  {
    "screen_version": "...",
    "package": "com.example.video",
    "activity": "PlayerActivity",
    "screen_size": {"width": 1280, "height": 800},
    "page_type": "player",
    "control_bar_visible": true,
    "overlay": null,
    "ocr_status": "ok",
    "detector_status": "disabled",
    "elements": [...],  // 兼容旧格式
    "candidates": [...] // 新格式（CandidateMap）
  }
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from send import send
from common.utils import success_with_data, error

from observation.screen.provider import AdbScreenshotProvider
from observation.candidates.builder import CandidateBuilder
from observation.observation_cache import get_candidate_map


# ─────────────────────── 屏幕信息采集 ───────────────────────

def get_screen_info():
    """获取当前屏幕基本信息（包名、Activity、尺寸）。"""
    try:
        resp = send({"id": "obs_ping", "op": "ping", "args": {}})
        if not resp.get("ok"):
            return None

        data = resp.get("data", {})
        return {
            "package": data.get("package", "") or data.get("pkg", ""),
            "activity": data.get("activity", ""),
            "screen": data.get("screen", {"width": 1280, "height": 800}),
        }
    except Exception as e:
        print(f"[observe_screen] 获取屏幕信息失败: {e}")
        return None


# ─────────────────────── 主入口 ───────────────────────

def observe_screen(params=None):
    """观察当前屏幕，返回候选列表。

    Args:
        params: 可选参数字典

    Returns:
        dict: success_with_data("observe_screen", {...}) 或 error(...)
    """
    # 1. 获取屏幕信息
    info = get_screen_info()
    if not info:
        return error("SCREEN_INFO_FAILED", "Failed to get screen info")

    package = info["package"]
    activity = info["activity"]
    screen = info["screen"]

    # 2. 构建候选
    try:
        provider = AdbScreenshotProvider(output_dir="./runtime/screenshots")
        builder = CandidateBuilder(screenshot_provider=provider)

        candidate_map = builder.build(
            request_id=f"obs_{int(time.time())}",
            package=package,
            activity=activity,
            page_type="unknown",  # Phase A 暂不分类
            control_bar_visible=None,
            overlay=None,
        )
    except Exception as e:
        return error("BUILD_FAILED", f"CandidateBuilder failed: {e}")

    # 3. 构建响应（兼容旧格式 + 新增字段）
    elements = []
    for c in candidate_map.candidates:
        elements.append({
            "element_id": c.candidate_id,
            "label": c.text or c.detector_label or c.kind,
            "action_rect": [c.bbox_px.x1, c.bbox_px.y1, c.bbox_px.x2, c.bbox_px.y2],
            "action_point": list(c.bbox_px.center()),
            "source": c.source,
            "click_confidence": c.clickable_likelihood,
            "evidence": {
                "ocr": {"text": c.text, "confidence": c.confidence} if c.source in ("ocr", "ocr+visual") else None,
                "visual": {"kind": c.kind, "confidence": c.confidence} if c.source in ("visual", "ocr+visual") else None,
            },
        })

    data = {
        # 新增字段
        "screen_version": candidate_map.screen_version,
        "package": candidate_map.package,
        "activity": candidate_map.activity,
        "page_type": candidate_map.page_type,
        "control_bar_visible": None,  # Phase A 暂不检测
        "overlay": None,
        "ocr_status": candidate_map.ocr_status,
        "detector_status": candidate_map.detector_status,
        "degradation_mode": candidate_map.degradation_mode,
        "candidates": [c.model_dump() for c in candidate_map.candidates],
        # 兼容旧字段
        "screen_size": {"width": candidate_map.width, "height": candidate_map.height},
        "elements": elements,
        "element_count": len(elements),
        "dump_status": "unavailable",  # Phase A 不再使用 dump
    }

    return success_with_data("observe_screen", data)


# 别名（registry 注册用）
handler = observe_screen


if __name__ == "__main__":
    import json
    result = observe_screen()
    print(json.dumps(result, ensure_ascii=False, indent=2))
