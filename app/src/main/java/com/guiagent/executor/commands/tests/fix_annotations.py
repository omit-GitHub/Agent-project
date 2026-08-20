#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复标注问题"""
import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


def main():
    manifest_path = "./data/screenshots/manifest.jsonl"

    # 读取
    entries = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))

    # 修复
    fixes = {
        6: {"control_bar_visible": "hidden"},   # grid 页面
        7: {"control_bar_visible": "hidden"},   # detail 页面
        12: {"control_bar_visible": "hidden"},  # list 页面
        15: {"control_bar_visible": "hidden"},  # grid 页面
        19: {"control_bar_visible": "visible"}, # player 页面
        27: {"control_bar_visible": "visible"}, # player 页面
        37: {"control_bar_visible": "hidden"},  # player 页面（可能是广告）
        38: {"control_bar_visible": "hidden"},  # player 页面
    }

    fixed_count = 0
    for i, entry in enumerate(entries, 1):
        if i in fixes:
            for key, value in fixes[i].items():
                old_value = entry.get(key, "")
                entry[key] = value
                print(f"[{i:2}] {entry.get('filename', '')}: {key} {old_value} -> {value}")
            fixed_count += 1

    # 写回
    with open(manifest_path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print()
    print(f"修复完成: {fixed_count} 张截图")


if __name__ == "__main__":
    main()
