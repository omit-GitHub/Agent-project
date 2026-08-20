#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase B0: Visual Detector 准入实验。

测试指标:
  1. 总体目标召回率 (>= 0.90 通过)
  2. 纯图标召回率 (>= 0.85 通过)
  3. p95 延迟 (<= 900ms 通过)
  4. 候选数 p95 (<= 40 通过)

用法:
    python tests/phase_b0_qualification.py --data ./data/screenshots --detector mock
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from observation.detector import create_detector
from observation.detector.interface import UiDetector


def run_qualification(data_dir: str, detector: UiDetector, iterations: int = 3):
    """运行准入实验。"""
    screenshots = sorted(Path(data_dir).glob("*.png"))

    if not screenshots:
        print(f"错误：未找到截图文件：{data_dir}")
        return None

    print(f"截图数量：{len(screenshots)}")
    print(f"Detector: {detector.get_metadata()}")
    print(f"迭代次数：{iterations}")
    print()

    # 统计
    total_latency_ms = []
    total_candidates = []
    total_detections = []

    for iteration in range(iterations):
        print(f"\n--- 迭代 {iteration + 1}/{iterations} ---")

        iter_latency = []
        iter_candidates = []

        for i, screenshot in enumerate(screenshots):
            start = time.time()
            results = detector.detect(str(screenshot))
            latency_ms = (time.time() - start) * 1000

            iter_latency.append(latency_ms)
            iter_candidates.append(len(results))

            if i < 5:  # 只显示前 5 个
                print(f"  [{i+1}] {screenshot.name}: {len(results)} candidates, {latency_ms:.0f}ms")

        total_latency_ms.extend(iter_latency)
        total_candidates.extend(iter_candidates)

    # 计算统计
    total_latency_ms.sort()
    total_candidates.sort()

    n = len(total_latency_ms)
    p50_latency = total_latency_ms[int(n * 0.50)] if n > 0 else 0
    p95_latency = total_latency_ms[int(n * 0.95)] if n > 0 else 0

    n_cand = len(total_candidates)
    p50_candidates = total_candidates[int(n_cand * 0.50)] if n_cand > 0 else 0
    p95_candidates = total_candidates[int(n_cand * 0.95)] if n_cand > 0 else 0

    # 输出结果
    print("\n" + "=" * 60)
    print("Phase B0 准入实验结果")
    print("=" * 60)
    print(f"\n延迟统计:")
    print(f"  p50: {p50_latency:.0f}ms")
    print(f"  p95: {p95_latency:.0f}ms (目标 <= 900ms)")
    print(f"\n候选数统计:")
    print(f"  p50: {p50_candidates}")
    print(f"  p95: {p95_candidates} (目标 <= 40)")

    # 判定
    latency_pass = p95_latency <= 900
    candidates_pass = p95_candidates <= 40

    print(f"\n判定:")
    print(f"  延迟：{'[PASS]' if latency_pass else '[FAIL]'}")
    print(f"  候选数：{'[PASS]' if candidates_pass else '[FAIL]'}")

    # 注意：召回率需要 ground truth，这里无法计算
    print(f"\n注意：召回率需要 ground truth 标注，请使用标注工具标注后重新运行")

    return {
        "detector": detector.get_metadata(),
        "screenshots": len(screenshots),
        "iterations": iterations,
        "latency_p50_ms": p50_latency,
        "latency_p95_ms": p95_latency,
        "candidates_p50": p50_candidates,
        "candidates_p95": p95_candidates,
        "latency_pass": latency_pass,
        "candidates_pass": candidates_pass,
    }


def main():
    parser = argparse.ArgumentParser(description="Phase B0 准入实验")
    parser.add_argument("--data", default="./data/screenshots", help="截图目录")
    parser.add_argument("--detector", default="mock", help="detector 类型：mock / omniparser")
    parser.add_argument("--iterations", type=int, default=3, help="迭代次数")
    args = parser.parse_args()

    # 设置 detector 类型
    os.environ["DETECTOR_TYPE"] = args.detector

    detector = create_detector()
    results = run_qualification(args.data, detector, args.iterations)

    # 保存结果
    if results:
        output_path = "./data/phase_b0_results.json"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存：{output_path}")


if __name__ == "__main__":
    main()
