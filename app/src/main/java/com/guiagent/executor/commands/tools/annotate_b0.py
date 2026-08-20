#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""简单标注工具 — 为 B0 最小标注集创建 ground truth。

用法:
    python tools/annotate_b0.py --input ./data/b0_minimum_set.json --output ./data/b0_annotations.json

标注格式:
{
  "screenshot": "screen_XXX.png",
  "annotations": [
    {
      "bbox": [x1, y1, x2, y2],
      "kind": "icon|text_button|card|menu_item|slider",
      "high_risk": false,
      "label": "可选标签"
    }
  ]
}

由于这是半自动工具，建议：
1. 先用 detector 自动生成候选
2. 人工审核/修正候选
3. 保存为 ground truth
"""
import json
import argparse
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from observation.detector import create_detector


def auto_annotate(screenshot_path: str, detector) -> list:
    """用 detector 自动生成标注候选。"""
    results = detector.detect(screenshot_path)
    annotations = []
    for r in results:
        annotations.append({
            "bbox": list(r.bbox_px),
            "kind": r.kind,
            "confidence": r.confidence,
            "high_risk": False,  # 需要人工标记
            "label": None,
        })
    return annotations


def main():
    parser = argparse.ArgumentParser(description="B0 标注工具")
    parser.add_argument("--input", default="./data/b0_minimum_set.json", help="选取的截图列表")
    parser.add_argument("--output", default="./data/b0_annotations.json", help="标注输出")
    parser.add_argument("--detector", default="opencv", help="detector 类型")
    parser.add_argument("--auto", action="store_true", help="自动生成候选（需人工审核）")
    args = parser.parse_args()

    # 加载截图列表
    with open(args.input, "r", encoding="utf-8") as f:
        screenshots = json.load(f)

    print(f"截图数量：{len(screenshots)}")

    # 创建 detector
    import os
    os.environ["DETECTOR_TYPE"] = args.detector
    detector = create_detector()
    print(f"Detector: {detector.get_metadata()}")

    # 标注
    annotations = []
    for i, screenshot_info in enumerate(screenshots):
        screenshot_path = f"./data/screenshots/{screenshot_info['filename']}"
        if not Path(screenshot_path).exists():
            print(f"  [{i+1}] 跳过：{screenshot_info['filename']} 不存在")
            continue

        if args.auto:
            # 自动生成
            ann = auto_annotate(screenshot_path, detector)
            print(f"  [{i+1}] {screenshot_info['filename']}: {len(ann)} 个候选")
        else:
            # 人工标注（这里只是框架）
            ann = []
            print(f"  [{i+1}] {screenshot_info['filename']}: 待人工标注")

        annotations.append({
            "screenshot": screenshot_info["filename"],
            "page_type": screenshot_info.get("page_type", "unknown"),
            "annotations": ann,
        })

    # 保存
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(annotations, f, ensure_ascii=False, indent=2)

    print(f"\n标注已保存：{args.output}")
    print(f"总计：{len(annotations)} 张截图")


if __name__ == "__main__":
    main()
