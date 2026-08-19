#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中屏截图采集工具 — Phase B0 数据集构建

用法:
    python collect_screenshots.py --output ./data/screenshots --count 150

功能:
    1. 自动截图并保存到指定目录
    2. 记录截图元信息（时间、App、页面类型）
    3. 支持手动标记场景类别

目标数据集:
    - 100-200 张真实中屏截图
    - 覆盖：爱奇艺/腾讯/夸克
    - 场景：player/detail/list/grid/dialog
    - 状态：控制条显隐、纯图标、小图标、广告、主题变化
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def get_adb_cmd(serial: str = None) -> list:
    """构建 adb 命令前缀。"""
    cmd = ["adb"]
    if serial:
        cmd.extend(["-s", serial])
    elif os.environ.get("ANDROID_SERIAL"):
        cmd.extend(["-s", os.environ["ANDROID_SERIAL"]])
    return cmd


def get_foreground_app(adb_cmd: list) -> dict:
    """获取当前前台 App 信息。"""
    try:
        # 方法 1: dumpsys activity
        result = subprocess.run(
            adb_cmd + ["shell", "dumpsys", "activity", "activities"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if "mResumedActivity" in line:
                    # 解析: mResumedActivity: ActivityRecord{xxx u0 com.tencent.qqlive/.audiobox.PlayerActivity}
                    parts = line.strip().split()
                    if len(parts) >= 4:
                        app_info = parts[-1]  # com.tencent.qqlive/.audiobox.PlayerActivity
                        if "/" in app_info:
                            package, activity = app_info.split("/", 1)
                            return {"package": package, "activity": activity}
    except Exception as e:
        print(f"[警告] 获取前台 App 失败: {e}", file=sys.stderr)
    return {"package": "unknown", "activity": "unknown"}


def capture_screenshot(adb_cmd: list, output_path: str) -> bool:
    """截取当前屏幕并保存。"""
    try:
        # 截图到设备
        result = subprocess.run(
            adb_cmd + ["shell", "screencap", "-p", "/sdcard/screenshot.png"],
            capture_output=True, timeout=10
        )
        if result.returncode != 0:
            return False

        # 拉取到本地
        result = subprocess.run(
            adb_cmd + ["pull", "/sdcard/screenshot.png", output_path],
            capture_output=True, timeout=10
        )
        return result.returncode == 0
    except Exception as e:
        print(f"[错误] 截图失败: {e}", file=sys.stderr)
        return False


def get_user_input(prompt: str, options: list = None) -> str:
    """获取用户输入（带选项提示）。"""
    if options:
        print(f"\n{prompt}")
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt}")
        while True:
            try:
                choice = int(input("选择 (数字): ").strip())
                if 1 <= choice <= len(options):
                    return options[choice - 1]
            except ValueError:
                pass
    else:
        return input(f"{prompt}: ").strip()


def main():
    parser = argparse.ArgumentParser(description="中屏截图采集工具")
    parser.add_argument("--output", default="./data/screenshots", help="输出目录")
    parser.add_argument("--count", type=int, default=150, help="目标截图数量")
    parser.add_argument("--serial", help="ADB 设备序列号")
    parser.add_argument("--auto", action="store_true", help="自动模式（不询问场景类别）")
    args = parser.parse_args()

    # 创建输出目录
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 元信息文件
    manifest_path = output_dir / "manifest.jsonl"
    manifest_file = open(manifest_path, "a", encoding="utf-8")

    adb_cmd = get_adb_cmd(args.serial)

    # 场景类别
    page_types = ["player", "detail", "search", "list", "grid", "dialog", "overlay", "unknown"]
    control_bar_states = ["visible", "hidden", "unknown"]
    special_tags = ["none", "pure_icon", "small_icon", "ad", "dark_theme", "light_theme"]

    print("=" * 60)
    print("中屏截图采集工具 — Phase B0")
    print("=" * 60)
    print(f"输出目录: {output_dir}")
    print(f"目标数量: {args.count}")
    print(f"自动模式: {args.auto}")
    print()
    print("按 Ctrl+C 停止采集")
    print()

    collected = 0
    try:
        while collected < args.count:
            # 截图
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screen_{timestamp}_{collected:03d}.png"
            output_path = output_dir / filename

            print(f"[{collected + 1}/{args.count}] 截图...", end=" ")
            if not capture_screenshot(adb_cmd, str(output_path)):
                print("失败")
                continue
            print("成功")

            # 获取前台 App
            app_info = get_foreground_app(adb_cmd)

            # 场景标记
            if args.auto:
                page_type = "unknown"
                control_bar = "unknown"
                tags = ["none"]
            else:
                page_type = get_user_input("页面类型", page_types)
                control_bar = get_user_input("控制条状态", control_bar_states)
                tags_input = get_user_input("特殊标签（逗号分隔）", special_tags)
                tags = [t.strip() for t in tags_input.split(",") if t.strip()]

            # 记录元信息
            metadata = {
                "filename": filename,
                "timestamp": timestamp,
                "package": app_info.get("package", "unknown"),
                "activity": app_info.get("activity", "unknown"),
                "page_type": page_type,
                "control_bar_visible": control_bar,
                "tags": tags,
                "width": 1280,  # 默认中屏分辨率
                "height": 800,
            }

            manifest_file.write(json.dumps(metadata, ensure_ascii=False) + "\n")
            manifest_file.flush()

            collected += 1
            print(f"  已保存: {filename}")
            print(f"  App: {metadata['package']}/{metadata['activity']}")
            print(f"  场景: {page_type} | 控制条: {control_bar} | 标签: {','.join(tags)}")
            print()

            # 等待用户准备下一张
            if not args.auto and collected < args.count:
                input("按 Enter 继续下一张截图...")

    except KeyboardInterrupt:
        print("\n\n采集已停止")
    finally:
        manifest_file.close()

    print()
    print("=" * 60)
    print(f"采集完成: {collected} 张截图")
    print(f"输出目录: {output_dir}")
    print(f"元信息: {manifest_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
