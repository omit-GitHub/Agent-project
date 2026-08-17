# -*- coding: utf-8 -*-
"""测试 Agent 的 observe_screen 和 click_element 功能"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.agent import VideoAgent

def test_observe_screen():
    """测试 observe_screen 命令"""
    print("=" * 60)
    print("测试 1: observe_screen")
    print("=" * 60)

    agent = VideoAgent()

    # 让 Agent 观察屏幕
    reply = agent.chat("看看屏幕上有什么")
    print(f"Agent 回复: {reply}")
    print()

    # 检查是否调用了 observe_screen
    last_tool_calls = [h for h in agent.history if h.get('role') == 'assistant' and h.get('tool_calls')]
    if last_tool_calls:
        print("✅ Agent 调用了工具")
        for tc in last_tool_calls[-1]['tool_calls']:
            print(f"  - {tc['function']['name']}")
    else:
        print("❌ Agent 没有调用工具")
    print()

def test_click_element():
    """测试 click_element 命令"""
    print("=" * 60)
    print("测试 2: click_element (模拟)")
    print("=" * 60)

    agent = VideoAgent()

    # 先观察
    print("步骤 1: 观察屏幕")
    reply = agent.chat("看看屏幕")
    print(f"Agent: {reply}")
    print()

    # 尝试点击（如果 Agent 识别到元素）
    print("步骤 2: 尝试点击某个元素")
    reply = agent.chat("点击第一个元素")
    print(f"Agent: {reply}")
    print()

def test_full_workflow():
    """测试完整工作流"""
    print("=" * 60)
    print("测试 3: 完整工作流")
    print("=" * 60)

    agent = VideoAgent()

    # 测试暂停播放
    print("用户: 暂停播放")
    reply = agent.chat("暂停播放")
    print(f"Agent: {reply}")
    print()

    # 检查工具调用历史
    tool_calls = []
    for h in agent.history:
        if h.get('role') == 'assistant' and h.get('tool_calls'):
            for tc in h['tool_calls']:
                tool_calls.append(tc['function']['name'])

    print("工具调用序列:")
    for i, tc in enumerate(tool_calls, 1):
        print(f"  {i}. {tc}")
    print()

    # 检查是否使用了新命令
    if 'observe_screen' in tool_calls:
        print("✅ 使用了 observe_screen")
    else:
        print("❌ 未使用 observe_screen")

    if 'click_element' in tool_calls:
        print("✅ 使用了 click_element")
    else:
        print("⚠️  未使用 click_element (可能使用了其他命令)")
    print()

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Agent 功能测试")
    print("=" * 60 + "\n")

    try:
        test_observe_screen()
        test_click_element()
        test_full_workflow()

        print("=" * 60)
        print("测试完成")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
