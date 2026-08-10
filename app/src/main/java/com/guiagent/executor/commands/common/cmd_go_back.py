# -*- coding: utf-8 -*-
"""返回键。通用命令，不区分 APP。

对标 Java: GoBackCommand.java
等价操作: service.global(AccessibilityService.GLOBAL_ACTION_BACK)
"""
import json
import sys

from common.utils import success, error, global_action

CMD_NAME = "go_back"


def run(params=None):
    """按下返回键。

    Args:
        params: 可选 dict，当前无使用参数。

    Returns:
        dict: {"ok": true, "data": {"command": "go_back", "result": "back"}}
              或 {"ok": false, "error": {"code": "...", "message": "..."}}
    """
    r = global_action("BACK")
    if r.get("ok"):
        return success(CMD_NAME, "back")
    return error("EXECUTION_FAILED", "global(ACTION_BACK) returned false")


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
