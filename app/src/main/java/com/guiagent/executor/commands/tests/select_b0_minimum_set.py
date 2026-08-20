#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从现有截图中选取 30 张 B0 最小标注集。

选取策略:
  1. 按 page_type 分组
  2. 每组抽取 3-5 张
  3. 优先覆盖不同 App 和场景
"""
import json
import random
from pathlib import Path
from collections import defaultdict

random.seed(42)  # 可复现


def select_b0_screenshots(manifest_path: str, output_path: str, target_count: int = 30):
    """选取 B0 标注集。"""
    # 读取 manifest
    screenshots = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                screenshots.append(json.loads(line))

    # 按 page_type 分组
    groups = defaultdict(list)
    for s in screenshots:
        page_type = s.get("page_type", "unknown")
        groups[page_type].append(s)

    # 每组抽取
    selected = []
    per_group = target_count // len(groups) + 1

    for page_type, items in groups.items():
        # 随机抽取
        sample = random.sample(items, min(per_group, len(items)))
        selected.extend(sample)
        print(f"  {page_type}: {len(items)} 张 -> 选取 {len(sample)} 张")

    # 如果不够，从大组补充
    if len(selected) < target_count:
        remaining = target_count - len(selected)
        all_items = [s for s in screenshots if s not in selected]
        if len(all_items) >= remaining:
            extra = random.sample(all_items, remaining)
            selected.extend(extra)
            print(f"  补充：{len(extra)} 张")

    # 限制总数
    selected = selected[:target_count]

    # 保存选取结果
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(selected, f, ensure_ascii=False, indent=2)

    print(f"\n总计选取：{len(selected)} 张")
    print(f"输出：{output_path}")

    # 打印覆盖情况
    print("\n场景覆盖:")
    coverage = defaultdict(int)
    for s in selected:
        page_type = s.get("page_type", "unknown")
        coverage[page_type] += 1
    for page_type, count in sorted(coverage.items(), key=lambda x: -x[1]):
        print(f"  {page_type}: {count} 张")


if __name__ == "__main__":
    manifest_path = "./data/screenshots/manifest.jsonl"
    output_path = "./data/b0_minimum_set.json"
    select_b0_screenshots(manifest_path, output_path, target_count=30)
