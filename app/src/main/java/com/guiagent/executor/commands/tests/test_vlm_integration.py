# -*- coding: utf-8 -*-
"""VLM 集成测试 — 端到端冒烟测试。

测试 vlm_execute 命令在真实设备上的表现。
"""
import sys
import io
import os
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 加载 .env
from dotenv import load_dotenv
load_dotenv(r'D:\GUIAPP-main\agent\.env')

# 确保能找到模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from observation.harness.action_loop import run_vlm_loop
from observation.vlm.screenshot import capture_screenshot


def test_vlm_observe():
    """测试 VLM 观察能力。"""
    print("=" * 60)
    print("测试 1: VLM Observe（观察当前屏幕）")
    print("=" * 60)

    shot = capture_screenshot(output_dir="./runtime/test_screenshots")
    print(f"截图: {shot.width}x{shot.height}")

    from observation.vlm.client import QwenVlmClient
    client = QwenVlmClient()

    result = client.observe(
        screenshot_path=shot.path,
        subgoal="描述当前屏幕状态",
        allowed_actions=["tap", "done", "ask_user"]
    )

    print(f"Page: {result.page_type}")
    print(f"Control bar: {result.control_bar_visible}")
    print(f"Task: {result.task_status}")
    print(f"Action: {result.next_action.type} -> {result.next_action.target_label}")
    print(f"Confidence: {result.confidence}")
    print(f"Evidence: {result.target_evidence[:100]}")

    assert result.page_type in ["player", "detail", "search", "list", "grid", "dialog", "overlay", "unknown"]
    assert result.next_action is not None
    assert 0.0 <= result.confidence <= 1.0

    print("✅ 测试 1 通过\n")


def test_vlm_verify():
    """测试 VLM 验证能力。"""
    print("=" * 60)
    print("测试 2: VLM Verify（验证动作结果）")
    print("=" * 60)

    shot = capture_screenshot(output_dir="./runtime/test_screenshots")
    print(f"截图: {shot.width}x{shot.height}")

    from observation.vlm.client import QwenVlmClient
    client = QwenVlmClient()

    result = client.verify(
        screenshot_path=shot.path,
        subgoal="测试验证",
        action={"type": "tap", "target_label": "测试按钮"},
        expected="屏幕正常显示"
    )

    print(f"Verification: {result.verification}")
    print(f"Reason: {result.reason}")

    assert result.verification in ["success", "not_yet", "failed", "unknown"]

    print("✅ 测试 2 通过\n")


def test_action_guard():
    """测试 Action Guard。"""
    print("=" * 60)
    print("测试 3: Action Guard（动作校验）")
    print("=" * 60)

    from observation.vlm.schemas import NextAction, BBox
    from observation.harness.action_guard import validate_action

    # 合法动作
    action = NextAction(
        type="tap",
        target_label="播放",
        bbox_normalized=BBox(x1=0.4, y1=0.4, x2=0.6, y2=0.6)
    )
    decision = validate_action(action, 1280, 800, "点击播放")
    print(f"合法 tap: allowed={decision.allowed}")
    assert decision.allowed

    # 缺失 label
    action = NextAction(type="tap", bbox_normalized=BBox(x1=0.4, y1=0.4, x2=0.6, y2=0.6))
    decision = validate_action(action, 1280, 800, "测试")
    print(f"缺失 label: allowed={decision.allowed}, error={decision.error_code}")
    assert not decision.allowed
    assert decision.error_code == "MISSING_TARGET_LABEL"

    # 敏感区域
    action = NextAction(
        type="tap",
        target_label="按钮",
        bbox_normalized=BBox(x1=0.4, y1=0.92, x2=0.6, y2=0.98)
    )
    decision = validate_action(action, 1280, 800, "测试")
    print(f"敏感区域: allowed={decision.allowed}, error={decision.error_code}")
    assert not decision.allowed
    assert decision.error_code == "SENSITIVE_ZONE"

    print("✅ 测试 3 通过\n")


def test_screenshot():
    """测试截图功能。"""
    print("=" * 60)
    print("测试 4: 截图功能")
    print("=" * 60)

    shot = capture_screenshot(output_dir="./runtime/test_screenshots")
    print(f"路径: {shot.path}")
    print(f"尺寸: {shot.width}x{shot.height}")
    print(f"Hash: {shot.sha256[:16]}...")

    assert os.path.exists(shot.path)
    assert shot.width > 0
    assert shot.height > 0
    assert len(shot.sha256) == 64

    print("✅ 测试 4 通过\n")


if __name__ == "__main__":
    print("开始 VLM 集成测试\n")

    try:
        test_screenshot()
        test_vlm_observe()
        test_vlm_verify()
        test_action_guard()

        print("=" * 60)
        print("🎉 全部测试通过!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
