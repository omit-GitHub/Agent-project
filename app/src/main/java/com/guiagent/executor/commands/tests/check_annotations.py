#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""截图标注检查工具"""
import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


def main():
    data_dir = "./data/screenshots"
    manifest_path = data_dir + "/manifest.jsonl"

    print("=" * 60)
    print("截图标注检查")
    print("=" * 60)
    print()

    # 读取 manifest
    entries = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))

    print(f"总截图数: {len(entries)}")
    print()

    # 场景统计
    page_types = {}
    control_bars = {}
    tags = {}

    for e in entries:
        pt = e.get("page_type", "unknown")
        cb = e.get("control_bar_visible", "unknown")
        for tag in e.get("tags", []):
            tags[tag] = tags.get(tag, 0) + 1

        page_types[pt] = page_types.get(pt, 0) + 1
        control_bars[cb] = control_bars.get(cb, 0) + 1

    print("页面类型分布:")
    for pt, count in sorted(page_types.items(), key=lambda x: -x[1]):
        print(f"  {pt:15} {count:3} 张")

    print("\n控制条状态分布:")
    for cb, count in sorted(control_bars.items(), key=lambda x: -x[1]):
        print(f"  {cb:15} {count:3} 张")

    print("\n标签分布:")
    for tag, count in sorted(tags.items(), key=lambda x: -x[1]):
        print(f"  {tag:15} {count:3} 张")

    print()
    print("=" * 60)
    print("标注一致性检查")
    print("=" * 60)
    print()

    issues = []

    for i, e in enumerate(entries, 1):
        filename = e.get("filename", "")
        pt = e.get("page_type", "")
        cb = e.get("control_bar_visible", "")

        # 非播放器页面不应有 control_bar_visible=visible
        if pt in ("search", "list", "grid", "detail", "unknown") and cb == "visible":
            issues.append(f"[{i:2}] {filename}: {pt} 页面不应有 control_bar=visible -> 改为 hidden/unknown")

        # 播放器页面应有明确控制条状态
        if pt == "player" and cb == "unknown":
            issues.append(f"[{i:2}] {filename}: player 页面应明确控制条状态 -> 改为 visible/hidden")

    if issues:
        print(f"发现 {len(issues)} 个标注问题:\n")
        for issue in issues:
            print(f"  -> {issue}")
    else:
        print("  [OK] 所有标注通过一致性检查!")

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
