# -*- coding: utf-8 -*-
"""命令管理 — 从设备 HTTP API 获取可用命令，生成 LLM function calling schema。

核心功能:
  1. 从 GET /v1/health 动态获取设备端可用命令列表
  2. 用内置文档为每个命令生成中文描述
  3. 构造 Qwen function calling 的 tools schema
"""
import json
import requests

from . import config


# ─────────────── 命令文档 ───────────────

# 每个命令的中文描述 + 参数说明
# 未在此列出的命令也能用（自动生成基础 schema），但有文档的命令 LLM 理解更准
COMMAND_DOCS = {
    # ── 通用 ──
    "get_state": {
        "desc": "获取设备当前状态（前台应用包名 + 页面可见文本）。用于判断当前在哪个 App、什么页面。",
        "params": {},
        "examples": ["现在在放什么", "当前是什么页面", "打开的什么应用"],
    },
    "go_back": {
        "desc": "按返回键（等同于遥控器返回按钮）。",
        "params": {},
        "examples": ["返回", "返回上一页", "后退"],
    },
    "go_home": {
        "desc": "按主页键，回到桌面/launcher。",
        "params": {},
        "examples": ["回到主页", "回桌面", "回到首页"],
    },
    "volume_up": {
        "desc": "调高音量。可指定格数。",
        "params": {"count": "调高几格（默认1，最大20）"},
        "examples": ["声音大一点", "音量调到最大", "音量+3"],
    },
    "volume_down": {
        "desc": "调低音量。可指定格数。",
        "params": {"count": "调低几格（默认1，最大20）"},
        "examples": ["声音小一点", "音量调低", "音量-2"],
    },
    "volume_mute": {
        "desc": "静音/取消静音（切换）。",
        "params": {},
        "examples": ["静音", "关闭声音", "取消静音"],
    },
    "launcher_search": {
        "desc": "在 launcher（聚合平台入口）搜索片源。支持爱奇艺/优酷/腾讯/芒果等。",
        "params": {"keyword": "搜索关键词（必填）"},
        "examples": ["搜索庆余年", "找一下甄嬛传", "搜电影战狼"],
    },
    "play": {
        "desc": "播放搜索结果中的第 N 个片源（需要先执行 launcher_search）。",
        "params": {"values": "片源序号数组，如 [1] 表示第一个"},
        "examples": ["播放第一个", "看第三个结果", "选第2个"],
    },

    # ── 爱奇艺 ──
    "aiqiyi.toggle_play": {
        "desc": "爱奇艺：播放/暂停切换。",
        "params": {},
        "examples": ["暂停", "继续播放", "暂停一下"],
    },
    "aiqiyi.next_episode": {
        "desc": "爱奇艺：切换到下一集。",
        "params": {},
        "examples": ["下一集", "看下一集"],
    },
    "aiqiyi.prev_episode": {
        "desc": "爱奇艺：切换到上一集。",
        "params": {},
        "examples": ["上一集", "看上一集"],
    },
    "aiqiyi.toggle_control_bar": {
        "desc": "爱奇艺：显示/隐藏播放控制条。",
        "params": {},
        "examples": ["显示控制条", "隐藏控制条"],
    },
    "aiqiyi.open_episode_panel": {
        "desc": "爱奇艺：打开选集面板（显示剧集列表）。仅电视剧/综艺有效，电影无选集。",
        "params": {},
        "examples": ["打开选集", "看看有哪些集"],
    },
    "aiqiyi.close_episode_panel": {
        "desc": "爱奇艺：关闭选集面板。",
        "params": {},
        "examples": ["关闭选集面板"],
    },
    "aiqiyi.scroll_episode_up": {
        "desc": "爱奇艺：选集列表向上滚动（看更早的集数）。",
        "params": {},
        "examples": ["往上翻", "看看前面的集"],
    },
    "aiqiyi.scroll_episode_down": {
        "desc": "爱奇艺：选集列表向下滚动（看更晚的集数）。",
        "params": {},
        "examples": ["往下翻", "看看后面的集"],
    },
    "aiqiyi.select_episode": {
        "desc": "爱奇艺：选择播放指定集数。",
        "params": {
            "values": "集数参数。[N] 选第 N 个；[R,C] 选第 R 行第 C 列（网格布局）"
        },
        "examples": ["看第3集", "播放第5集", "选第2行第1列"],
    },
    "aiqiyi.set_speed": {
        "desc": "爱奇艺：设置播放倍速。",
        "params": {"speed": "倍速值：0.75, 1.0, 1.25, 1.5, 2.0"},
        "examples": ["1.5倍速", "快进播放", "正常速度", "两倍速"],
    },
    "aiqiyi.set_quality": {
        "desc": "爱奇艺：设置视频清晰度。",
        "params": {"quality": "清晰度：270P, 480P（720P/1080P 待验证）"},
        "examples": ["切到480P", "高清", "标清"],
    },
    "aiqiyi.brightness_up": {
        "desc": "爱奇艺：调高屏幕亮度。",
        "params": {"count": "调高几格（默认1）"},
        "examples": ["亮一点", "亮度调高"],
    },
    "aiqiyi.brightness_down": {
        "desc": "爱奇艺：调低屏幕亮度。",
        "params": {"count": "调低几格（默认1）"},
        "examples": ["暗一点", "亮度调低"],
    },
    "aiqiyi.toggle_control_bar": {
        "desc": "爱奇艺：显示/隐藏控制条。",
        "params": {},
        "examples": ["显示控制条"],
    },
    "aiqiyi.open_detail": {
        "desc": "爱奇艺：打开影片详情页（显示简介、演员等）。",
        "params": {},
        "examples": ["看看简介", "打开详情"],
    },
    "aiqiyi.close_detail": {
        "desc": "爱奇艺：关闭影片详情页。",
        "params": {},
        "examples": ["关闭详情", "返回播放"],
    },

    # ── 腾讯视频 ──
    "tencent.toggle_play": {
        "desc": "腾讯视频：播放/暂停切换。",
        "params": {},
        "examples": ["暂停", "继续播放"],
    },
    "tencent.next_episode": {
        "desc": "腾讯视频：切换到下一集。",
        "params": {},
        "examples": ["下一集"],
    },
    "tencent.prev_episode": {
        "desc": "腾讯视频：切换到上一集。",
        "params": {},
        "examples": ["上一集"],
    },
    "tencent.toggle_control_bar": {
        "desc": "腾讯视频：显示/隐藏控制条。",
        "params": {},
        "examples": ["显示控制条"],
    },
    "tencent.open_episode_panel": {
        "desc": "腾讯视频：打开选集面板。",
        "params": {},
        "examples": ["打开选集"],
    },
    "tencent.close_episode_panel": {
        "desc": "腾讯视频：关闭选集面板。",
        "params": {},
        "examples": ["关闭选集"],
    },
    "tencent.scroll_episode_up": {
        "desc": "腾讯视频：选集列表向上滚动。",
        "params": {},
        "examples": ["往上翻选集"],
    },
    "tencent.scroll_episode_down": {
        "desc": "腾讯视频：选集列表向下滚动。",
        "params": {},
        "examples": ["往下翻选集"],
    },
    "tencent.select_episode": {
        "desc": "腾讯视频：选择播放指定集数。",
        "params": {"episode": "集数（整数）"},
        "examples": ["看第3集"],
    },
    "tencent.set_speed": {
        "desc": "腾讯视频：设置播放倍速。",
        "params": {"speed": "倍速值：0.75, 1.0, 1.25, 1.5, 2.0"},
        "examples": ["1.5倍速", "正常速度"],
    },
    "tencent.set_quality": {
        "desc": "腾讯视频：设置视频清晰度。",
        "params": {"quality": "清晰度：270P, 480P"},
        "examples": ["切到480P", "标清"],
    },
    "tencent.brightness_up": {
        "desc": "腾讯视频：调高屏幕亮度。",
        "params": {"count": "调高几格（默认1）"},
        "examples": ["亮一点"],
    },
    "tencent.brightness_down": {
        "desc": "腾讯视频：调低屏幕亮度。",
        "params": {"count": "调低几格（默认1）"},
        "examples": ["暗一点"],
    },
    "tencent.open_detail": {
        "desc": "腾讯视频：打开影片详情页。",
        "params": {},
        "examples": ["看看简介"],
    },

    # ── 夸克网盘 ──
    "quark.launch_app": {
        "desc": "夸克网盘：启动应用。",
        "params": {},
        "examples": ["打开夸克"],
    },
    "quark.click_navigation": {
        "desc": "夸克网盘：点击导航栏项目。",
        "params": {"text": "导航项文本"},
        "examples": ["点击全部文件"],
    },
    "quark.scroll_up": {
        "desc": "夸克网盘：文件列表向上滚动。",
        "params": {},
        "examples": ["往上翻"],
    },
    "quark.scroll_down": {
        "desc": "夸克网盘：文件列表向下滚动。",
        "params": {},
        "examples": ["往下翻"],
    },
    "quark.select_file": {
        "desc": "夸克网盘：选择文件。",
        "params": {"values": "文件序号 [N] 或行列 [R,C]"},
        "examples": ["打开第3个文件"],
    },
    "quark.go_back": {
        "desc": "夸克网盘：智能返回（自动判断返回层级）。",
        "params": {},
        "examples": ["返回"],
    },
    "quark.search": {
        "desc": "夸克网盘：搜索文件。",
        "params": {"keyword": "搜索关键词"},
        "examples": ["搜索电影"],
    },
}


# ─────────────── 从设备获取命令列表 ───────────────

def fetch_available_commands():
    """从设备 HTTP API 获取可用命令列表。

    调用 GET /v1/health → 返回 available_commands 列表。
    """
    try:
        resp = requests.get(f"{config.DEVICE_URL}/v1/health", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data.get("ok"):
            return data["data"].get("available_commands", [])
    except Exception as e:
        print(f"[警告] 无法连接设备 {config.DEVICE_URL}: {e}")
    return []


# ─────────────── 生成 Tools Schema ───────────────

def build_tools_schema(commands=None):
    """生成 Qwen function calling 的 tools schema。

    使用单 function 策略: 一个 control_device 函数，参数为 command + params。
    这样比 54 个独立 function 更紧凑，token 消耗更少。

    Args:
        commands: 命令名列表。为 None 时从设备动态获取。

    Returns:
        list: OpenAI 格式的 tools schema
    """
    if commands is None:
        commands = fetch_available_commands()

    if not commands:
        print("[警告] 设备无可用命令，使用默认列表")
        commands = list(COMMAND_DOCS.keys())

    # 构造命令列表描述（含文档的命令加中文说明）
    cmd_descriptions = []
    for cmd in commands:
        doc = COMMAND_DOCS.get(cmd)
        if doc:
            cmd_descriptions.append(f"  - {cmd}: {doc['desc']}")
        else:
            cmd_descriptions.append(f"  - {cmd}")

    commands_text = "\n".join(cmd_descriptions)

    # 构造参数示例
    param_examples = []
    for cmd in commands[:10]:  # 取前 10 个有代表性的
        doc = COMMAND_DOCS.get(cmd)
        if doc and doc.get("params"):
            params_desc = ", ".join(f'"{k}": v' for k, v in doc["params"].items())
            param_examples.append(f'    {{"command": "{cmd}", "params": {{{params_desc}}}}}')

    examples_text = "\n".join(param_examples) if param_examples else '    {"command": "get_state"}'

    tools = [
        {
            "type": "function",
            "function": {
                "name": "control_device",
                "description": (
                    "控制连接的电视设备。支持爱奇艺、腾讯视频、夸克网盘等视频应用。\n"
                    "每次调用后会自动返回设备当前状态（前台应用+页面内容），你可以据此判断操作是否成功。\n\n"
                    f"可用命令列表（共 {len(commands)} 个）:\n{commands_text}\n\n"
                    "调用示例:\n"
                    f"{examples_text}"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "要执行的命令名（从上方的可用命令列表中选择）",
                        },
                        "params": {
                            "type": "object",
                            "description": (
                                "命令参数（根据具体命令填写）。"
                                "无参数的命令传 {} 或省略。"
                                "常见参数: "
                                "count(整数,音量/亮度格数), "
                                "speed(字符串,倍速值), "
                                "quality(字符串,清晰度), "
                                "keyword(字符串,搜索关键词), "
                                "values(整数数组,集数/序号), "
                                "episode(整数,集数)"
                            ),
                            "default": {},
                        },
                    },
                    "required": ["command"],
                },
            },
        }
    ]

    return tools


def get_command_description(command_name):
    """获取单个命令的中文描述。"""
    doc = COMMAND_DOCS.get(command_name)
    if doc:
        return doc["desc"]
    return command_name
