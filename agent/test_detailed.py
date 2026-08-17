# -*- coding: utf-8 -*-
"""详细测试 Agent 的工具调用"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.agent import VideoAgent

def test_detailed_calls():
    """测试并显示详细的工具调用"""
    print("=" * 60)
    print("详细工具调用测试")
    print("=" * 60)

    agent = VideoAgent()

    # 测试点击操作
    print("\n用户: 点击游戏频道")
    reply = agent.chat("点击游戏频道")
    print(f"Agent: {reply}")

    # 分析工具调用
    print("\n" + "=" * 60)
    print("工具调用详情:")
    print("=" * 60)

    for i, h in enumerate(agent.history):
        if h.get('role') == 'assistant':
            if h.get('tool_calls'):
                print(f"\n第 {i} 轮 - Assistant 调用工具:")
                for tc in h['tool_calls']:
                    func_name = tc['function']['name']
                    func_args = json.loads(tc['function']['arguments'])
                    print(f"  工具: {func_name}")
                    print(f"  参数: {json.dumps(func_args, ensure_ascii=False, indent=4)}")

            elif h.get('content'):
                # 检查是否是工具响应
                pass

        elif h.get('role') == 'tool':
            print(f"\n第 {i} 轮 - Tool 响应:")
            content = json.loads(h['content'])
            if 'data' in content:
                data = content['data']
                if 'command' in data:
                    print(f"  命令: {data['command']}")
                    if 'result' in data:
                        print(f"  结果: {data['result']}")
                    if 'element_count' in data:
                        print(f"  元素数量: {data['element_count']}")
                    if 'elements' in data:
                        print(f"  前3个元素:")
                        for elem in data['elements'][:3]:
                            print(f"    - {elem.get('label', 'N/A')} @ {elem.get('action_point', 'N/A')}")

if __name__ == "__main__":
    try:
        test_detailed_calls()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
