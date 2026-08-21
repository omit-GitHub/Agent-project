#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase B0: 计算 Detector 召回率。

对比 detector 检测结果与 ground truth（红框标注），计算：
  - 总体召回率 (>= 0.90 通过)
  - 纯图标召回率 (>= 0.85 通过)

IoU 匹配：检测框与 GT 框 IoU >= 0.3 视为命中。

用法:
    python tests/phase_b0_recall.py --gt ./data/b0_ground_truth.json --detector opencv
"""
import json
import sys
import os
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from observation.detector import create_detector


def calc_iou(box1: list, box2: list) -> float:
    """计算两个 bbox 的 IoU。"""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    if x2 <= x1 or y2 <= y1:
        return 0.0

    intersection = (x2 - x1) * (y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - intersection

    return intersection / union if union > 0 else 0.0


def is_icon(gt_bbox: list) -> bool:
    """判断 GT 框是否是纯图标（小尺寸，近似方形）。"""
    w = gt_bbox[2] - gt_bbox[0]
    h = gt_bbox[3] - gt_bbox[1]
    area = w * h
    aspect = w / h if h > 0 else 0
    # 图标：小尺寸 (< 5000px), 近似方形 (0.5 < ratio < 2.0)
    return area < 5000 and 0.5 < aspect < 2.0


def evaluate(gt_annotations: list, screenshot_dir: str, detector, iou_threshold: float = 0.3):
    """评估 detector 召回率。"""
    total_gt = 0
    matched_gt = 0
    total_icon_gt = 0
    matched_icon_gt = 0
    total_detections = 0
    per_image_results = []

    for ann in gt_annotations:
        screenshot_name = ann["screenshot"]
        gt_boxes = [a["bbox"] for a in ann["annotations"]]
        screenshot_path = os.path.join(screenshot_dir, screenshot_name)

        if not Path(screenshot_path).exists():
            continue

        # 运行 detector
        start = time.time()
        detections = detector.detect(screenshot_path)
        latency_ms = (time.time() - start) * 1000

        det_boxes = [list(d.bbox_px) for d in detections]
        total_detections += len(det_boxes)

        # 匹配 GT
        image_matched = 0
        image_icon_matched = 0
        image_gt_count = len(gt_boxes)
        image_icon_count = sum(1 for b in gt_boxes if is_icon(b))

        for gt_box in gt_boxes:
            best_iou = 0.0
            for det_box in det_boxes:
                iou = calc_iou(gt_box, det_box)
                if iou > best_iou:
                    best_iou = iou

            if best_iou >= iou_threshold:
                matched_gt += 1
                image_matched += 1
                if is_icon(gt_box):
                    matched_icon_gt += 1
                    image_icon_matched += 1

        total_gt += image_gt_count
        total_icon_gt += image_icon_count

        per_image_results.append({
            "screenshot": screenshot_name,
            "gt_count": image_gt_count,
            "matched": image_matched,
            "icon_gt": image_icon_count,
            "icon_matched": image_icon_matched,
            "detection_count": len(det_boxes),
            "recall": image_matched / image_gt_count if image_gt_count > 0 else 0,
            "latency_ms": latency_ms,
        })

    # 汇总
    overall_recall = matched_gt / total_gt if total_gt > 0 else 0
    icon_recall = matched_icon_gt / total_icon_gt if total_icon_gt > 0 else 0

    return {
        "total_gt": total_gt,
        "matched_gt": matched_gt,
        "overall_recall": overall_recall,
        "total_icon_gt": total_icon_gt,
        "matched_icon_gt": matched_icon_gt,
        "icon_recall": icon_recall,
        "total_detections": total_detections,
        "avg_detections_per_image": total_detections / len(gt_annotations) if gt_annotations else 0,
        "per_image": per_image_results,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Phase B0 召回率计算")
    parser.add_argument("--gt", default="./data/b0_ground_truth.json", help="Ground truth 文件")
    parser.add_argument("--screenshots", default="./data/screenshots/", help="截图目录")
    parser.add_argument("--detector", default="opencv", help="detector 类型")
    parser.add_argument("--iou", type=float, default=0.3, help="IoU 阈值")
    args = parser.parse_args()

    # 加载 GT
    with open(args.gt, "r", encoding="utf-8") as f:
        gt_annotations = json.load(f)

    print(f"GT 标注：{len(gt_annotations)} 张截图")

    # 创建 detector
    os.environ["DETECTOR_TYPE"] = args.detector
    detector = create_detector()
    print(f"Detector: {detector.get_metadata()}")
    print(f"IoU 阈值：{args.iou}")
    print()

    # 评估
    results = evaluate(gt_annotations, args.screenshots, detector, args.iou)

    # 输出结果
    print("=" * 60)
    print("Phase B0 召回率实验结果")
    print("=" * 60)

    print(f"\n总体召回率:")
    print(f"  GT 总数：{results['total_gt']}")
    print(f"  命中数：{results['matched_gt']}")
    print(f"  召回率：{results['overall_recall']:.1%} (目标 >= 90%)")
    print(f"  判定：{'[PASS]' if results['overall_recall'] >= 0.90 else '[FAIL]'}")

    print(f"\n纯图标召回率:")
    print(f"  图标 GT 总数：{results['total_icon_gt']}")
    print(f"  图标命中数：{results['matched_icon_gt']}")
    print(f"  图标召回率：{results['icon_recall']:.1%} (目标 >= 85%)")
    print(f"  判定：{'[PASS]' if results['icon_recall'] >= 0.85 else '[FAIL]'}")

    print(f"\n检测统计:")
    print(f"  总检测数：{results['total_detections']}")
    print(f"  平均每图：{results['avg_detections_per_image']:.1f}")

    # 保存
    output = {
        "detector": detector.get_metadata(),
        "iou_threshold": args.iou,
        "overall_recall": results["overall_recall"],
        "icon_recall": results["icon_recall"],
        "overall_pass": results["overall_recall"] >= 0.90,
        "icon_pass": results["icon_recall"] >= 0.85,
        "per_image": results["per_image"],
    }

    output_path = "./data/b0_recall_results.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存：{output_path}")


if __name__ == "__main__":
    main()
