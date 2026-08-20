# -*- coding: utf-8 -*-
"""Visual Detector Sidecar 客户端。

通过 HTTP 与 detector 服务通信（如 OmniParser）。
支持熔断器模式：连续失败后自动降级。
"""
import time
from typing import List, Optional

import requests

from .interface import UiDetector, DetectionResult


class SidecarDetector(UiDetector):
    """HTTP sidecar detector 客户端。"""

    def __init__(
        self,
        url: str = "http://127.0.0.1:8790",
        timeout_ms: int = 900,
        min_confidence: float = 0.25,
    ):
        self.url = url
        self.timeout = timeout_ms / 1000.0
        self.min_confidence = min_confidence

        # 熔断器状态
        self._failure_count = 0
        self._circuit_open_until = 0.0
        self._max_failures = 3
        self._circuit_open_seconds = 30

    def detect(self, screenshot_path: str) -> List[DetectionResult]:
        """调用 sidecar 服务检测。"""
        # 检查熔断器
        if time.time() < self._circuit_open_until:
            return []

        try:
            with open(screenshot_path, "rb") as f:
                files = {"image": f}
                resp = requests.post(
                    f"{self.url}/v1/detect",
                    files=files,
                    timeout=self.timeout,
                )

            if resp.status_code != 200:
                self._record_failure()
                return []

            data = resp.json()

            # 重置熔断器
            self._failure_count = 0

            # 解析结果
            results = []
            for elem in data.get("elements", []):
                conf = elem.get("confidence", 0.0)
                if conf < self.min_confidence:
                    continue

                bbox = elem.get("bbox_px", [])
                if len(bbox) != 4:
                    continue

                results.append(DetectionResult(
                    kind=elem.get("kind", "unknown"),
                    bbox_px=tuple(bbox),
                    confidence=conf,
                    label=elem.get("label"),
                ))

            return results

        except (requests.RequestException, ValueError, KeyError) as e:
            self._record_failure()
            return []

    def _record_failure(self):
        """记录失败，可能触发熔断。"""
        self._failure_count += 1
        if self._failure_count >= self._max_failures:
            self._circuit_open_until = time.time() + self._circuit_open_seconds

    def get_metadata(self) -> dict:
        return {
            "name": "SidecarDetector",
            "version": "1.0.0",
            "device": "sidecar",
            "url": self.url,
        }

    def is_healthy(self) -> bool:
        """检查服务是否健康。"""
        if time.time() < self._circuit_open_until:
            return False
        try:
            resp = requests.get(f"{self.url}/healthz", timeout=2)
            return resp.status_code == 200
        except requests.RequestException:
            return False
