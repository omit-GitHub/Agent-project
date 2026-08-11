# -*- coding: utf-8 -*-
"""CLI 入口 — 交互式文字对话。

用法:
  # 方式 1: 直接运行
  python agent/main.py

  # 方式 2: 作为模块
  python -m agent.main

  # 先设置 API Key（二选一）:
  set DASHSCOPE_API_KEY=sk-xxx
  # 或复制 agent/.env.example 为 agent/.env 并填入

特殊命令:
  /state     — 查看设备状态
  /commands  — 列出可用命令
  /reset     — 重置对话
  /stats     — 查看统计信息
  /debug     — 切换调试模式
  /quit      — 退出
"""
import sys
import os
import json

# 确保项目根目录在 path 中（以便 import agent）
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from agent import config
from agent.agent import VideoAgent


def print_banner():
    """打印欢迎信息。"""
    print()
    print("=" * 56)
    print("  🎬 GUIAgent 智能视频助手")
    print("   Powered by 通义千问 (DashScope)")
    print("=" * 56)
    print()
    print(f"  设备地址: {config.DEVICE_URL}")
    print(f"  模型:     {config.MODEL_NAME}")
    print()
    print("  输入 /help 查看帮助，/quit 退出")
    print("-" * 56)
    print()


def print_help():
    """打印帮助信息。"""
    print("""
  特殊命令:
    /state     — 查看设备当前状态
    /commands  — 列出所有可用命令
    /reset     — 重置对话（清空上下文）
    /stats     — 查看对话统计
    /debug     — 切换调试模式（显示命令调用详情）
    /help      — 显示此帮助
    /quit      — 退出

  对话示例:
    > 帮我暂停播放
    > 声音大一点
    > 现在在放什么
    > 切到第3集
    > 1.5倍速
    > 搜索庆余年
    > 打开腾讯视频
""")


def handle_special_command(agent, cmd):
    """处理 / 开头的特殊命令。返回 True 表示已处理。"""
    cmd = cmd.strip().lower()

    if cmd in ("/quit", "/exit", "/q"):
        print("\n  👋 再见！\n")
        sys.exit(0)

    elif cmd == "/state":
        print("\n  📺 查询设备状态...")
        result = agent.get_device_state()
        if result.get("ok"):
            data = result.get("data", {})
            pkg = data.get("pkg", "未知")
            summary = data.get("summary", [])
            print(f"  前台应用: {pkg}")
            if summary:
                print(f"  页面内容: {', '.join(str(s) for s in summary[:8])}")
            else:
                print("  页面内容: (无可见文本)")
        else:
            err = result.get("error", {})
            print(f"  ❌ {err.get('code')}: {err.get('message')}")
        print()
        return True

    elif cmd == "/commands":
        print(f"\n  📋 可用命令 ({len(agent.available_commands)} 个):")
        for cmd_name in agent.available_commands:
            from agent.commands import get_command_description
            desc = get_command_description(cmd_name)
            print(f"    • {cmd_name}")
            if desc != cmd_name:
                print(f"      {desc}")
        print()
        return True

    elif cmd == "/reset":
        agent.reset()
        print("\n  🔄 对话已重置\n")
        return True

    elif cmd == "/stats":
        stats = agent.get_stats()
        print(f"\n  📊 统计信息:")
        print(f"    对话轮数:     {stats['total_turns']}")
        print(f"    命令调用次数: {stats['total_tool_calls']}")
        print(f"    历史记录长度: {stats['history_length']}")
        print(f"    可用命令数:   {stats['available_commands']}")
        print()
        return True

    elif cmd == "/debug":
        config.DEBUG = not config.DEBUG
        status = "开启" if config.DEBUG else "关闭"
        print(f"\n  🔧 调试模式已{status}\n")
        return True

    elif cmd == "/help":
        print_help()
        return True

    return False


def main():
    """主循环。"""
    print_banner()

    # 检查 API Key
    if not config.DASHSCOPE_API_KEY:
        print("  ❌ 错误: 未配置 DASHSCOPE_API_KEY")
        print()
        print("  请通过以下方式之一配置:")
        print("    1. 设置环境变量: set DASHSCOPE_API_KEY=sk-xxx")
        print("    2. 创建 agent/.env 文件: DASHSCOPE_API_KEY=sk-xxx")
        print("    3. 复制 agent/.env.example 为 agent/.env 并填入 Key")
        print()
        sys.exit(1)

    # 初始化 Agent
    try:
        agent = VideoAgent()
    except ValueError as e:
        print(f"  ❌ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"  ❌ 初始化失败: {e}")
        print("  请确认设备 HTTP 服务已启动 (python server.py)")
        sys.exit(1)

    print(f"  ✅ 已连接设备，{len(agent.available_commands)} 个命令可用")
    print(f"  ✅ 模型: {config.MODEL_NAME}")
    print()

    # 先获取一次设备状态
    state = agent.get_device_state()
    if state.get("ok"):
        pkg = state.get("data", {}).get("pkg", "")
        if pkg:
            print(f"  📺 当前设备: {pkg}")
        else:
            print("  ⚠️  设备已连接但无活跃窗口")
    else:
        print("  ⚠️  设备未响应（命令仍可尝试执行）")
    print()

    # 主循环
    while True:
        try:
            user_input = input("  👤 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n  👋 再见！\n")
            break

        if not user_input:
            continue

        # 处理特殊命令
        if user_input.startswith("/"):
            if handle_special_command(agent, user_input):
                continue

        # 正常对话
        try:
            if config.DEBUG:
                print(f"  [调试] 用户输入: {user_input}")

            reply = agent.chat(user_input)

            if config.DEBUG:
                stats = agent.get_stats()
                print(f"  [调试] 总轮数={stats['total_turns']}, "
                      f"总调用={stats['total_tool_calls']}")

            print(f"  🤖 > {reply}")
            print()

        except Exception as e:
            print(f"  ❌ 错误: {e}")
            if config.DEBUG:
                import traceback
                traceback.print_exc()
            print()


if __name__ == "__main__":
    main()
