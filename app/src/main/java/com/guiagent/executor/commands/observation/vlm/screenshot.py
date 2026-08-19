# -*- coding: utf-8 -*-
"""截图模块 — 从设备截取当前屏幕。

对应 Cursor 任务书 §5.1。
复用 adb screencap 命令，返回本地 PNG 路径和屏幕尺寸。
"""
import hashlib
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import Optional


class ScreenshotError(Exception):
    """截图失败时抛出。"""
    pass


@dataclass
class Screenshot:
    """截图结果。"""
    path: str           # 本地 PNG 文件路径
    width: int          # 屏幕宽度（像素）
    height: int         # 屏幕高度（像素）
    sha256: str         # 文件 hash（用于去重）
    captured_at: float  # 截图时间戳


def capture_screenshot(
    output_dir: str = "./runtime/screenshots",
    request_id: Optional[str] = None,
) -> Screenshot:
    """截取当前设备屏幕。

    Args:
        output_dir: 截图保存目录（自动创建）
        request_id: 请求 ID（用于文件名）；为 None 时用时间戳

    Returns:
        Screenshot 对象

    Raises:
        ScreenshotError: 截图失败时
    """
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    # 生成文件名
    ts = time.strftime("%Y%m%d_%H%M%S")
    rid = request_id or ts
    filename = f"screenshot_{ts}_{rid}.png"
    output_path = os.path.join(output_dir, filename)

    # 执行 adb screencap
    try:
        result = subprocess.run(
            ["adb", "exec-out", "screencap", "-p"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise ScreenshotError(
                f"adb screencap failed: {result.stderr.decode('utf-8', errors='replace')}"
            )
        if not result.stdout:
            raise ScreenshotError("adb screencap returned empty output")

        # 写入文件
        with open(output_path, "wb") as f:
            f.write(result.stdout)

    except subprocess.TimeoutExpired:
        raise ScreenshotError("adb screencap timed out (10s)")
    except FileNotFoundError:
        raise ScreenshotError("adb not found in PATH")

    # 计算 hash
    sha256 = hashlib.sha256(result.stdout).hexdigest()

    # 获取屏幕尺寸（从 ping 命令或默认值）
    width, height = _get_screen_size()

    return Screenshot(
        path=output_path,
        width=width,
        height=height,
        sha256=sha256,
        captured_at=time.time(),
    )


def _get_screen_size() -> tuple[int, int]:
    """获取屏幕尺寸（从 adb 或默认值）。"""
    try:
        result = subprocess.run(
            ["adb", "shell", "wm", "size"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode == 0:
            # 输出格式: "Physical size: 1280x800"
            output = result.stdout.decode("utf-8", errors="replace")
            for line in output.strip().split("\n"):
                if "Physical size" in line:
                    size_str = line.split(":")[-1].strip()
                    w, h = map(int, size_str.split("x"))
                    return w, h
    except Exception:
        pass
    # 默认值（中屏盒常见分辨率）
    return 1280, 800
