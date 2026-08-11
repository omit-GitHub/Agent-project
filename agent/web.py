# -*- coding: utf-8 -*-
"""Web 聊天前端 — Flask 服务器。

用法:
  python agent/web.py

然后在浏览器打开:
  - 本机: http://localhost:5000
  - 局域网: http://<设备IP>:5000
  - 手机/平板: 同上

环境变量:
  WEB_HOST — 绑定地址（默认 0.0.0.0）
  WEB_PORT — 端口（默认 5000）
"""
import os
import sys
import json
import traceback

# 确保项目根目录在 path 中
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from flask import Flask, render_template, request, jsonify

from agent import config
from agent.agent import VideoAgent
from agent.commands import get_command_description


# ─────────────── 初始化 ───────────────

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "templates"))

# 全局 Agent 实例（单例）
agent = None


def get_agent():
    """获取或初始化 Agent 实例。"""
    global agent
    if agent is None:
        agent = VideoAgent()
    return agent


# ─────────────── 页面路由 ───────────────

@app.route("/")
def index():
    """聊天主页面。"""
    return render_template("index.html")


# ─────────────── API 路由 ───────────────

@app.route("/api/chat", methods=["POST"])
def api_chat():
    """处理用户消息，返回 Agent 回复。

    请求: {"message": "帮我暂停"}
    响应: {"reply": "好的，已为您暂停", "tool_calls": [...]}
    """
    try:
        data = request.get_json()
        if not data or "message" not in data:
            return jsonify({"error": "缺少 message 字段"}), 400

        message = data["message"].strip()
        if not message:
            return jsonify({"error": "消息不能为空"}), 400

        a = get_agent()
        reply = a.chat(message)

        # 返回回复 + 最近的 tool call 信息（前端可选展示）
        tool_info = []
        if len(a.history) >= 2:
            # 从历史中提取最近的 tool call
            for msg in reversed(a.history[:-1]):
                if msg.get("role") == "assistant" and msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        try:
                            args = json.loads(tc["function"]["arguments"])
                            cmd = args.get("command", "")
                            tool_info.append({
                                "command": cmd,
                                "description": get_command_description(cmd),
                            })
                        except Exception:
                            pass
                    break

        return jsonify({
            "reply": reply,
            "tool_calls": tool_info,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/state")
def api_state():
    """获取设备当前状态。"""
    try:
        a = get_agent()
        state = a.get_device_state()
        return jsonify(state)
    except Exception as e:
        return jsonify({"ok": False, "error": {"code": "FAILED", "message": str(e)}})


@app.route("/api/commands")
def api_commands():
    """获取可用命令列表（带描述）。"""
    try:
        a = get_agent()
        commands = []
        for cmd_name in a.available_commands:
            commands.append({
                "name": cmd_name,
                "description": get_command_description(cmd_name),
            })
        return jsonify({"commands": commands})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reset", methods=["POST"])
def api_reset():
    """重置对话历史。"""
    try:
        a = get_agent()
        a.reset()
        return jsonify({"ok": True, "message": "对话已重置"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health")
def api_health():
    """健康检查。"""
    try:
        a = get_agent()
        stats = a.get_stats()
        return jsonify({
            "ok": True,
            "agent": "running",
            "model": config.MODEL_NAME,
            "device": config.DEVICE_URL,
            "stats": stats,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


# ─────────────── 启动 ───────────────

def main():
    host = os.environ.get("WEB_HOST", "0.0.0.0")
    port = int(os.environ.get("WEB_PORT", "5000"))

    print()
    print("=" * 56)
    print("  🎬 GUIAgent Web 聊天服务")
    print("=" * 56)
    print()
    print(f"  模型:   {config.MODEL_NAME}")
    print(f"  设备:   {config.DEVICE_URL}")
    print()

    # 预初始化 Agent（检测连接问题）
    try:
        get_agent()
        print(f"  ✅ Agent 初始化成功")
    except Exception as e:
        print(f"  ⚠️  Agent 初始化失败: {e}")
        print(f"  （仍会启动 Web 服务，待连接后重试）")
    print()
    print(f"  🌐 打开浏览器访问:")
    print(f"     本机:    http://localhost:{port}")
    print(f"     局域网:  http://<本机IP>:{port}")
    print()
    print(f"  按 Ctrl+C 停止服务")
    print("-" * 56)
    print()

    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
