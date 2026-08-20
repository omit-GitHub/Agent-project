# -*- coding: utf-8 -*-
"""启动夸克网盘 APP — Phase 6 无 dump 版。"""
import json
import sys
import time

from common.utils import success_with_data, error, start_app  # noqa: E402
from observation.state import resolve_state  # noqa: E402

CMD_NAME = "quark.launch_app"
QUARK_PACKAGE = "com.quark.yun.tv"
SEARCH_READY_BUFFER_SEC = 8


def run(params=None):
    """启动夸克网盘 APP。"""
    r = start_app(QUARK_PACKAGE)
    if r.get("ok"):
        time.sleep(SEARCH_READY_BUFFER_SEC)

        # 附即时状态快照
        state = resolve_state()

        return success_with_data(CMD_NAME, {
            "result": "launched",
            "state": state.to_dict() if hasattr(state, 'to_dict') else {},
        })
    else:
        return error("EXECUTION_FAILED", "Failed to launch Quark APP")


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
