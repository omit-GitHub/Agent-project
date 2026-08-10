# -*- coding: utf-8 -*-
"""命令注册表 — 对标 Java CompoundRegistry。

核心功能:
  - register(name, handler) — 注册命令
  - execute(name, params) — 串行执行命令（15s 超时）
  - 命令执行后自动附加前台状态（capture_state / await_stable）
  - list_commands() — 列出所有已注册命令名

状态捕获:
  通过 WS dump 操作获取 UI 树，提取前台 pkg + 可见文本摘要。
  对标 Java StateCapture.java（原来直接操作 AccessibilityNodeInfo，
  Python 侧只能通过 WS 远程获取）。
"""
import json
import os
import sys
import time
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# 确保能找到根目录的 send.py
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from common.utils import (  # noqa: E402
    dump as ws_dump,
    collect_texts,
    find_node_in_tree,
    error as make_error,
)


# ─────────────────────── 状态捕获 ───────────────────────

MAX_SUMMARY_TEXTS = 12
MAX_TEXT_LEN = 30
POLL_INTERVAL_S = 0.3
STATE_WAIT_CAP_MS = 8000


def capture_state():
    """采集当前前台状态。

    对标 Java StateCapture.capture():
    {"pkg": "com.xxx", "summary": ["文本1", "文本2", ...]}

    通过 WS dump 获取 UI 树，提取 root 的 pkg 和可见文本。
    """
    try:
        r = ws_dump(depth=4, include=["id", "text", "pkg"])
        if not r.get("ok"):
            return {"pkg": "", "summary": []}

        window = r.get("data", {}).get("window", {})
        pkg = window.get("pkg", "")
        texts = collect_texts(window, max_count=MAX_SUMMARY_TEXTS, max_len=MAX_TEXT_LEN)
        return {"pkg": pkg, "summary": texts}
    except Exception:
        return {"pkg": "", "summary": []}


def _capture_baseline_pkg():
    """捕获当前前台包名作为基线。"""
    try:
        state = capture_state()
        return state.get("pkg", "")
    except Exception:
        return ""


def await_stable(baseline_pkg, cap_ms=STATE_WAIT_CAP_MS):
    """等待 UI 稳定后采集状态。

    对标 Java StateCapture.awaitStable():
    每 300ms 采一次，最多 cap_ms。返回条件:
      - 前台包名离开基线（App 切换）且连续两次采集相同
      - 包名未变但树发生过变化且已稳定
      - 否则等到 cap_ms

    返回 state dict。
    """
    prev = capture_state()
    tree_changed = False
    deadline = time.time() + cap_ms / 1000.0

    while time.time() < deadline:
        time.sleep(POLL_INTERVAL_S)
        cur = capture_state()

        pkg = cur.get("pkg", "")
        pkg_left_baseline = bool(pkg) and pkg != baseline_pkg

        if cur == prev:
            # 连续两次相同
            if pkg_left_baseline or tree_changed:
                return cur
        else:
            tree_changed = True

        prev = cur

    return prev


def _states_equal(a, b):
    """比较两个状态是否相同。"""
    return a.get("pkg") == b.get("pkg") and a.get("summary") == b.get("summary")


# ─────────────────────── 命令注册表 ───────────────────────

class CompoundRegistry:
    """命令注册表。

    对标 Java CompoundRegistry:
    - Map<String, CompoundCommand> → COMMANDS dict
    - SingleThreadExecutor → ThreadPoolExecutor(max_workers=1)
    - 15s 超时
    - 自动状态附加
    """

    def __init__(self, timeout_seconds=15, state_cap_ms=STATE_WAIT_CAP_MS):
        self._commands = {}  # name → handler(params) -> result_dict
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="guiagent-cmd")
        self._timeout = timeout_seconds
        self._state_cap_ms = state_cap_ms
        self._lock = threading.Lock()

    def register(self, name, handler):
        """注册命令。handler 签名: handler(params: dict) -> dict"""
        with self._lock:
            self._commands[name] = handler

    def list_commands(self):
        """列出所有已注册命令名。"""
        with self._lock:
            return list(self._commands.keys())

    def execute(self, name, params):
        """执行命令。串行化（SingleThreadExecutor），超时返回 TIMEOUT 错误。

        对标 Java CompoundRegistry.execute():
        1. 捕获基线包名
        2. 提交到单线程执行器
        3. 等待结果（15s 超时）
        4. 自动附加状态
        """
        with self._lock:
            handler = self._commands.get(name)

        if handler is None:
            return make_error("UNKNOWN_COMMAND", f"Unknown command: {name}")

        baseline_pkg = _capture_baseline_pkg()

        try:
            future = self._executor.submit(self._run_command, handler, params)
            result = future.result(timeout=self._timeout)
            self._attach_state(result, baseline_pkg)
            return result
        except FuturesTimeoutError:
            return make_error("TIMEOUT",
                              f"Command execution timed out after {self._timeout}s")
        except Exception as e:
            traceback.print_exc()
            msg = str(e) if str(e) else repr(e)
            return make_error("EXECUTION_FAILED", msg)

    def _run_command(self, handler, params):
        """在线程中执行命令。"""
        try:
            return handler(params)
        except Exception as e:
            # 命令内部异常：包装为错误响应
            msg = str(e) if str(e) else repr(e)
            return make_error("EXECUTION_FAILED", msg)

    def _attach_state(self, result, baseline_pkg):
        """命令执行后自动附加前台状态。

        对标 Java CompoundRegistry.attachState():
        - 成功时: 等待 UI 稳定，附加 state 到 data.state
        - 失败时: 立即采集一次，附加到顶层 state
        - 任何异常静默吞掉
        """
        try:
            if not isinstance(result, dict):
                return

            ok = result.get("ok", False)
            if ok:
                data = result.get("data")
                if isinstance(data, dict):
                    # 如果 data 里已经有 summary 或 state，跳过
                    if "summary" not in data and "state" not in data:
                        state = await_stable(baseline_pkg, self._state_cap_ms)
                        if state:
                            data["state"] = state
            else:
                # 失败时：立即采集一次状态
                state = capture_state()
                if state:
                    result["state"] = state
        except Exception:
            # 静默吞掉，绝不影响命令本身的响应
            pass

    def shutdown(self):
        """关闭执行器。"""
        self._executor.shutdown(wait=False)


# ─────────────────────── 全局单例 ───────────────────────

_registry = None
_registry_lock = threading.Lock()


def get_registry():
    """获取全局命令注册表单例。"""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = CompoundRegistry()
    return _registry


def register(name, handler):
    """注册命令到全局注册表。"""
    get_registry().register(name, handler)


def execute(name, params):
    """执行命令。"""
    return get_registry().execute(name, params)


def list_commands():
    """列出所有已注册命令。"""
    return get_registry().list_commands()
