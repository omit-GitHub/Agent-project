# -*- coding: utf-8 -*-
"""StateSnapshot — UI State Resolver 的输出数据结构。

对标原 registry.py.capture_state() 的 {pkg, summary}，但扩展为结构化状态：
  - 页面类型 (page_type)
  - 播放器子状态 (PlayerState)
  - 浮层类型 (overlay)
  - 焦点元素 (focused_element)
  - 等等

向后兼容：旧字段 pkg / summary 仍保留，新字段按需填充。
"""
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any


# ─────────────── 播放器子状态 ───────────────

@dataclass
class PlayerState:
    """播放器场景的结构化状态。

    字段全部可选 —— 非播放器场景下整个 PlayerState 为 None。
    """
    # 控制条是否可见（关键：决定后续要不要先 reveal_controls）
    control_bar_visible: bool = False

    # 是否正在播放 (None = 无法判断)
    is_playing: Optional[bool] = None

    # 当前倍速 ("0.75" / "1.0" / "1.5" / "2.0" 等；None = 未知)
    current_speed: Optional[str] = None

    # 当前清晰度 ("270P" / "480P" / "720P" / "1080P" 等；None = 未知)
    current_quality: Optional[str] = None

    # 选集面板是否打开
    episode_panel_open: bool = False

    # 当前焦点元素的 resource-id (None = 无焦点 / 无法检测)
    focused_element_id: Optional[str] = None

    # 播放进度（秒；None = 无法检测）
    progress_seconds: Optional[int] = None

    # 当前集数/标题（如果可见）
    current_episode: Optional[str] = None


# ─────────────── 顶层状态快照 ───────────────

# page_type 的合法取值
PAGE_TYPE_STRUCTURED = "structured"           # 搜索/详情/选集/列表/launcher/文件浏览器
PAGE_TYPE_VISUAL = "visual"                   # 自绘/WebView 等无完整节点的页面
PAGE_TYPE_PLAYER = "player"                   # 播放器页面（隐藏/瞬态控件）
PAGE_TYPE_HIDDEN_CONTROLS = "hidden_controls" # 通用隐藏控件场景（与 player 等价别名）
PAGE_TYPE_UNKNOWN = "unknown"

VALID_PAGE_TYPES = {
    PAGE_TYPE_STRUCTURED,
    PAGE_TYPE_VISUAL,
    PAGE_TYPE_PLAYER,
    PAGE_TYPE_HIDDEN_CONTROLS,
    PAGE_TYPE_UNKNOWN,
}

# app_category 的合法取值
APP_CATEGORY_VIDEO_PLAYER = "video_player"
APP_CATEGORY_FILE_BROWSER = "file_browser"
APP_CATEGORY_LAUNCHER = "launcher"
APP_CATEGORY_SYSTEM = "system"
APP_CATEGORY_UNKNOWN = "unknown"

# overlay 的合法取值
OVERLAY_SPEED_PANEL = "speed_panel"
OVERLAY_QUALITY_PANEL = "quality_panel"
OVERLAY_EPISODE_PANEL = "episode_panel"
OVERLAY_DETAIL_PANEL = "detail_panel"
OVERLAY_NONE = None


@dataclass
class StateSnapshot:
    """设备当前状态的结构化快照。

    向后兼容：pkg + summary 仍保留（与旧 capture_state 一致）。
    新增字段：page_type / app_category / player / focused_element / overlay / ...

    序列化：to_dict() 输出 JSON-friendly dict，None 字段省略。
    """
    # ── 基础信息（兼容旧 schema）──
    pkg: str = ""
    activity: str = ""
    summary: List[str] = field(default_factory=list)

    # ── 屏幕版本标识（与 observe_screen 的 screen_version 同语义）──
    screen_version: str = ""

    # ── 新增：结构化分类 ──
    page_type: str = PAGE_TYPE_UNKNOWN
    app_category: str = APP_CATEGORY_UNKNOWN

    # ── 新增：播放器子状态（非播放器场景为 None）──
    player: Optional[PlayerState] = None

    # ── 新增：焦点/浮层 ──
    focused_element: Optional[str] = None
    overlay: Optional[str] = None

    # ── dump 可用性 ──
    dump_status: str = "ok"

    # ── 屏幕尺寸 ──
    screen_size: Dict[str, int] = field(
        default_factory=lambda: {"width": 1280, "height": 800}
    )

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 dict，None 字段省略（保持响应简洁）。"""
        d = asdict(self)
        # 移除 None 字段（让响应更紧凑）
        keys_to_remove = [k for k, v in d.items() if v is None]
        for k in keys_to_remove:
            d.pop(k)
        # PlayerState 整体为 None 时也直接移除
        if "player" in d and d["player"] is None:
            d.pop("player")
        return d

    # ── 便捷判断方法 ──

    @property
    def is_player_page(self) -> bool:
        """是否是播放器页面。"""
        return self.page_type in (PAGE_TYPE_PLAYER, PAGE_TYPE_HIDDEN_CONTROLS)

    @property
    def is_structured_page(self) -> bool:
        """是否是结构化页面（UI 节点完整）。"""
        return self.page_type == PAGE_TYPE_STRUCTURED

    @property
    def is_visual_page(self) -> bool:
        """是否是视觉页面（UI 节点不完整，依赖 OCR）。"""
        return self.page_type == PAGE_TYPE_VISUAL

    @property
    def has_control_bar(self) -> bool:
        """控制条是否可见（非播放器页返回 False）。"""
        return bool(self.player and self.player.control_bar_visible)

    def validate(self) -> None:
        """校验字段取值合法性。非法值抛 ValueError。"""
        if self.page_type not in VALID_PAGE_TYPES:
            raise ValueError(
                f"Invalid page_type: {self.page_type!r}. "
                f"Must be one of {sorted(VALID_PAGE_TYPES)}"
            )


# ─────────────── 工厂方法 ───────────────

def empty_snapshot() -> StateSnapshot:
    """构造一个空快照（所有字段默认值）。用于失败兜底。"""
    return StateSnapshot()


def snapshot_from_legacy(legacy_state: Dict[str, Any]) -> StateSnapshot:
    """从旧版 {pkg, summary} dict 构造 StateSnapshot。

    用于过渡期兼容：旧 registry.capture_state() 返回的 dict 可以
    无损升级到 StateSnapshot（page_type 默认为 unknown）。
    """
    if not isinstance(legacy_state, dict):
        return empty_snapshot()
    return StateSnapshot(
        pkg=legacy_state.get("pkg", ""),
        summary=list(legacy_state.get("summary", [])),
    )
