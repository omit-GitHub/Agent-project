# -*- coding: utf-8 -*-
"""Mock infrastructure for Harness testing.

Provides fake implementations that allow testing the Harness logic
without real device connection or VLM calls.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time


@dataclass
class MockCandidate:
    """Mock UI candidate."""
    candidate_id: str
    role: str  # e.g., "playback_speed", "delete", "payment"
    label: str = ""
    bbox: tuple = (0, 0, 100, 100)  # (x1, y1, x2, y2)
    semantic_tags: List[str] = field(default_factory=list)


@dataclass
class MockCandidateMap:
    """Mock candidate map."""
    screen_version: str
    package: str
    activity: str
    candidates: List[MockCandidate]
    created_at: float = field(default_factory=time.time)


@dataclass
class MockVLMDecision:
    """Mock VLM decision."""
    action_type: str = "tap_candidate"
    candidate_id: Optional[str] = None
    target_label: str = ""
    bbox: Optional[tuple] = None
    expected_roles: List[str] = field(default_factory=list)


@dataclass
class MockScreenFingerprint:
    """Mock screen fingerprint."""
    package: str
    activity: str
    screen_version: str


class FakeExecutor:
    """Fake executor that records calls but doesn't execute real actions."""

    def __init__(self):
        self.call_count = 0
        self.last_action = None
        self.should_fail = False

    def execute(self, action_type: str, **kwargs) -> Dict[str, Any]:
        """Record the action call."""
        self.call_count += 1
        self.last_action = {"type": action_type, **kwargs}

        if self.should_fail:
            return {"ok": False, "error": "fake_failure"}
        return {"ok": True, "detail": f"fake_{action_type}"}

    def reset(self):
        """Reset call count."""
        self.call_count = 0
        self.last_action = None


class MockVLMVerifier:
    """Mock VLM verifier that returns configurable results."""

    def __init__(self, default_result: str = "unknown"):
        self.call_count = 0
        self.default_result = default_result
        self.results_queue: List[str] = []

    def verify(self, **kwargs) -> Dict[str, Any]:
        """Return verification result."""
        self.call_count += 1

        if self.results_queue:
            result = self.results_queue.pop(0)
        else:
            result = self.default_result

        return {
            "verification": result,
            "source": "vlm",
            "reason": f"mock_vlm_{result}",
        }

    def enqueue_result(self, result: str):
        """Enqueue a verification result."""
        self.results_queue.append(result)

    def reset(self):
        """Reset call count and queue."""
        self.call_count = 0
        self.results_queue = []


def make_candidate_map(
    candidates: List[MockCandidate],
    screen_version: str = "v1|test|12345",
    package: str = "com.example.app",
    activity: str = "MainActivity",
) -> MockCandidateMap:
    """Helper to create mock candidate map."""
    return MockCandidateMap(
        screen_version=screen_version,
        package=package,
        activity=activity,
        candidates=candidates,
    )


def make_candidate(
    candidate_id: str,
    role: str,
    label: str = "",
    bbox: tuple = (100, 100, 200, 200),
    semantic_tags: Optional[List[str]] = None,
) -> MockCandidate:
    """Helper to create mock candidate."""
    return MockCandidate(
        candidate_id=candidate_id,
        role=role,
        label=label,
        bbox=bbox,
        semantic_tags=semantic_tags or [],
    )
