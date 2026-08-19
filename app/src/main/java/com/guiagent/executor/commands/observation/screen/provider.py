# -*- coding: utf-8 -*-
"""截图提供者抽象和 ADB 实现。"""
import hashlib
import os
import subprocess
import time
from typing import Optional, Protocol

from .models import ScreenshotFrame


class ScreenshotProvider(Protocol):
    """截图提供者接口。"""
    def capture(self, request_id: Optional[str] = None) -> ScreenshotFrame: ...


class AdbScreenshotProvider:
    """ADB 截图实现。

    使用 ANDROID_SERIAL 环境变量指定设备，所有命令使用同一设备。
    """

    def __init__(
        self,
        output_dir: str = "./runtime/screenshots",
        serial: Optional[str] = None,
    ):
        self.output_dir = output_dir
        self.serial = serial or os.environ.get("ANDROID_SERIAL", "")
        os.makedirs(output_dir, exist_ok=True)

    def capture(self, request_id: Optional[str] = None) -> ScreenshotFrame:
        """截取当前设备屏幕。

        Returns:
            ScreenshotFrame

        Raises:
            RuntimeError: 截图失败时
        """
        # 生成文件名
        ts = time.strftime("%Y%m%d_%H%M%S")
        rid = request_id or ts
        filename = f"screenshot_{ts}_{rid}.png"
        output_path = os.path.join(self.output_dir, filename)

        # 构建 adb 命令
        cmd = ["adb"]
        if self.serial:
            cmd.extend(["-s", self.serial])
        cmd.extend(["exec-out", "screencap", "-p"])

        # 执行截图
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace")
                raise RuntimeError(f"adb screencap failed: {stderr}")
            if not result.stdout:
                raise RuntimeError("adb screencap returned empty output")

            # 写入文件
            with open(output_path, "wb") as f:
                f.write(result.stdout)

        except subprocess.TimeoutExpired:
            raise RuntimeError("adb screencap timed out (10s)")
        except FileNotFoundError:
            raise RuntimeError("adb not found in PATH")

        # 计算 hash
        sha256 = hashlib.sha256(result.stdout).hexdigest()

        # 获取屏幕尺寸（从 ping 或默认值）
        width, height = self._get_screen_size()

        return ScreenshotFrame(
            path=output_path,
            width=width,
            height=height,
            sha256=sha256,
            captured_at=time.time(),
            request_id=rid,
        )

    def _get_screen_size(self) -> tuple[int, int]:
        """获取屏幕尺寸。"""
        try:
            cmd = ["adb"]
            if self.serial:
                cmd.extend(["-s", self.serial])
            cmd.extend(["shell", "wm", "size"])

            result = subprocess.run(cmd, capture_output=True, timeout=5)
            if result.returncode == 0:
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
