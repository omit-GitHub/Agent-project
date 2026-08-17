# -*- coding: utf-8 -*-
"""获取当前前台状态（增强版）。

返回结构化状态：
  - 基础信息：pkg, activity, summary (向后兼容旧 schema)
  - 页面分类：page_type, app_category
  - 播放器子状态：player.control_bar_visible / is_playing / current_speed / ...
  - 焦点与浮层：focused_element, overlay
  - 屏幕信息：screen_size, screen_version, dump_status

委托给 observation.state.resolve_state()，后者封装了 ping + dump + classify + detect。

示例响应（Player 页面，控制条可见）:
    POST /v1/compound  {"command":"get_state","params":{}}
    -> {"ok":true,"data":{
         "command":"get_state",
         "pkg":"com.qiyi.video.speaker",
         "activity":"PlayerActivity",
         "page_type":"player",
         "app_category":"video_player",
         "player":{
            "control_bar_visible":true,
            "is_playing":true,
            "current_speed":"1.0",
            "current_quality":"1080P",
            "episode_panel_open":false
         },
         "summary":["暂停","选集","第3集","1080P","倍速"],
         ...
       }}
"""
import json
import sys
import os

# 让本模块能找到 observation 包
_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from common.utils import success_with_data, error       # noqa: E402
from observation.state import resolve_state              # noqa: E402

CMD_NAME = "get_state"


def run(params=None):
    """获取当前前台状态（结构化版本）。

    Returns:
        dict: success_with_data("get_state", StateSnapshot.to_dict())
              或 error(...)
    """
    try:
        snapshot = resolve_state()
    except Exception as e:
        return error("RESOLVE_FAILED", f"resolve_state failed: {e}")

    data = snapshot.to_dict()

    # 兜底：如果 pkg 完全为空，至少给个错误码让调用方知道
    if not data.get("pkg"):
        # 仍返回部分数据（summary 里可能有失败原因），但用 error 提示
        # 这里选择返回 success + 警告，因为 Agent 仍能处理部分信息
        data["warning"] = "pkg_empty: dump or ping may have failed"

    return success_with_data(CMD_NAME, data)


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
