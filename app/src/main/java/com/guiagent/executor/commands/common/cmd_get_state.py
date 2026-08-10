# -*- coding: utf-8 -*-
"""获取当前前台状态。通用命令，不区分 APP。

返回前台应用包名 + 页面前若干条可见文本（去重后最多 12 条），
供调用方判断"当前在哪个 App / 大概在哪个页面"，再决定使用哪组 App 命令。

对标 Java: GetStateCommand.java

示例:
    POST /v1/compound  {"command":"get_state","params":{}}
    -> {"ok":true,"data":{"command":"get_state","pkg":"com.qiyi.video.speaker",
        "summary":["播放","选集","第3集","1080P"]}}
"""
import json
import sys

from common.utils import (
    success_with_data, error, dump, collect_texts, find_node_in_tree,
)

CMD_NAME = "get_state"


def run(params=None):
    """获取当前前台状态。

    Args:
        params: 可选 dict，当前无使用参数。

    Returns:
        dict: {"ok": true, "data": {"command": "get_state", "pkg": "...", "summary": [...]}}
              或 {"ok": false, "error": {"code": "...", "message": "..."}}
    """
    # dump UI 树，取 pkg + 可见文本
    r = dump(depth=4, include=["id", "text", "pkg"])
    if not r.get("ok"):
        return error("EXECUTION_FAILED", "dump failed")

    data = r.get("data", {})
    window = data.get("window", {})
    pkg = window.get("pkg", "")

    if not pkg:
        return error("NO_MATCH", "no active window")

    # 收集可见文本（去重，最多 12 条）
    texts = collect_texts(window)

    return success_with_data(CMD_NAME, {"pkg": pkg, "summary": texts})


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
