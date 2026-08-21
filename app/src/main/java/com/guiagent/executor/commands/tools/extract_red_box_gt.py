#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从红框标注图中提取 ground truth 标注。

用户用红色方框标注了可点击区域。本脚本自动检测红色像素，
提取每个独立红色区域的 bbox，作为 ground truth。

用法:
    python tools/extract_red_box_gt.py --input ./data/screenshots/ --output ./data/b0_ground_truth.json
"""
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def extract_red_boxes(img_path: str, min_area: int = 50) -> list:
    """从图片中提取所有红色方框的 bbox。

    红色定义: R > 150, G < 100, B < 100
    """
    img = cv2.imread(img_path)
    if img is None:
        return []

    # 转换到 HSV 更容易检测红色
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # 红色在 HSV 中有两段（0-10 和 170-180）
    lower_red1 = np.array([0, 100, 100])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([160, 100, 100])
    upper_red2 = np.array([180, 255, 255])

    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    red_mask = mask1 | mask2

    # 膨胀连接断开的框线
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(red_mask, kernel, iterations=1)

    # 查找轮廓
    contours, _ = cv2.findContours(
        dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    bboxes = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue

        x, y, w, h = cv2.boundingRect(contour)
        # 过滤掉过大的区域（可能是背景误检）
        if w > img.shape[1] * 0.5 or h > img.shape[0] * 0.5:
            continue
        # 过滤掉过小的
        if w < 10 or h < 10:
            continue

        bboxes.append({
            "bbox": [int(x), int(y), int(x + w), int(y + h)],
            "area": int(area),
        })

    # 合并重叠的 bbox（红框可能有内外两条线）
    bboxes = _merge_overlapping(bboxes)

    return bboxes


def _merge_overlapping(bboxes: list, iou_threshold: float = 0.3) -> list:
    """合并重叠的 bbox。"""
    if not bboxes:
        return bboxes

    bboxes.sort(key=lambda b: b["area"], reverse=True)
    merged = []

    for bbox in bboxes:
        x1, y1, x2, y2 = bbox["bbox"]
        is_duplicate = False

        for existing in merged:
            ex1, ey1, ex2, ey2 = existing["bbox"]
            # 计算 IoU
            ix1 = max(x1, ex1)
            iy1 = max(y1, ey1)
            ix2 = min(x2, ex2)
            iy2 = min(y2, ey2)

            if ix2 <= ix1 or iy2 <= iy1:
                continue

            intersection = (ix2 - ix1) * (iy2 - iy1)
            union = (x2 - x1) * (y2 - y1) + (ex2 - ex1) * (ey2 - ey1) - intersection
            iou = intersection / union if union > 0 else 0

            if iou > iou_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            merged.append(bbox)

    return merged


def main():
    import argparse
    parser = argparse.ArgumentParser(description="提取红框标注为 ground truth")
    parser.add_argument("--input", default="./data/screenshots/", help="截图目录")
    parser.add_argument("--output", default="./data/b0_ground_truth.json", help="输出文件")
    parser.add_argument("--limit", type=int, default=18, help="处理前 N 张图")
    args = parser.parse_args()

    screenshots = sorted(Path(args.input).glob("*.png"))[:args.limit]
    print(f"处理截图：{len(screenshots)} 张")

    all_annotations = []
    total_boxes = 0

    for i, screenshot in enumerate(screenshots):
        bboxes = extract_red_boxes(str(screenshot))
        total_boxes += len(bboxes)
        print(f"  [{i+1}] {screenshot.name}: {len(bboxes)} 个红框")

        all_annotations.append({
            "screenshot": screenshot.name,
            "annotations": bboxes,
        })

    # 保存
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(all_annotations, f, ensure_ascii=False, indent=2)

    print(f"\n总计：{total_boxes} 个标注框")
    print(f"输出：{args.output}")


if __name__ == "__main__":
    main()
