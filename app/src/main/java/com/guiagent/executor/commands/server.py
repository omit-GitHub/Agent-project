# -*- coding: utf-8 -*-
"""Python HTTP 服务器 — 对标 Java HttpCompoundServer。

监听端口 8765，提供:
  - POST /v1/compound — 执行复合命令（路由到 CompoundRegistry）
  - GET  /v1/health   — 健康检查（返回状态 + 可用命令列表）

使用 http.server 标准库（零外部依赖，Android/Termux 友好）。
线程模型: ThreadingHTTPServer（每个请求一个线程）。

用法:
  python server.py                 # 默认 0.0.0.0:8765
  python server.py --port 9000     # 自定义端口

环境变量:
  GUIAGENT_HTTP_PORT  — 端口号（默认 8765）
  GUIAGENT_HTTP_HOST  — 绑定地址（默认 0.0.0.0）
"""
import json
import os
import sys
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

# 确保能找到 commands/ 下的模块
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from registry import get_registry, register, execute, list_commands  # noqa: E402


# ─────────────────────── 命令注册 ───────────────────────

def register_all_commands():
    """注册所有命令到全局 registry。

    对标 Java GuiAgentService.registerAllCommands()。
    每个命令名映射到一个 handler(params) -> result_dict 函数。
    """
    # ── Common ──
    from common import cmd_get_state, cmd_go_back, cmd_go_home
    from common import cmd_volume_up, cmd_volume_down, cmd_volume_mute
    from common import cmd_launcher_search, cmd_play

    register("get_state",        cmd_get_state.run)
    register("go_back",          cmd_go_back.run)
    register("go_home",          cmd_go_home.run)
    register("volume_up",        cmd_volume_up.run)
    register("volume_down",      cmd_volume_down.run)
    register("volume_mute",      cmd_volume_mute.run)
    register("launcher_search",  cmd_launcher_search.run)
    register("play",             cmd_play.run)

    # ── AiQiyi ──
    from aiqiyi import run_toggle, run_episode, run_speed, run_resolution
    from aiqiyi import run_brightness, run_detail
    from aiqiyi import cmd_toggle_control_bar as aiqiyi_toggle_bar

    register("aiqiyi.toggle_play",          run_toggle.run)
    register("aiqiyi.next_episode",         run_episode.run_next)
    register("aiqiyi.prev_episode",         run_episode.run_prev)
    register("aiqiyi.open_episode_panel",   run_episode.run_open)
    register("aiqiyi.close_episode_panel",  run_episode.run_close)
    register("aiqiyi.scroll_episode_up",    lambda p: run_episode.run_scroll("up", p))
    register("aiqiyi.scroll_episode_down",  lambda p: run_episode.run_scroll("down", p))
    register("aiqiyi.select_episode",       run_episode.run_select)
    register("aiqiyi.set_speed",            run_speed.run)
    register("aiqiyi.set_quality",          run_resolution.run)
    register("aiqiyi.brightness_up",        lambda p: run_brightness.run_up(p))
    register("aiqiyi.brightness_down",      lambda p: run_brightness.run_down(p))
    register("aiqiyi.toggle_control_bar",   aiqiyi_toggle_bar.run)
    register("aiqiyi.open_detail",          lambda p: run_detail.run_open(p))
    register("aiqiyi.close_detail",         lambda p: run_detail.run_close(p))

    # ── Tencent ──
    from Tencent import run_toggle as tencent_toggle
    from Tencent import run_episode as tencent_episode
    from Tencent import run_speed as tencent_speed
    from Tencent import run_resolution as tencent_resolution
    from Tencent import run_detail as tencent_detail
    from Tencent import cmd_toggle_control_bar as tencent_toggle_bar
    from Tencent import cmd_brightness_up as tencent_bright_up
    from Tencent import cmd_brightness_down as tencent_bright_down

    register("tencent.toggle_play",          tencent_toggle.run)
    register("tencent.next_episode",         tencent_episode.run_next)
    register("tencent.prev_episode",         tencent_episode.run_prev)
    register("tencent.open_episode_panel",   tencent_episode.run_open)
    register("tencent.close_episode_panel",  tencent_episode.run_close)
    register("tencent.scroll_episode_up",    lambda p: tencent_episode.run_scroll("up", p))
    register("tencent.scroll_episode_down",  lambda p: tencent_episode.run_scroll("down", p))
    register("tencent.select_episode",       tencent_episode.run_select)
    register("tencent.set_speed",            tencent_speed.run)
    register("tencent.set_quality",          tencent_resolution.run)
    register("tencent.brightness_up",        lambda p: tencent_bright_up.run(p))
    register("tencent.brightness_down",      lambda p: tencent_bright_down.run(p))
    register("tencent.toggle_control_bar",   tencent_toggle_bar.run)
    register("tencent.open_detail",          lambda p: tencent_detail.run_open(p))

    # ── Quark ──
    from quark import cmd_launch_app, cmd_click_navigation
    from quark import cmd_scroll_up, cmd_scroll_down
    from quark import cmd_select_file, cmd_go_back, cmd_search

    register("quark.launch_app",           cmd_launch_app.run)
    register("quark.click_navigation",     cmd_click_navigation.run)
    register("quark.scroll_up",            cmd_scroll_up.run)
    register("quark.scroll_down",          cmd_scroll_down.run)
    register("quark.select_file",          cmd_select_file.run)
    register("quark.go_back",              cmd_go_back.run)
    register("quark.search",               cmd_search.run)

    # ── OCR (Dump + OCR 融合) ──
    from ocr import cmd_observe_screen, cmd_click_element, cmd_reveal_controls

    register("observe_screen",             cmd_observe_screen.observe_screen)
    register("click_element",              cmd_click_element.click_element)
    register("reveal_controls",            cmd_reveal_controls.reveal_controls)


# ─────────────────────── HTTP 处理器 ───────────────────────

class CompoundHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器。

    对标 Java HttpCompoundServer.handleConnection()。
    """

    # 禁止默认的 stderr 日志（设备环境不需要）
    def log_message(self, format, *args):
        print(f"[HTTP] {self.client_address[0]} - {format % args}")

    def do_POST(self):
        if self.path == "/v1/compound":
            self._handle_compound()
        else:
            self._send_json(404, _error_json("NOT_FOUND", f"Unknown path: {self.path}"))

    def do_GET(self):
        if self.path == "/v1/health":
            self._handle_health()
        else:
            self._send_json(404, _error_json("NOT_FOUND", f"Unknown path: {self.path}"))

    def _handle_compound(self):
        """处理 POST /v1/compound。

        请求体: {"command": "xxx", "params": {...}} 或 {"command": "xxx", "params": [1,2]}
        响应: registry.execute() 的返回值
        """
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self._send_json(400, _error_json("BAD_JSON", "Empty request body"))
                return

            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))

            if "command" not in data:
                self._send_json(400, _error_json("BAD_JSON", "Missing required field: command"))
                return

            command = data["command"]

            # 解析 params（支持对象和数组两种格式）
            params = {}
            if "params" in data:
                p = data["params"]
                if isinstance(p, dict):
                    params = p
                elif isinstance(p, list):
                    # 数组格式：包装成 {"values": [1, 2, 3]}
                    params = {"values": p}

            # 执行命令
            result = execute(command, params)
            self._send_json(200, result)

        except json.JSONDecodeError as e:
            self._send_json(400, _error_json("BAD_JSON", f"Invalid JSON: {e}"))
        except Exception as e:
            traceback.print_exc()
            self._send_json(500, _error_json("INTERNAL_ERROR", str(e)))

    def _handle_health(self):
        """处理 GET /v1/health。"""
        commands = list_commands()
        response = {
            "ok": True,
            "data": {
                "status": "healthy",
                "version": "0.2.0-python",
                "available_commands": commands,
            },
        }
        self._send_json(200, response)

    def _send_json(self, status_code, data):
        """发送 JSON 响应。"""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=UTF-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """多线程 HTTP 服务器。"""
    daemon_threads = True
    allow_reuse_address = True


def _error_json(code, message):
    """构造错误响应 JSON。"""
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
        },
    }


# ─────────────────────── 启动入口 ───────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="GUIAgent Python Compound HTTP Server")
    parser.add_argument("--port", type=int,
                        default=int(os.environ.get("GUIAGENT_HTTP_PORT", "8765")),
                        help="HTTP port (default: 8765)")
    parser.add_argument("--host", type=str,
                        default=os.environ.get("GUIAGENT_HTTP_HOST", "0.0.0.0"),
                        help="Bind address (default: 0.0.0.0)")
    args = parser.parse_args()

    # 注册所有命令
    print("[server] Registering commands...")
    register_all_commands()
    commands = list_commands()
    print(f"[server] Registered {len(commands)} commands: {', '.join(commands)}")

    # 启动 HTTP 服务器
    try:
        server = ThreadingHTTPServer((args.host, args.port), CompoundHandler)
        print(f"[server] GUIAgent Python HTTP server up: {args.host}:{args.port}")
        server.serve_forever()
    except OSError as e:
        print(f"[server] Failed to bind {args.host}:{args.port}: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[server] Shutting down...")
        server.shutdown()
        get_registry().shutdown()


if __name__ == "__main__":
    main()
