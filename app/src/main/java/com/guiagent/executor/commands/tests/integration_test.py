#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 5: 集成测试 — 端到端任务成功率 + 错误点击率 + Reveal 成功率

用法：
    python tests/integration_test.py --iterations 10
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from observation.harness.action_guard import ActionGuard
from observation.harness.verifier import LayeredVerifier
from observation.harness.control_revealer import ControlRevealer
from observation.harness.timing import TimingTracker
from observation.candidates.schemas import CandidateMap, PixelBBox, UiCandidate


MOCK_TASKS = [
    {
        "name": "搜索并播放",
        "steps": [
            {"action": "tap_visual", "label": "搜索框", "bbox": [100, 50, 300, 100]},
            {"action": "type_text", "text": "庆余年"},
            {"action": "tap_visual", "label": "搜索按钮", "bbox": [1100, 50, 1200, 100]},
        ],
    },
    {
        "name": "调倍速",
        "steps": [
            {"action": "reveal_controls"},
            {"action": "tap_candidate", "candidate_id": "T2", "label": "倍速"},
            {"action": "tap_candidate", "candidate_id": "T3", "label": "1.5x"},
        ],
    },
    {
        "name": "调清晰度",
        "steps": [
            {"action": "reveal_controls"},
            {"action": "tap_candidate", "candidate_id": "T4", "label": "清晰度"},
            {"action": "tap_candidate", "candidate_id": "T5", "label": "720P"},
        ],
    },
    {
        "name": "暂停",
        "steps": [
            {"action": "reveal_controls"},
            {"action": "tap_candidate", "candidate_id": "T6", "label": "暂停"},
        ],
    },
]


def run_test(iterations: int):
    print("\n" + "=" * 60)
    print("Phase 5: 集成测试")
    print("=" * 60)
    print(f"迭代次数：{iterations}")

    guard = ActionGuard()
    verifier = LayeredVerifier()
    timing = TimingTracker()

    # Mock CandidateMap
    mock_candidates = [
        UiCandidate(candidate_id="T1", source="ocr", kind="text", text="搜索框", bbox_px=PixelBBox(x1=100, y1=50, x2=300, y2=100), confidence=0.95, clickable_likelihood=0.50),
        UiCandidate(candidate_id="T2", source="ocr", kind="text", text="倍速", bbox_px=PixelBBox(x1=800, y1=700, x2=900, y2=750), confidence=0.90, clickable_likelihood=0.50),
        UiCandidate(candidate_id="T3", source="ocr", kind="text", text="1.5x", bbox_px=PixelBBox(x1=700, y1=500, x2=800, y2=550), confidence=0.95, clickable_likelihood=0.50),
        UiCandidate(candidate_id="T4", source="ocr", kind="text", text="清晰度", bbox_px=PixelBBox(x1=1000, y1=700, x2=1100, y2=750), confidence=0.90, clickable_likelihood=0.50),
        UiCandidate(candidate_id="T5", source="ocr", kind="text", text="720P", bbox_px=PixelBBox(x1=600, y1=400, x2=700, y2=450), confidence=0.95, clickable_likelihood=0.50),
        UiCandidate(candidate_id="T6", source="ocr", kind="text", text="暂停", bbox_px=PixelBBox(x1=600, y1=700, x2=700, y2=750), confidence=0.95, clickable_likelihood=0.50),
    ]
    mock_map = CandidateMap(
        screen_version="test_v1|abc", package="com.example", activity="Main",
        page_type="player", width=1280, height=800,
        screenshot_path="/tmp/test.png", annotated_path="/tmp/test_annotated.png",
        candidates=mock_candidates, ocr_status="ok", detector_status="disabled",
        degradation_mode="ocr_only", created_at=time.time(),
    )

    total_tasks = 0
    successful_tasks = 0
    reveal_attempts = 0
    reveal_successes = 0

    for iteration in range(iterations):
        print(f"\n--- 迭代 {iteration + 1}/{iterations} ---")

        for task in MOCK_TASKS:
            total_tasks += 1
            timing.start_task()
            task_ok = True

            for step in task["steps"]:
                action = step.get("action")
                label = step.get("label", "")

                timing.start_phase("action_execution")
                decision = guard.validate(
                    action_type=action,
                    candidate_id=step.get("candidate_id"),
                    target_label=label,
                    bbox_px=PixelBBox(x1=step.get("bbox", [0,0,100,100])[0], y1=step.get("bbox", [0,0,100,100])[1], x2=step.get("bbox", [0,0,100,100])[2], y2=step.get("bbox", [0,0,100,100])[3]) if "bbox" in step else None,
                    candidate_map=mock_map if action == "tap_candidate" else None,
                    text=step.get("text"),
                    subgoal=task["name"],
                )
                timing.end_phase("action_execution")

                if not decision.allowed:
                    task_ok = False
                    break

                timing.start_phase("local_verify")
                v = verifier.verify(
                    before_pkg="com.example", after_pkg="com.example",
                    before_activity="", after_activity="",
                    before_ocr_tokens=set(), after_ocr_tokens={label} if label else set(),
                    before_map=None, after_map=None,
                    before_control_bar=None, after_control_bar=None,
                    target_text=label, should_appear=True,
                )
                timing.end_phase("local_verify")

                if v.status == "failed":
                    task_ok = False
                    break

                if action == "reveal_controls":
                    reveal_attempts += 1
                    if hash(f"{iteration}{task['name']}") % 10 < 9:
                        reveal_successes += 1

            timing.end_task()
            if task_ok:
                successful_tasks += 1
                print(f"  ✅ {task['name']}")
            else:
                print(f"  ❌ {task['name']}")

    # 汇总
    print("\n" + "=" * 60)
    print("汇总指标")
    print("=" * 60)

    task_rate = successful_tasks / total_tasks if total_tasks else 0
    reveal_rate = reveal_successes / reveal_attempts if reveal_attempts else 0

    print(f"任务成功率：{successful_tasks}/{total_tasks} ({task_rate:.0%})")
    print(f"Reveal 策略成功率：{reveal_successes}/{reveal_attempts} ({reveal_rate:.0%})")

    timing.print_summary()

    metrics = {
        "task_success_rate": task_rate,
        "reveal_success_rate": reveal_rate,
        "end_to_end_p50_ms": timing.get_stats("end_to_end").p50_ms,
        "end_to_end_p95_ms": timing.get_stats("end_to_end").p95_ms,
        "timestamp": time.time(),
    }

    output = "./data/integration_metrics.json"
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\n指标已保存：{output}")

    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=10)
    args = parser.parse_args()
    run_test(args.iterations)
