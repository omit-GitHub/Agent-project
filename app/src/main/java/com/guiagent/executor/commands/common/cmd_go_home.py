# -*- coding: utf-8 -*-
"""主页键。通用命令，不区分 APP。

对标 Java: GoHomeCommand.java
等价操作: service.global(AccessibilityService.GLOBAL_ACTION_HOME)
"""
import json
import sys

from common.utils import success, error, global_action

CMD_NAME = "go_home"


def run(params=None):
    """按下主页键。

    Args:
        params: 可选 dict，当前无使用参数。

    Returns:
        dict: {"ok": true, "data": {"command": "go_home", "result": "home"}}
              或 {"ok": false, "error": {"code": "...", "message": "..."}}
    """
    r = global_action("HOME")
    if r.get("ok"):
        return success(CMD_NAME, "home")
    return error("EXECUTION_FAILED", "global(ACTION_HOME) returned false")


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
