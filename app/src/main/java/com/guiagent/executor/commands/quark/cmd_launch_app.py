# -*- coding: utf-8 -*-
"""启动夸克网盘 APP。

对标 Java: QuarkLaunchAppCommand.java
包名: com.quark.yun.tv

冷启动后等待 8 秒让搜索入口完成初始化，并附带即时状态快照
避免 CompoundRegistry 再等待页面稳定（8s 缓冲 + 8s 稳定等待会超过 15s 全局超时）。
"""
import json
import sys

from common.utils import success_with_data, error, start_app, dump

CMD_NAME = "quark.launch_app"
QUARK_PACKAGE = "com.quark.yun.tv"
SEARCH_READY_BUFFER_SEC = 8  # 冷启动后等待搜索入口初始化


def run(params=None):
    """启动夸克网盘 APP。

    Args:
        params: 可选 dict，当前无使用参数。

    Returns:
        dict: {"ok": true, "data": {"command": "quark.launch_app",
               "result": "launched", "state": {...}}}
              或 {"ok": false, "error": {"code": "...", "message": "..."}}
    """
    r = start_app(QUARK_PACKAGE)
    if r.get("ok"):
        # 等待夸克首页的搜索入口完成初始化
        import time
        time.sleep(SEARCH_READY_BUFFER_SEC)

        # 附即时状态快照，避免 CompoundRegistry 再等待页面稳定
        state = {}
        state_r = dump(depth=3)
        if state_r.get("ok"):
            state = state_r.get("data", {}).get("window", {})

        return success_with_data(CMD_NAME, {
            "result": "launched",
            "state": state,
        })
    else:
        return error("EXECUTION_FAILED", "Failed to launch Quark APP")


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
