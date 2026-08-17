# -*- coding: utf-8 -*-
"""UI State Resolver 单元测试。

覆盖:
  - schema.py: StateSnapshot 序列化、校验、便捷属性
  - page_classifier.py: 包名/Activity 快速路径 + UI 树启发式
  - player_state.py: 控制条/播放状态/浮层/焦点检测

运行:
  cd app/src/main/java/com/guiagent/executor/commands
  python -m pytest observation/tests/test_state_resolver.py -v
"""
import os
import sys
import unittest

# 让测试能 import observation 包
_HERE = os.path.dirname(os.path.abspath(__file__))
_COMMANDS_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _COMMANDS_ROOT not in sys.path:
    sys.path.insert(0, _COMMANDS_ROOT)

from observation.state.schema import (
    StateSnapshot,
    PlayerState,
    empty_snapshot,
    snapshot_from_legacy,
    PAGE_TYPE_PLAYER,
    PAGE_TYPE_STRUCTURED,
    PAGE_TYPE_VISUAL,
    PAGE_TYPE_UNKNOWN,
    APP_CATEGORY_VIDEO_PLAYER,
    APP_CATEGORY_LAUNCHER,
    APP_CATEGORY_FILE_BROWSER,
    OVERLAY_SPEED_PANEL,
)
from observation.state.page_classifier import classify_page_type
from observation.state.player_state import detect_player_state, detect_overlay


# ═══════════════ Schema Tests ═══════════════

class TestStateSnapshot(unittest.TestCase):

    def test_default_values(self):
        s = StateSnapshot()
        self.assertEqual(s.page_type, PAGE_TYPE_UNKNOWN)
        self.assertIsNone(s.player)
        self.assertEqual(s.summary, [])
        self.assertEqual(s.screen_size, {"width": 1280, "height": 800})

    def test_is_player_page(self):
        s = StateSnapshot(page_type=PAGE_TYPE_PLAYER)
        self.assertTrue(s.is_player_page)
        self.assertFalse(s.is_structured_page)
        self.assertFalse(s.is_visual_page)

    def test_is_structured_page(self):
        s = StateSnapshot(page_type=PAGE_TYPE_STRUCTURED)
        self.assertFalse(s.is_player_page)
        self.assertTrue(s.is_structured_page)

    def test_has_control_bar(self):
        # 无 player 时返回 False
        s = StateSnapshot()
        self.assertFalse(s.has_control_bar)
        # player 存在但 bar 不可见
        s.player = PlayerState(control_bar_visible=False)
        self.assertFalse(s.has_control_bar)
        # player 存在且 bar 可见
        s.player.control_bar_visible = True
        self.assertTrue(s.has_control_bar)

    def test_to_dict_removes_none(self):
        s = StateSnapshot(pkg="x")
        d = s.to_dict()
        self.assertIn("pkg", d)
        self.assertNotIn("player", d)          # player=None 应被省略
        self.assertNotIn("overlay", d)         # overlay=None 应被省略
        self.assertNotIn("focused_element", d) # 同上

    def test_to_dict_keeps_player(self):
        s = StateSnapshot(player=PlayerState(control_bar_visible=True))
        d = s.to_dict()
        self.assertIn("player", d)
        self.assertTrue(d["player"]["control_bar_visible"])

    def test_validate_accepts_valid(self):
        s = StateSnapshot(page_type=PAGE_TYPE_PLAYER)
        s.validate()  # 不抛

    def test_validate_rejects_invalid(self):
        s = StateSnapshot(page_type="bogus_type")
        with self.assertRaises(ValueError):
            s.validate()

    def test_empty_snapshot(self):
        s = empty_snapshot()
        self.assertEqual(s.pkg, "")
        self.assertEqual(s.page_type, PAGE_TYPE_UNKNOWN)

    def test_snapshot_from_legacy(self):
        legacy = {"pkg": "com.qiyi.video.speaker", "summary": ["暂停", "选集"]}
        s = snapshot_from_legacy(legacy)
        self.assertEqual(s.pkg, "com.qiyi.video.speaker")
        self.assertEqual(s.summary, ["暂停", "选集"])
        self.assertEqual(s.page_type, PAGE_TYPE_UNKNOWN)  # 不自动分类

    def test_snapshot_from_legacy_invalid_input(self):
        s = snapshot_from_legacy("not a dict")
        self.assertEqual(s.pkg, "")


# ═══════════════ Page Classifier Tests ═══════════════

class TestPageClassifier(unittest.TestCase):

    # ── 包名快速路径 ──

    def test_aiqiyi_player_activity(self):
        r = classify_page_type("com.qiyi.video.speaker", "PlayerActivity")
        self.assertEqual(r["page_type"], PAGE_TYPE_PLAYER)
        self.assertEqual(r["app_category"], APP_CATEGORY_VIDEO_PLAYER)
        self.assertEqual(r["confidence"], "high")
        self.assertEqual(r["method"], "pkg_activity")

    def test_aiqiyi_detail_activity_is_player(self):
        # DetailActivity 在爱奇艺 = 实际在播放
        r = classify_page_type("com.qiyi.video.speaker", "PhoneDetailActivity")
        self.assertEqual(r["page_type"], PAGE_TYPE_PLAYER)

    def test_aiqiyi_search_activity_is_structured(self):
        r = classify_page_type("com.qiyi.video.speaker", "SearchActivity")
        self.assertEqual(r["page_type"], PAGE_TYPE_STRUCTURED)

    def test_tencent_player_activity(self):
        r = classify_page_type("com.tencent.qqlive", "VideoDetailActivity")
        self.assertEqual(r["page_type"], PAGE_TYPE_PLAYER)

    def test_launcher_pkg(self):
        r = classify_page_type("com.wohuatv.launcher", "")
        self.assertEqual(r["page_type"], PAGE_TYPE_STRUCTURED)
        self.assertEqual(r["app_category"], APP_CATEGORY_LAUNCHER)

    def test_quark_is_file_browser(self):
        r = classify_page_type("com.quark.browser", "")
        self.assertEqual(r["page_type"], PAGE_TYPE_STRUCTURED)
        self.assertEqual(r["app_category"], APP_CATEGORY_FILE_BROWSER)

    def test_unknown_pkg_falls_through(self):
        r = classify_page_type("com.unknown.app", "")
        # 没有 UI 树时应为 unknown
        self.assertEqual(r["page_type"], PAGE_TYPE_UNKNOWN)

    # ── UI 树启发式 ──

    def test_tree_with_player_control_bar_id(self):
        tree = {
            "id": "root",
            "children": [
                {"id": "playerControlBar", "children": [
                    {"id": "btn_pause"},
                ]},
            ],
        }
        r = classify_page_type("com.unknown.app", "", tree=tree)
        self.assertEqual(r["page_type"], PAGE_TYPE_PLAYER)
        self.assertEqual(r["method"], "tree_heuristic")

    def test_tree_with_episode_grid_view(self):
        tree = {"id": "root", "children": [
            {"id": "episodeGridView"},
        ]}
        r = classify_page_type("com.unknown.app", "", tree=tree)
        self.assertEqual(r["page_type"], PAGE_TYPE_PLAYER)

    def test_tree_with_few_nodes_is_visual(self):
        tree = {"id": "root", "children": [
            {"id": "a"}, {"id": "b"},
        ]}
        r = classify_page_type("com.unknown.app", "", tree=tree)
        self.assertEqual(r["page_type"], PAGE_TYPE_VISUAL)

    def test_tree_with_recyclerview_and_clickables(self):
        tree = {"id": "root", "class": "androidx.recyclerview.widget.RecyclerView",
                "children": [
                    {"id": "c1", "clickable": True},
                    {"id": "c2", "clickable": True},
                    {"id": "c3", "clickable": True},
                    {"id": "c4", "clickable": True},
                    {"id": "c5", "clickable": True},
                    {"id": "c6", "clickable": False},
                    {"id": "c7", "clickable": False},
                    {"id": "c8", "clickable": False},
                ]}
        r = classify_page_type("com.unknown.app", "", tree=tree)
        self.assertEqual(r["page_type"], PAGE_TYPE_STRUCTURED)


# ═══════════════ Player State Tests ═══════════════

class TestPlayerState(unittest.TestCase):

    def test_non_player_returns_none(self):
        # 明确非视频 App + 无播放器信号 → None
        tree = {"id": "root", "children": [
            {"id": "launcher_item", "text": "搜索"},
        ]}
        ps = detect_player_state(tree, pkg="com.wohuatv.launcher",
                                 app_category=APP_CATEGORY_LAUNCHER)
        self.assertIsNone(ps)

    def test_control_bar_visible(self):
        tree = {"id": "root", "children": [
            {"id": "playerControlBar", "children": [
                {"id": "btn_pause"},
            ]},
        ]}
        ps = detect_player_state(tree, pkg="com.qiyi.video.speaker",
                                 app_category=APP_CATEGORY_VIDEO_PLAYER)
        self.assertIsNotNone(ps)
        self.assertTrue(ps.control_bar_visible)

    def test_control_bar_hidden(self):
        tree = {"id": "root", "children": [
            {"id": "video_surface", "children": []},
        ]}
        ps = detect_player_state(tree, pkg="com.qiyi.video.speaker",
                                 app_category=APP_CATEGORY_VIDEO_PLAYER)
        self.assertIsNotNone(ps)
        self.assertFalse(ps.control_bar_visible)

    def test_is_playing_via_pause_button(self):
        # 看到 btn_pause → 正在播放
        tree = {"id": "root", "children": [
            {"id": "btn_pause"},
        ]}
        ps = detect_player_state(tree, app_category=APP_CATEGORY_VIDEO_PLAYER)
        self.assertTrue(ps.is_playing)

    def test_is_paused_via_play_button(self):
        # 看到 btn_play → 已暂停
        tree = {"id": "root", "children": [
            {"id": "btn_play"},
        ]}
        ps = detect_player_state(tree, app_category=APP_CATEGORY_VIDEO_PLAYER)
        self.assertFalse(ps.is_playing)

    def test_current_speed(self):
        tree = {"id": "root", "children": [
            {"id": "speed_panel", "children": [
                {"id": "s1", "text": "1.5x"},
            ]},
        ]}
        ps = detect_player_state(tree, app_category=APP_CATEGORY_VIDEO_PLAYER)
        self.assertEqual(ps.current_speed, "1.5")

    def test_current_quality(self):
        tree = {"id": "root", "children": [
            {"id": "quality_panel", "children": [
                {"id": "q1", "text": "1080P"},
            ]},
        ]}
        ps = detect_player_state(tree, app_category=APP_CATEGORY_VIDEO_PLAYER)
        self.assertEqual(ps.current_quality, "1080P")

    def test_episode_panel_open(self):
        tree = {"id": "root", "children": [
            {"id": "episodeGridView", "children": []},
        ]}
        ps = detect_player_state(tree, app_category=APP_CATEGORY_VIDEO_PLAYER)
        self.assertTrue(ps.episode_panel_open)

    def test_focused_element(self):
        tree = {"id": "root", "children": [
            {"id": "btn_pause", "focused": False},
            {"id": "btn_next", "focused": True},
        ]}
        ps = detect_player_state(tree, app_category=APP_CATEGORY_VIDEO_PLAYER)
        self.assertEqual(ps.focused_element_id, "btn_next")

    def test_current_episode_text(self):
        tree = {"id": "root", "children": [
            {"id": "ep_indicator", "text": "正在播放：第3集"},
        ]}
        ps = detect_player_state(tree, app_category=APP_CATEGORY_VIDEO_PLAYER)
        self.assertEqual(ps.current_episode, "第3集")


# ═══════════════ Overlay Detection Tests ═══════════════

class TestOverlayDetection(unittest.TestCase):

    def test_no_overlay(self):
        tree = {"id": "root", "children": [{"id": "btn_pause"}]}
        self.assertIsNone(detect_overlay(tree))

    def test_speed_panel(self):
        tree = {"id": "root", "children": [{"id": "speed_panel"}]}
        self.assertEqual(detect_overlay(tree), OVERLAY_SPEED_PANEL)

    def test_episode_panel(self):
        tree = {"id": "root", "children": [{"id": "episodeGridView"}]}
        self.assertEqual(detect_overlay(tree), "episode_panel")


if __name__ == "__main__":
    unittest.main()
