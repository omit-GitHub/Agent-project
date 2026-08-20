# 遗留 dump/find 调用迁移指南

## 概述

以下文件仍直接调用 `send({"op": "dump"})` 和 `send({"op": "find"})`，需要迁移到 `observe_screen()` 候选匹配模式。

---

## 待迁移文件

### 1. aiqiyi/run_episode.py (4 处)

| 行号 | 调用 | 用途 | 迁移方案 |
|------|------|------|----------|
| 90 | `send({"op": "dump"})` | `find_episode_items()`: 找 episodeGridView 节点，提取可选集项 | 改用 `observe_screen()` + 候选匹配 text 含"第 X 集" |
| 260 | `send({"op": "dump"})` | `_plan_scroll()`: 获取 swipe_target bounds 计算滚动距离 | 改用候选列表中 kind=="container" 的 bbox |
| 317 | `send({"op": "dump"})` | `_check_scroll_success()`: 验证滚动后 item top 对齐 | 改用候选位置对比 |
| 367 | `send({"op": "find"})` | 检查 `swipe_target` 是否存在 | 改用候选列表检查 |

**迁移策略**:
- `find_episode_items()` 改为从 `observe_screen()` 的 candidates 中筛选 text 匹配 `r"第\s*\d+\s*集"` 的项
- `_plan_scroll()` 改为使用候选列表中最大的 container 类型 bbox
- `_check_scroll_success()` 改为对比前后两次 `observe_screen()` 的候选位置变化

---

### 2. Tencent/run_episode.py (6 处)

| 行号 | 调用 | 用途 | 迁移方案 |
|------|------|------|----------|
| 103 | `send({"op": "dump"})` | `find_episode_items()`: 同上 | 同 aiqiyi |
| 268 | `send({"op": "find"})` | 检查 `episode_select_list` 是否存在 | 改用候选检查 |
| 323 | `send({"op": "dump"})` | `_plan_scroll()`: 同上 | 同 aiqiyi |
| 402 | `send({"op": "dump"})` | `_check_scroll_success()`: 同上 | 同 aiqiyi |
| 452 | `send({"op": "find"})` | `_panel_is_open()`: 检查面板是否打开 | 改用候选检查 |
| 627 | `send({"op": "find"})` | `do_open()`: 检查面板是否已开 | 改用候选检查 |

**迁移策略**: 同 aiqiyi

---

## 迁移步骤示例

### 示例：迁移 `find_episode_items()`

**旧代码**:
```python
resp = send({"id": "find_ep", "op": "dump", "args": {"depth": 6}})
window = resp["data"].get("window", {})
# 递归找 episodeGridView → 遍历子节点 → 提取 bounds/text
```

**新代码**:
```python
from observation.screen.cmd_observe_screen import observe_screen
import re

def find_episode_items():
    obs_result = observe_screen()
    if not obs_result.get("ok"):
        return [], "unknown"

    candidates = obs_result.get("data", {}).get("candidates", [])
    items = []
    episode_pattern = re.compile(r"第\s*(\d+)\s*集")

    for c in candidates:
        text = c.get("text", "")
        match = episode_pattern.search(text)
        if match:
            bbox = c.get("bbox_px", {})
            cx = (bbox.get("x1", 0) + bbox.get("x2", 0)) // 2
            cy = (bbox.get("y1", 0) + bbox.get("y2", 0)) // 2
            episode_num = int(match.group(1))
            items.append((cx, cy, text, "grid"))

    items.sort(key=lambda x: (x[1], x[0]))
    return items, "grid" if items else "unknown"
```

---

## 优先级

1. **高**: `find_episode_items()` — 选集功能核心
2. **中**: `_plan_scroll()` — 滚动距离计算
3. **低**: `_check_scroll_success()` — 滚动验证（可选，失败可重试）

---

## 测试验证

迁移后运行:
```bash
python aiqiyi/run_episode.py open
python aiqiyi/run_episode.py list
python aiqiyi/run_episode.py scroll up 1
python aiqiyi/run_episode.py select 3
```

---

**创建时间**: 2026-08-20
**相关 Phase**: Phase 6+7 技术债务
