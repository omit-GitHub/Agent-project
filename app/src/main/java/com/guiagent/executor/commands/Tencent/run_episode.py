# -*- coding: utf-8 -*-
"""腾讯视频选集控制（支持综艺和电视剧，自适应布局）。

包名: com.tencent.qqlive.audiobox (中屏定制版)

选集面板类型（自动检测）:
  1. 综艺：垂直列表（每行一期，含标题）
  2. 电视剧：网格布局（N 列 × M 行，单集格子）

UI 结构:
  - viewport: swipe_target (RecyclerView)
  - items: container (RelativeLayout), desc = 集数/标题
  - 无面板标题，无关闭按钮（点左侧空白区域关闭）
  - swipe:content 比例 ≈ 1:1（实测腾讯视频）

可见性过滤与滚动对齐:
  目标内容位移 = (可见行数 - 1) × 中位数行高。
  翻页后用 _check_scroll_success() 验证: 是否有正常高度的 item 其 top 对齐 viewport 顶部。

  swipe:content ≈ 1:1，手指距离 ≈ 内容位移。

命令:
  open          打开选集面板（面板保持打开，显示当前列表）
  list          显示当前可见列表（面板需已打开）
  scroll up N   向上滚动 N 次（面板保持打开）
  scroll down N 向下滚动 N 次（面板保持打开）
  select N      选择第 N 个可见项（选择后面板关闭）
  select R C    选择第 R 行第 C 列（网格布局专用）
  close         手动关闭面板
  next          下一集（不需要打开面板，点控制条 nextPlay）

用法:
  python Tencent/run-episode.py open              # 打开选集面板
  python Tencent/run-episode.py list              # 显示当前可见列表
  python Tencent/run-episode.py scroll up 2       # 向上滚动 2 次
  python Tencent/run-episode.py scroll down 1     # 向下滚动 1 次
  python Tencent/run-episode.py select 3          # 选择第 3 个
  python Tencent/run-episode.py select 2 3        # 选择第 2 行第 3 列（网格）
  python Tencent/run-episode.py close             # 关闭面板
  python Tencent/run-episode.py next              # 下一集

工作流示例:
  1. python Tencent/run-episode.py open           # 打开面板
  2. python Tencent/run-episode.py list           # 查看列表
  3. python Tencent/run-episode.py scroll up 1    # 向上滚一次
  4. python Tencent/run-episode.py list           # 查看新列表
  5. python Tencent/run-episode.py select 2       # 选择第 2 个

前置: 已在腾讯视频播放页。
      设备已开 GUIAgent 无障碍, 且 adb forward tcp:8322 tcp:8322。
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from send import send

# 让本脚本也能找到 common/utils.py（供 run_*() 函数使用）
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from common.utils import (  # noqa: E402
    success, success_with_data, error as make_error, parse_count,
)

# ── 坐标常量 ──
WAKE_X, WAKE_Y = 640, 200        # 唤控制条(顶部)
NEXT_X, NEXT_Y = 214, 749        # nextPlay
EPISODE_BTN_X, EPISODE_BTN_Y = 828, 749   # episode_select_list
CLOSE_X, CLOSE_Y = 200, 400      # 面板左侧空白区域(点击关闭面板)

# 选集面板滚动区域(面板中部, 避开屏幕边缘)
# swipe_target 大致在 x=609-1238, y=6-794
# swipe 必须在中段进行, 不能从屏幕底部起滑, 避免触发系统手势
SCROLL_X = 920
SCROLL_Y_MIN = 200    # swipe 区域上边界
SCROLL_Y_MAX = 600    # swipe 区域下边界
SCROLL_Y_MID = (SCROLL_Y_MIN + SCROLL_Y_MAX) // 2  # 中心 = 400

# swipe 距离 vs 内容位移的比例 (实测腾讯视频 ≈ 1:1)
SWIPE_TO_CONTENT_RATIO = 1.0


def op(i, name, **args):
    r = send({"id": str(i), "op": name, "args": args})
    print(f"[{i}] {name} -> ok={r.get('ok')} "
          f"{json.dumps(r.get('data', r.get('err')), ensure_ascii=False)}")
    return r


def find_episode_items():
    """从 dump 中提取所有可选集项。

    自适应两种布局:
      - 综艺(list): 垂直列表，每行一项
      - 电视剧(grid): 网格布局，多列

    只返回**用户实际可见**的项（item 至少 25% 高度在 swipe_target 可见区域内）。

    Returns:
        items: list of (cx, cy, title, layout_type)
        layout_type: 'list' 或 'grid'
    """
    resp = send({"id": "find_ep", "op": "dump",
                 "args": {"depth": 10, "include": ["bounds", "id", "text", "desc", "clickable"]}})
    if not resp.get("ok"):
        return [], "unknown"

    # 找 swipe_target (它就是可见区域的 viewport)
    swipe_target = None

    def find_viewport(node):
        nonlocal swipe_target
        if "swipe_target" in node.get("id", ""):
            swipe_target = node
            return
        for c in node.get("children", []):
            find_viewport(c)

    find_viewport(resp["data"].get("window", {}))
    if swipe_target is None:
        return [], "unknown"

    items = []

    # 收集所有 item 的原始数据
    raw_items = []
    for child in swipe_target.get("children", []):
        if not child.get("clickable", False):
            continue
        b = child.get("bounds", {})
        it = b.get("t", 0)
        ib = b.get("b", 0)
        ih = ib - it
        if ih <= 0:
            continue

        cx = (b.get("l", 0) + b.get("r", 0)) // 2
        cy = (it + ib) // 2

        # 集数/标题在 desc 里
        title = child.get("desc", "") or child.get("text", "")
        if not title:
            continue

        raw_items.append((cx, cy, title, ih))

    if not raw_items:
        return [], "unknown"

    # 计算中位数高度，过滤掉被裁剪到几乎看不见的（高度 < 中位数 25%）
    heights = sorted(it[3] for it in raw_items)
    median_h = heights[len(heights) // 2]
    threshold = median_h * 0.25

    for cx, cy, title, ih in raw_items:
        if ih >= threshold:
            items.append((cx, cy, title))

    if not items:
        return [], "unknown"

    # 检测布局类型: 按 y 坐标分组，看同一行有多少个
    layout_type = _detect_layout(items)

    # 按 y 再 x 排序(网格需要行优先)
    items.sort(key=lambda x: (x[1], x[0]))
    return items, layout_type


def _detect_layout(items):
    """检测布局类型（网格 or 列表）。

    按 y 坐标分组（容差 20px），看有多少行有 2+ 个元素。
    如果有 2+ 行每行 2+ 个元素 → 网格；否则 → 列表。
    """
    if len(items) < 2:
        return 'list'

    y_groups = {}
    tolerance = 20
    for cx, cy, title in items:
        matched = False
        for key in y_groups:
            if abs(cy - key) < tolerance:
                y_groups[key].append((cx, cy, title))
                matched = True
                break
        if not matched:
            y_groups[cy] = [(cx, cy, title)]

    grid_rows = sum(1 for group in y_groups.values() if len(group) >= 2)
    return 'grid' if grid_rows >= 2 else 'list'


def _detect_grid_cols(items):
    """网格布局: 检测列数（按 x 坐标分组）。"""
    if not items:
        return 1
    xs = []
    for cx, _, _ in items:
        matched = False
        for x in xs:
            if abs(cx - x) < 30:
                matched = True
                break
        if not matched:
            xs.append(cx)
    return len(xs)


def _group_items_by_row(items):
    """把 items 按 y 坐标分组为视觉行。

    同一 y（容差 30px）的 items 归为一行；行内按 x 排序；
    行与行按 y 排序。返回 list[list[item]]。
    """
    rows = []
    for item in items:
        cx, cy, title = item
        matched = False
        for row in rows:
            if abs(cy - row[0][1]) < 30:
                row.append(item)
                matched = True
                break
        if not matched:
            rows.append([item])
    # 行内按 x，行间按 y
    for row in rows:
        row.sort(key=lambda it: it[0])
    rows.sort(key=lambda r: r[0][1])
    return rows


def show_list(items, layout_type):
    """显示剧集列表。"""
    if not items:
        print("\n未找到剧集（面板可能未打开）")
        return

    print(f"\n面板类型: {layout_type}")
    print(f"当前可见 {len(items)} 项:")

    if layout_type == 'grid':
        cols = _detect_grid_cols(items)
        print(f"(网格布局: {cols} 列)")
        idx = 1
        rows = _group_items_by_row(items)
        for row in rows:
            for cx, cy, title in row:
                t_short = title[:20] if len(title) > 20 else title
                print(f"  {idx:2d}. ({cx},{cy}) {t_short}")
                idx += 1
    else:
        print("(垂直列表)")
        for i, (cx, cy, title) in enumerate(items, 1):
            t_short = title[:30] if len(title) > 30 else title
            print(f"  {i:2d}. ({cx},{cy}) {t_short}")


def do_open():
    """打开选集面板（带重试）。"""
    print("打开选集面板...")

    items = []
    for attempt in range(3):
        # 先检查控制条是否已可见
        r = send({"id": f"0.{attempt}", "op": "find",
                  "args": {"id": "episode_select_list", "limit": 1}})
        controlbar_visible = bool(r.get("ok") and r.get("data", {}).get("nodes"))

        if not controlbar_visible:
            # 控制条不可见，先唤出
            send({"id": f"1.{attempt}", "op": "tap", "args": {"x": WAKE_X, "y": WAKE_Y}})
            time.sleep(1.5)

        # 点选集按钮（用 click_node 更可靠）
        r = send({"id": f"2.{attempt}", "op": "click_node",
                  "args": {"id": "com.tencent.qqlive.audiobox:id/episode_select_list"}})
        if not r.get("ok"):
            # 降级到坐标 tap
            send({"id": f"2b.{attempt}", "op": "tap",
                  "args": {"x": EPISODE_BTN_X, "y": EPISODE_BTN_Y}})
        time.sleep(1.0)

        items, layout_type = find_episode_items()
        if items:
            break

        if attempt < 2:
            print(f"面板未正确打开, 重试 {attempt + 1}/3...")
            time.sleep(0.5)

    if not items:
        print("\n错误: 无法打开选集面板")
        print("可能原因:")
        print("  1. 当前页面不支持选集（如电影）")
        print("  2. 控制条未正确唤出")
        print("  3. 选集按钮位置变化")
        return

    show_list(items, layout_type)
    print(f"\n选集面板已打开（保持打开状态）")
    print("提示: list 查看 / scroll up|down N 滚动 / select N 或 select R C 选择 / close 关闭")


def do_list():
    """显示当前可见列表。"""
    print("获取当前列表...")
    items, layout_type = find_episode_items()
    show_list(items, layout_type)


def _page_scroll_plan():
    """计算翻页计划: 每次 swipe 的距离 × 次数。

    目标内容位移 = (可见行数 - 1) × 中位数行高
    (让原最后一行顶到新一页第一行位置，对齐 viewport 顶部)

    swipe:content ≈ 1:1（实测腾讯视频），手指距离 ≈ 内容位移。
    如果超出视口能容纳的最大 swipe，拆成多次。
    """
    resp = send({"id": "plan", "op": "dump",
                 "args": {"depth": 10, "include": ["bounds", "id", "clickable"]}})
    if not resp.get("ok"):
        return 300, 1  # fallback

    # 找 swipe_target
    swipe_target = None

    def find_viewport(node):
        nonlocal swipe_target
        if "swipe_target" in node.get("id", ""):
            swipe_target = node
            return
        for c in node.get("children", []):
            find_viewport(c)

    find_viewport(resp["data"].get("window", {}))
    if swipe_target is None:
        return 300, 1

    heights = []
    for c in swipe_target.get("children", []):
        if not c.get("clickable", False):
            continue
        b = c.get("bounds", {})
        h = b.get("b", 0) - b.get("t", 0)
        if h > 20:
            heights.append(h)

    if len(heights) < 2:
        return 300, 1

    heights.sort()
    median_h = heights[len(heights) // 2]
    visible_count = len(heights)

    # 按行分组，计算可见行数
    y_groups = {}
    for c in swipe_target.get("children", []):
        if not c.get("clickable", False):
            continue
        b = c.get("bounds", {})
        h = b.get("b", 0) - b.get("t", 0)
        if h <= 20:
            continue
        cy = (b.get("t", 0) + b.get("b", 0)) // 2
        matched = False
        for key in y_groups:
            if abs(cy - key) < 20:
                y_groups[key] += 1
                matched = True
                break
        if not matched:
            y_groups[cy] = 1

    visible_rows = len(y_groups)

    # 目标内容位移: (可见行数-1) 行
    target_content = (visible_rows - 1) * median_h

    # 总手指距离（swipe:content ≈ 1:1）
    total_finger = target_content / SWIPE_TO_CONTENT_RATIO

    # 视口内最大 swipe
    max_swipe = SCROLL_Y_MAX - SCROLL_Y_MIN  # 400

    # 拆成 N 次，每次不超过 max_swipe
    n_swipes = max(1, -(-int(total_finger) // int(max_swipe)))  # ceil div
    each_swipe = int(total_finger / n_swipes)

    return each_swipe, n_swipes


def _check_scroll_success():
    """检查翻页是否成功: 是否有 item 的 top 对齐 viewport 顶部。

    swipe_target 的顶部 ≈ y=6。
    翻页成功后，应该有一个 item 的 top ≈ 这个值（容差 15px）。
    """
    resp = send({"id": "check_scroll", "op": "dump",
                 "args": {"depth": 10, "include": ["bounds", "id", "clickable"]}})
    if not resp.get("ok"):
        return False, None

    # 找 swipe_target 的 top
    viewport_top = None

    def find_viewport(node):
        nonlocal viewport_top
        if "swipe_target" in node.get("id", ""):
            viewport_top = node.get("bounds", {}).get("t")
            return
        for c in node.get("children", []):
            find_viewport(c)

    find_viewport(resp["data"].get("window", {}))
    if viewport_top is None:
        return False, None

    # 找 swipe_target 里 top 对齐 viewport 顶部的 item
    swipe_target = None

    def find_st(node):
        nonlocal swipe_target
        if "swipe_target" in node.get("id", ""):
            swipe_target = node
            return
        for c in node.get("children", []):
            find_st(c)

    find_st(resp["data"].get("window", {}))
    if swipe_target is None:
        return False, None

    for c in swipe_target.get("children", []):
        if not c.get("clickable", False):
            continue
        b = c.get("bounds", {})
        t = b.get("t", -1)
        h = b.get("b", 0) - t
        # 必须高度合理（> 50px），排除只剩几像素的残影
        if abs(t - viewport_top) <= 15 and h > 50:
            return True, t

    return False, None


def _panel_is_open():
    """检查选集面板是否还开着（避免 overscroll 把面板关了还继续翻）。"""
    r = send({"id": "chk", "op": "find",
              "args": {"id": "swipe_target", "limit": 1}})
    return bool(r.get("ok") and r.get("data", {}).get("nodes"))


def _get_top_item_title():
    """返回当前最顶部 item 的标题（用于翻页前后对比，检测边界）。"""
    items, _ = find_episode_items()
    if items:
        return items[0][2]
    return None


def do_scroll(direction, times):
    """滚动选集列表。direction: 'up' 或 'down'。

    每次"翻页"可能由 1~N 次 swipe 组成，目标内容位移 = (可见行数-1) × 行高。

    边界保护（两道）:
      1. 翻页前后比较顶部 item 标题，没变 = 已到达边界，停止
      2. 翻页后检查面板是否还在，关了 = overscroll 触发关闭，停止
    """
    dir_cn = "上" if direction == "up" else "下"
    print(f"向{dir_cn}滚动 {times} 次...")

    each_swipe, n_swipes = _page_scroll_plan()
    half = each_swipe // 2

    for page in range(times):
        # 翻页前: 先检查面板还在不在
        if not _panel_is_open():
            print(f"[边界] 选集面板已关闭, 停止后续翻页")
            break

        # 翻页前: 记录顶部 item 标题
        before_title = _get_top_item_title()

        # 每次翻页: n_swipes 次 swipe
        for i in range(n_swipes):
            # up: 手指从下往上滑(y1 > y2)
            # down: 手指从上往下滑(y1 < y2)
            if direction == 'up':
                y1 = SCROLL_Y_MID + half
                y2 = SCROLL_Y_MID - half
            else:
                y1 = SCROLL_Y_MID - half
                y2 = SCROLL_Y_MID + half

            y1 = max(SCROLL_Y_MIN, min(SCROLL_Y_MAX, y1))
            y2 = max(SCROLL_Y_MIN, min(SCROLL_Y_MAX, y2))

            send({"id": f"20.{page}.{i}", "op": "swipe",
                  "args": {"x1": SCROLL_X, "y1": y1,
                           "x2": SCROLL_X, "y2": y2, "duration": 300}})
            time.sleep(0.2)
        time.sleep(0.5)

        # 翻页后: 检查面板是否还在
        if not _panel_is_open():
            boundary = "最后一页" if direction == 'up' else "第一页"
            print(f"[边界] 已到达{boundary} (面板被关闭), 停止后续翻页")
            break

        # 翻页后: 检查顶部 item 是否变化
        after_title = _get_top_item_title()
        if before_title and before_title == after_title:
            boundary = "最后一页" if direction == 'up' else "第一页"
            print(f"[边界] 已到达{boundary}, 停止后续翻页")
            break

    # 验证翻页
    if _panel_is_open():
        ok, aligned_t = _check_scroll_success()
        if ok:
            print(f"[翻页成功] 有 item 顶格对齐 viewport 顶部 (y={aligned_t})")
        else:
            print("[翻页可能未到位] 未检测到 item 对齐 viewport 顶部")

        items, layout_type = find_episode_items()
        show_list(items, layout_type)
    else:
        print("[面板已关闭] 无法显示列表")


def do_select(args):
    """选择项。

    args 可以是:
      - [N]:        选择第 N 个可见项（通用，列表/网格都行）
      - [row, col]: 选择第 row 行第 col 列（网格布局专用，更直观）
    """
    items, layout_type = find_episode_items()

    if not items:
        print("\n未找到剧集，面板可能未打开")
        print("提示: 先运行 'open' 打开面板")
        return

    # 解析参数
    if len(args) == 1:
        # 单参数: 第 N 个
        try:
            n = int(args[0])
        except ValueError:
            sys.exit(f"序号非法: {args[0]}")
        if n < 1 or n > len(items):
            print(f"\n序号非法: {n}（当前可见 {len(items)} 项）")
            show_list(items, layout_type)
            return
        target = items[n - 1]
        desc = f"第 {n} 个"
    elif len(args) == 2:
        # 双参数: row col（网格布局）
        if layout_type != 'grid':
            sys.exit(f"当前面板是 {layout_type} 布局，不支持 row/col 选择，请用 select N")
        try:
            row, col = int(args[0]), int(args[1])
        except ValueError:
            sys.exit(f"行列非法: {args[0]} {args[1]}")
        if row < 1 or col < 1:
            sys.exit(f"行列非法: row={row} col={col}（须 >= 1）")
        rows = _group_items_by_row(items)
        if row > len(rows):
            print(f"\n行超出范围: row={row}（当前 {len(rows)} 行）")
            show_list(items, layout_type)
            return
        if col > len(rows[row - 1]):
            print(f"\n列超出范围: col={col}（第 {row} 行只有 {len(rows[row - 1])} 列）")
            show_list(items, layout_type)
            return
        target = rows[row - 1][col - 1]
        desc = f"第 {row} 行第 {col} 列"
    else:
        sys.exit("用法: python Tencent/run-episode.py select N 或 select <行> <列>")

    cx, cy, title = target
    send({"id": "31", "op": "tap", "args": {"x": cx, "y": cy}})

    t_short = title[:30] if len(title) > 30 else title
    print(f"\n已选择 {desc}: {t_short}")
    print(f"坐标: ({cx},{cy})")
    print("选集面板已关闭，开始播放")


def do_close():
    """关闭选集面板。"""
    print("关闭选集面板...")
    send({"id": "40", "op": "tap", "args": {"x": CLOSE_X, "y": CLOSE_Y}})
    print("选集面板已关闭")


def do_next():
    """下一集（点控制条 nextPlay）。"""
    print("下一集...")
    send({"id": "50", "op": "tap", "args": {"x": WAKE_X, "y": WAKE_Y}})
    time.sleep(1.5)
    send({"id": "51", "op": "tap", "args": {"x": NEXT_X, "y": NEXT_Y}})
    print("已切换到下一集")


# ── 可编程接口（对标 Java tencent_java 各命令） ──

def run_open(params=None):
    """打开选集面板（可编程接口）。

    对标 Java: TencentOpenEpisodePanelCommand → tencent.open_episode_panel

    Args:
        params: 可选 dict（当前无参数）

    Returns:
        dict: {"ok": True, "data": {"command": "tencent.open_episode_panel", "result": "panel_opened"}}
    """
    try:
        # 1. 检查面板是否已开
        r = send({"id": "ro0", "op": "find",
                  "args": {"id": "episode_select_list", "limit": 1}})
        controlbar_visible = bool(r.get("ok") and r.get("data", {}).get("nodes"))

        if not controlbar_visible:
            send({"id": "ro1", "op": "tap", "args": {"x": WAKE_X, "y": WAKE_Y}})
            time.sleep(1.5)

        # 2. 点选集按钮
        r = send({"id": "ro2", "op": "click_node",
                  "args": {"id": "com.tencent.qqlive.audiobox:id/episode_select_list"}})
        if not r.get("ok"):
            send({"id": "ro2b", "op": "tap",
                  "args": {"x": EPISODE_BTN_X, "y": EPISODE_BTN_Y}})
        time.sleep(1.0)

        return success("tencent.open_episode_panel", "panel_opened")
    except Exception as e:
        return make_error("EXECUTION_FAILED", str(e))


def run_close(params=None):
    """关闭选集面板（可编程接口）。

    对标 Java: TencentCloseEpisodePanelCommand → tencent.close_episode_panel
    腾讯视频关闭方式: 点左侧空白区域 (200, 400)，无 close 按钮。

    Args:
        params: 可选 dict（当前无参数）

    Returns:
        dict: {"ok": True, "data": {"command": "tencent.close_episode_panel", "result": "panel_closed"}}
    """
    try:
        send({"id": "rc1", "op": "tap", "args": {"x": CLOSE_X, "y": CLOSE_Y}})
        return success("tencent.close_episode_panel", "panel_closed")
    except Exception as e:
        return make_error("EXECUTION_FAILED", str(e))


def run_scroll(direction, params=None):
    """滚动选集面板（可编程接口）。

    对标 Java:
      direction='up'   → TencentScrollEpisodeUpCommand   → tencent.scroll_episode_up
      direction='down' → TencentScrollEpisodeDownCommand → tencent.scroll_episode_down

    Args:
        direction: 'up' 或 'down'
        params: 可选 dict，支持 {"count": N}，默认 1

    Returns:
        dict: {"ok": True, "data": {"command": "tencent.scroll_episode_up|down", "result": "scrolled_..."}}
    """
    direction = direction.lower()
    if direction not in ("up", "down"):
        return make_error("BAD_PARAMS", f"Invalid direction: {direction}. Use 'up' or 'down'")

    count = parse_count(params, default=1, max_val=20)
    cmd_name = f"tencent.scroll_episode_{direction}"

    try:
        do_scroll(direction, count)
        return success(cmd_name, f"scrolled_{direction} x{count}")
    except Exception as e:
        return make_error("EXECUTION_FAILED", str(e))


def run_select(params=None):
    """选择剧集（可编程接口）。

    对标 Java: TencentSelectEpisodeCommand → tencent.select_episode

    Args:
        params: dict，支持以下任一格式:
            {"episode": N}     — 选择第 N 个可见项（从 1 开始）
            {"row": R, "col": C} — 选择第 R 行第 C 列（网格布局专用）
            {"index": N}       — 同 episode（兼容别名）

    Returns:
        dict: {"ok": True, "data": {"command": "tencent.select_episode", "result": "selected_..."}}
    """
    if not params:
        return make_error("BAD_PARAMS", "Missing parameters. Need {episode: N} or {row: R, col: C}")

    try:
        items, layout_type = find_episode_items()
        if not items:
            return make_error("NO_MATCH", "No episode items found (panel may not be open)")

        target = None
        desc = ""

        if "episode" in params or "index" in params:
            n = int(params.get("episode", params.get("index")))
            if n < 1 or n > len(items):
                return make_error("NO_MATCH",
                                  f"Episode {n} out of range ({len(items)} items visible)")
            target = items[n - 1]
            desc = f"episode_{n}_by_position"
        elif "row" in params and "col" in params:
            row, col = int(params["row"]), int(params["col"])
            if row < 1 or col < 1:
                return make_error("BAD_PARAMS", "row/col must be >= 1")
            rows = _group_items_by_row(items)
            if row > len(rows):
                return make_error("NO_MATCH", f"Row {row} out of range ({len(rows)} rows)")
            if col > len(rows[row - 1]):
                return make_error("NO_MATCH",
                                  f"Col {col} out of range (row {row} has {len(rows[row - 1])} cols)")
            target = rows[row - 1][col - 1]
            desc = f"row_{row}_col_{col}"
        else:
            return make_error("BAD_PARAMS", "Need {episode: N} or {row: R, col: C}")

        cx, cy, title = target
        send({"id": "rs31", "op": "tap", "args": {"x": cx, "y": cy}})
        return success("tencent.select_episode",
                       f"selected_{desc} ({len(items)} items)")
    except (ValueError, TypeError) as e:
        return make_error("BAD_PARAMS", f"Invalid parameters: {e}")
    except Exception as e:
        return make_error("EXECUTION_FAILED", str(e))


def run_next(params=None):
    """下一集/期（可编程接口）。

    对标 Java: TencentNextEpisodeCommand → tencent.next_episode

    Args:
        params: 可选 dict（当前无参数）

    Returns:
        dict: {"ok": True, "data": {"command": "tencent.next_episode", "result": "next_episode"}}
    """
    try:
        send({"id": "rn1", "op": "tap", "args": {"x": WAKE_X, "y": WAKE_Y}})
        time.sleep(1.5)
        send({"id": "rn2", "op": "tap", "args": {"x": NEXT_X, "y": NEXT_Y}})
        return success("tencent.next_episode", "next_episode")
    except Exception as e:
        return make_error("EXECUTION_FAILED", str(e))


def run_prev(params=None):
    """上一集/期（可编程接口）。

    对标 Java: TencentPrevEpisodeCommand → tencent.prev_episode
    使用遥控器 MEDIA_PREVIOUS 按键（腾讯不支持侧滑手势）。

    Args:
        params: 可选 dict（当前无参数）

    Returns:
        dict: {"ok": True, "data": {"command": "tencent.prev_episode", "result": "prev_episode"}}
    """
    try:
        send({"id": "rp1", "op": "remote_key",
              "args": {"key": "MEDIA_PREVIOUS", "duration": 1800}})
        return success("tencent.prev_episode", "prev_episode")
    except Exception as e:
        return make_error("EXECUTION_FAILED", str(e))


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python Tencent/run-episode.py open              # 打开选集面板")
        print("  python Tencent/run-episode.py list              # 显示当前列表")
        print("  python Tencent/run-episode.py scroll up N       # 向上滚动 N 次")
        print("  python Tencent/run-episode.py scroll down N     # 向下滚动 N 次")
        print("  python Tencent/run-episode.py select N          # 选择第 N 个")
        print("  python Tencent/run-episode.py select R C        # 选择第 R 行第 C 列（网格）")
        print("  python Tencent/run-episode.py close             # 关闭面板")
        print("  python Tencent/run-episode.py next              # 下一集")
        print("\n支持两种面板类型（自动检测）:")
        print("  - 综艺:   垂直列表（每行一期）")
        print("  - 电视剧: 网格布局（N 列 × M 行）")
        print("\n工作流示例:")
        print("  1. python Tencent/run-episode.py open           # 打开面板")
        print("  2. python Tencent/run-episode.py scroll up 2    # 向上滚 2 次")
        print("  3. python Tencent/run-episode.py select 3       # 选择第 3 个")
        return

    cmd = sys.argv[1]

    r1 = op(0, "ping")
    if not r1.get("ok"):
        sys.exit("ping 失败——确认无障碍服务已开且 adb forward 已建")

    if cmd == "open":
        do_open()
    elif cmd == "list":
        do_list()
    elif cmd == "scroll":
        if len(sys.argv) < 4:
            sys.exit("用法: python Tencent/run-episode.py scroll <up|down> <次数>")
        direction = sys.argv[2].lower()
        if direction not in ("up", "down"):
            sys.exit(f"方向非法: {sys.argv[2]}（须 up 或 down）")
        try:
            times = int(sys.argv[3])
            if times < 1:
                sys.exit(f"次数非法: {times}（须 >= 1）")
        except ValueError:
            sys.exit(f"次数非法: {sys.argv[3]}")
        do_scroll(direction, times)
    elif cmd == "select":
        if len(sys.argv) < 3:
            sys.exit("用法: python Tencent/run-episode.py select <序号> 或 select <行> <列>")
        # 接受 select N 或 select R C
        do_select(sys.argv[2:])
    elif cmd == "close":
        do_close()
    elif cmd == "next":
        do_next()
    else:
        sys.exit(f"未知命令: {cmd}\n可选: open / list / scroll / select / close / next")


if __name__ == "__main__":
    main()
