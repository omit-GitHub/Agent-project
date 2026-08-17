# -*- coding: utf-8 -*-
"""DPAD Executor 单元测试。

覆盖:
  - focus_tracker.py: find_focused_node, get_focused_id, detect_focus_change
  - keymaps.py: get_keymap, list_apps, list_contexts, 方向映射
  - executor._normalize_direction: 方向字符串归一化

运行:
  cd app/src/main/java/com/guiagent/executor/commands
  python -m unittest observation.tests.test_dpad -v
"""
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_COMMANDS_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _COMMANDS_ROOT not in sys.path:
    sys.path.insert(0, _COMMANDS_ROOT)

from observation.dpad.focus_tracker import (
    find_focused_node,
    get_focused_id,
    get_focused_info,
    detect_focus_change,
)
from observation.dpad.keymaps import (
    get_keymap,
    list_apps,
    list_contexts,
    DIRECTION_TO_KEY,
    OPPOSITE_DIRECTION,
)
from observation.dpad.executor import _normalize_direction


# ═══════════════ Focus Tracker Tests ═══════════════

class TestFocusTracker(unittest.TestCase):

    def test_find_focused_root(self):
        tree = {"id": "root", "focused": True, "children": []}
        node = find_focused_node(tree)
        self.assertIsNotNone(node)
        self.assertEqual(node.get("id"), "root")

    def test_find_focused_child(self):
        tree = {"id": "root", "children": [
            {"id": "a", "focused": False},
            {"id": "b", "focused": True, "text": "暂停"},
            {"id": "c"},
        ]}
        node = find_focused_node(tree)
        self.assertIsNotNone(node)
        self.assertEqual(node.get("id"), "b")

    def test_find_focused_deep(self):
        tree = {"id": "root", "children": [
            {"id": "a", "children": [
                {"id": "a1", "children": [
                    {"id": "a1a", "focused": True},
                ]},
            ]},
        ]}
        node = find_focused_node(tree)
        self.assertEqual(node.get("id"), "a1a")

    def test_find_focused_none(self):
        tree = {"id": "root", "children": [
            {"id": "a"}, {"id": "b"},
        ]}
        self.assertIsNone(find_focused_node(tree))

    def test_find_focused_empty_tree(self):
        self.assertIsNone(find_focused_node(None))
        self.assertIsNone(find_focused_node({}))

    def test_get_focused_id(self):
        tree = {"id": "root", "children": [
            {"id": "btn_pause", "focused": True},
        ]}
        self.assertEqual(get_focused_id(tree), "btn_pause")

    def test_get_focused_id_none(self):
        tree = {"id": "root", "children": []}
        self.assertIsNone(get_focused_id(tree))

    def test_get_focused_info(self):
        tree = {"id": "root", "children": [
            {"id": "btn_pause", "text": "暂停",
             "class": "Button", "focused": True,
             "bounds": {"l": 100, "t": 200, "r": 200, "b": 250},
             "clickable": True},
        ]}
        info = get_focused_info(tree)
        self.assertIsNotNone(info)
        self.assertEqual(info["id"], "btn_pause")
        self.assertEqual(info["text"], "暂停")
        self.assertEqual(info["class"], "Button")
        self.assertTrue(info["clickable"])

    def test_detect_focus_change_moved(self):
        before = {"id": "root", "children": [
            {"id": "btn_pause", "focused": True},
            {"id": "btn_next"},
        ]}
        after = {"id": "root", "children": [
            {"id": "btn_pause"},
            {"id": "btn_next", "text": "下一集", "focused": True},
        ]}
        result = detect_focus_change(before, after)
        self.assertTrue(result["focus_moved"])
        self.assertTrue(result["tracking_available"])
        self.assertEqual(result["old_focus_id"], "btn_pause")
        self.assertEqual(result["new_focus_id"], "btn_next")
        self.assertEqual(result["new_focus_text"], "下一集")

    def test_detect_focus_change_not_moved(self):
        before = {"id": "root", "children": [
            {"id": "btn_pause", "focused": True},
        ]}
        after = {"id": "root", "children": [
            {"id": "btn_pause", "focused": True, "text": "暂停"},
        ]}
        result = detect_focus_change(before, after)
        self.assertFalse(result["focus_moved"])
        self.assertTrue(result["tracking_available"])

    def test_detect_focus_change_gained(self):
        # 之前没焦点，之后有焦点 → 也算 moved
        before = {"id": "root", "children": []}
        after = {"id": "root", "children": [
            {"id": "btn", "focused": True},
        ]}
        result = detect_focus_change(before, after)
        self.assertTrue(result["focus_moved"])
        self.assertTrue(result["tracking_available"])

    def test_detect_focus_change_no_tracking(self):
        # 两边都没焦点
        before = {"id": "root"}
        after = {"id": "root"}
        result = detect_focus_change(before, after)
        self.assertFalse(result["focus_moved"])
        self.assertFalse(result["tracking_available"])


# ═══════════════ Keymaps Tests ═══════════════

class TestKeymaps(unittest.TestCase):

    def test_list_apps(self):
        apps = list_apps()
        self.assertIn("aiqiyi", apps)
        self.assertIn("tencent", apps)
        self.assertIn("quark", apps)

    def test_get_keymap_aiqiyi_player(self):
        km = get_keymap("aiqiyi", "player_with_bar")
        self.assertIsNotNone(km)
        self.assertIn("btn_pause", km["focusable_elements"])
        self.assertEqual(km["layout"], "horizontal_row")

    def test_get_keymap_tencent_speed(self):
        km = get_keymap("tencent", "speed_panel")
        self.assertIsNotNone(km)
        self.assertEqual(km["layout"], "vertical_list")

    def test_get_keymap_unknown(self):
        self.assertIsNone(get_keymap("unknown_app", "player_with_bar"))
        self.assertIsNone(get_keymap("aiqiyi", "unknown_context"))
        self.assertIsNone(get_keymap(None, "player_with_bar"))

    def test_list_contexts(self):
        ctxs = list_contexts("aiqiyi")
        self.assertIn("player_with_bar", ctxs)
        self.assertIn("speed_panel", ctxs)
        self.assertEqual(list_contexts("unknown_app"), [])

    def test_direction_keys(self):
        self.assertEqual(DIRECTION_TO_KEY["UP"], "UP")
        self.assertEqual(DIRECTION_TO_KEY["DOWN"], "DOWN")
        self.assertIn("LEFT", DIRECTION_TO_KEY)
        self.assertIn("RIGHT", DIRECTION_TO_KEY)

    def test_opposite_direction(self):
        self.assertEqual(OPPOSITE_DIRECTION["UP"], "DOWN")
        self.assertEqual(OPPOSITE_DIRECTION["LEFT"], "RIGHT")


# ═══════════════ Direction Normalization Tests ═══════════════

class TestDirectionNormalization(unittest.TestCase):

    def test_english(self):
        self.assertEqual(_normalize_direction("UP"), "UP")
        self.assertEqual(_normalize_direction("down"), "DOWN")
        self.assertEqual(_normalize_direction("  LEFT  "), "LEFT")
        self.assertEqual(_normalize_direction("RIGHT"), "RIGHT")

    def test_chinese(self):
        self.assertEqual(_normalize_direction("上"), "UP")
        self.assertEqual(_normalize_direction("下"), "DOWN")
        self.assertEqual(_normalize_direction("左"), "LEFT")
        self.assertEqual(_normalize_direction("右"), "RIGHT")
        self.assertEqual(_normalize_direction("向上"), "UP")
        self.assertEqual(_normalize_direction("向右"), "RIGHT")

    def test_unknown(self):
        self.assertIsNone(_normalize_direction(""))
        self.assertIsNone(_normalize_direction(None))
        self.assertIsNone(_normalize_direction("DIAGONAL"))


if __name__ == "__main__":
    unittest.main()
