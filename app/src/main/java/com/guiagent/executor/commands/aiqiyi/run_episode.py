# -*- coding: utf-8 -*-
"""爱奇艺选集控制（支持综艺和电视剧，自适应布局）。

包名: com.qiyi.video.speaker (中屏定制版)

选集面板类型（自动检测）:
  1. 综艺：垂直列表（每行一期，含标题/副标题/日期）
  2. 电视剧：网格布局（N 列 × M 行，单集格子）

可见性过滤与滚动对齐:
  目标内容位移 = (可见行数 - 1) × 中位数行高。
  效果: 原本在最后一行的项滚到新一页第一行位置, 顶格对齐标题下沿。

  由于 swipe 手指距离 vs 内容位移 ≈ 2:3 (实测爱奇艺播放器),
  要产生 ~596px 内容位移需要 ~894px 手指距离, 超出视口能容纳的最大 swipe。
  解决方案: 拆成 2 次 swipe (每次 ~447px), 合计达到目标内容位移。

  翻页后用 _check_scroll_success() 验证: 是否有正常高度 (h > 50px) 的 item
  其 top 对齐标题下沿 (episodePanelTitle 的 bottom ≈ y=93, 容差 10px)。

命令:
  open          打开选集面板（面板保持打开，显示当前列表）
  list          显示当前可见列表（面板需已打开）
  scroll up N   向上滚动 N 次（面板保持打开）
  scroll down N 向下滚动 N 次（面板保持打开）
  select N      选择第 N 个可见项（选择后面板关闭）
  close         手动关闭面板
  next          下一集（不需要打开面板，点控制条 im_play_next）

用法:
  python aiqiyi/run-episode.py open              # 打开选集面板
  python aiqiyi/run-episode.py list              # 显示当前可见列表
  python aiqiyi/run-episode.py scroll up 2       # 向上滚动 2 次
  python aiqiyi/run-episode.py scroll down 1     # 向下滚动 1 次
  python aiqiyi/run-episode.py select 3          # 选择第 3 个
  python aiqiyi/run-episode.py close             # 关闭面板
  python aiqiyi/run-episode.py next              # 下一集

工作流示例:
  1. python aiqiyi/run-episode.py open           # 打开面板
  2. python aiqiyi/run-episode.py list           # 查看列表
  3. python aiqiyi/run-episode.py scroll up 1    # 向上滚一次
  4. python aiqiyi/run-episode.py list           # 查看新列表
  5. python aiqiyi/run-episode.py select 2       # 选择第 2 个

前置: 已在爱奇艺播放页。
      设备已开 GUIAgent 无障碍, 且 adb forward tcp:8322 tcp:8322。
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from send import send
from common.utils import success, error, remote_key, parse_count

# ── 坐标常量 ──
WAKE_X, WAKE_Y = 640, 200        # 唤控制条(顶部)
NEXT_X, NEXT_Y = 177, 724        # im_play_next
EPISODE_BTN_X, EPISODE_BTN_Y = 1212, 724   # tv_change_episode
CLOSE_X, CLOSE_Y = 1237, 53      # 面板右上角 close(不能用 back,会退出播放页)

# 选集面板滚动区域(面板右侧中部)
# swipe 必须在中段进行 (y ∈ [SCROLL_Y_MIN, SCROLL_Y_MAX]),
# 不能从屏幕底部起滑, 否则会触发"上滑关闭应用"手势
SCROLL_X = 1010
SCROLL_Y_MIN = 250    # swipe 区域上边界
SCROLL_Y_MAX = 650    # swipe 区域下边界
SCROLL_Y_MID = (SCROLL_Y_MIN + SCROLL_Y_MAX) // 2  # 中心 = 450


def op(i, name, **args):
    r = send({"id": str(i), "op": name, "args": args})
    print(f"[{i}] {name} -> ok={r.get('ok')} "
          f"{json.dumps(r.get('data', r.get('err')), ensure_ascii=False)}")
    return r


def find_episode_items():
    """从 dump 中提取所有可选集项。

    自适应两种布局:
      - 综艺(list): episodeGridView 子节点含 episode_list_item_title
      - 电视剧(grid): episodeGridView 子节点含 episode_item

    只返回**用户实际可见**的项（item 至少 50% 高度在 episodeGridView 可见区域内）。

    Returns:
        list of (cx, cy, title, layout_type)
        layout_type: 'list' 或 'grid'
    """
    resp = send({"id": "find_ep", "op": "dump",
                 "args": {"depth": 6, "include": ["bounds", "id", "text", "clickable"]}})
    if not resp.get("ok"):
        return [], "unknown"

    # 找 episodeGridView (它就是可见区域的 viewport)
    gridview = None

    def find_gridview(node):
        nonlocal gridview
        if "episodeGridView" in node.get("id", ""):
            gridview = node
            return
        for c in node.get("children", []):
            find_gridview(c)

    find_gridview(resp["data"].get("window", {}))
    if gridview is None:
        return [], "unknown"

    items = []
    layout_type = None

    # 第一遍: 收集所有 item 的原始数据
    raw_items = []
    for child in gridview.get("children", []):
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

        # 在孙子节点里找标题
        title = ""
        is_list = False
        is_grid = False

        def scan(node):
            nonlocal title, is_list, is_grid
            nid = node.get("id", "")
            short = nid.split("/")[-1] if "/" in nid else nid
            if short == "episode_list_item_title" and not title:
                title = node.get("text", "")
                is_list = True
            elif short == "episode_item":
                title = node.get("text", "")
                is_grid = True
            for gc in node.get("children", []):
                scan(gc)

        scan(child)
        if is_list or is_grid:
            raw_items.append((cx, cy, title, ih, "list" if is_list else "grid"))

    if not raw_items:
        return [], "unknown"

    # 计算中位数高度，过滤掉被裁剪到几乎看不见的(高度 < 中位数 25%)
    # 仅过滤极端情况(如只剩几毫米边边); 正常半截露出的保留
    heights = sorted(it[3] for it in raw_items)
    median_h = heights[len(heights) // 2]
    threshold = median_h * 0.25

    for cx, cy, title, ih, lt in raw_items:
        if ih >= threshold:
            items.append((cx, cy, title, lt))

    if items:
        layout_type = items[0][3]
    else:
        layout_type = "unknown"

    # 按 y 再 x 排序(网格需要行优先)
    items.sort(key=lambda x: (x[1], x[0]))
    return items, layout_type


def show_list(items, layout_type):
    """显示剧集列表。"""
    if not items:
        print("\n未找到剧集(面板可能未打开)")
        return

    print(f"\n面板类型: {layout_type}")
    print(f"当前可见 {len(items)} 项:")

    if layout_type == 'grid':
        # 推断列数: 看有多少个不同的 y 值算一行
        ys = sorted(set(it[1] for it in items))
        # 同 y 容差 20px 算一行
        rows = []
        for y in ys:
            row = [it for it in items if abs(it[1] - y) < 20]
            rows.append(row)
        cols = max(len(r) for r in rows) if rows else 1
        print(f"(网格布局: {cols} 列)")
        idx = 1
        for r in rows:
            for cx, cy, title, _ in r:
                t_short = title[:20] if len(title) > 20 else title
                print(f"  {idx:2d}. ({cx},{cy}) {t_short}")
                idx += 1
    else:
        print("(垂直列表)")
        for i, (cx, cy, title, _) in enumerate(items, 1):
            t_short = title[:30] if len(title) > 30 else title
            print(f"  {i:2d}. ({cx},{cy}) {t_short}")


def do_open():
    """打开选集面板(带重试)。"""
    print("打开选集面板...")

    items = []
    for attempt in range(3):
        # 唤控制条
        send({"id": f"1.{attempt}", "op": "tap", "args": {"x": WAKE_X, "y": WAKE_Y}})
        time.sleep(2.0)
        # 点选集按钮
        send({"id": f"2.{attempt}", "op": "tap",
              "args": {"x": EPISODE_BTN_X, "y": EPISODE_BTN_Y}})
        time.sleep(1.8)

        items, layout_type = find_episode_items()
        if items:
            break

        if attempt < 2:
            print(f"面板未正确打开, 重试 {attempt + 1}/3...")
            time.sleep(0.5)

    if not items:
        print("\n错误: 无法打开选集面板")
        print("可能原因:")
        print("  1. 当前页面不支持选集(如电影)")
        print("  2. 控制条未正确唤出")
        print("  3. 选集按钮位置变化")
        return

    show_list(items, layout_type)
    print(f"\n选集面板已打开(保持打开状态)")
    print("提示: list 查看 / scroll N 滚动 / select N 选择 / close 关闭")


def do_list():
    """显示当前可见列表。"""
    print("获取当前列表...")
    items, layout_type = find_episode_items()
    show_list(items, layout_type)


# swipe 距离 vs 内容位移的比例 (实测爱奇艺播放器 ≈ 2/3)
SWIPE_TO_CONTENT_RATIO = 0.667


def _page_scroll_plan():
    """计算翻页计划: 每次 swipe 的距离 × 次数。

    目标内容位移 = (可见行数 - 1) × 中位数行高
    (让原最后一行顶到新一页第一行位置, 对齐标题下沿)

    由于 swipe:content ≈ 2:3, 手指距离 = 内容位移 / 0.667。
    如果超出视口能容纳的最大 swipe, 拆成多次。
    """
    resp = send({"id": "plan", "op": "dump",
                 "args": {"depth": 5, "include": ["bounds", "id", "clickable"]}})
    if not resp.get("ok"):
        return 450, 2  # fallback

    gridview = None

    def find_grid(node):
        nonlocal gridview
        if "episodeGridView" in node.get("id", ""):
            gridview = node
            return
        for c in node.get("children", []):
            find_grid(c)

    find_grid(resp["data"].get("window", {}))
    if gridview is None:
        return 450, 2

    heights = []
    for c in gridview.get("children", []):
        if not c.get("clickable", False):
            continue
        b = c.get("bounds", {})
        h = b.get("b", 0) - b.get("t", 0)
        if h > 20:
            heights.append(h)

    if len(heights) < 2:
        return 450, 2

    heights.sort()
    median_h = heights[len(heights) // 2]
    visible_count = len(heights)

    # 目标内容位移: (可见行数-1) 行
    target_content = (visible_count - 1) * median_h

    # 总手指距离
    total_finger = target_content / SWIPE_TO_CONTENT_RATIO

    # 视口内最大 swipe (y ∈ [SCROLL_Y_MIN, SCROLL_Y_MAX], 只在屏幕中段滑)
    max_swipe = SCROLL_Y_MAX - SCROLL_Y_MIN  # 400

    # 拆成 N 次, 每次不超过 max_swipe
    n_swipes = max(1, -(-int(total_finger) // int(max_swipe)))  # ceil div
    each_swipe = int(total_finger / n_swipes)

    return each_swipe, n_swipes


def _check_scroll_success():
    """检查翻页是否成功: 是否有 item 的 top 对齐标题下沿。

    标题 episodePanelTitle 的下沿 ≈ episodeGridView 的顶部 (y=93)。
    翻页成功后, 应该有一个 item 的 top ≈ 这个值 (容差 10px)。
    """
    resp = send({"id": "check_scroll", "op": "dump",
                 "args": {"depth": 5, "include": ["bounds", "id", "clickable"]}})
    if not resp.get("ok"):
        return False, None

    # 找标题下沿
    title_bottom = None

    def find_title(node):
        nonlocal title_bottom
        if "episodePanelTitle" in node.get("id", ""):
            title_bottom = node.get("bounds", {}).get("b")
            return
        for c in node.get("children", []):
            find_title(c)

    find_title(resp["data"].get("window", {}))
    if title_bottom is None:
        return False, None

    # 找 gridview 里 top 对齐标题下沿的 item
    gridview = None

    def find_grid(node):
        nonlocal gridview
        if "episodeGridView" in node.get("id", ""):
            gridview = node
            return
        for c in node.get("children", []):
            find_grid(c)

    find_grid(resp["data"].get("window", {}))
    if gridview is None:
        return False, None

    for c in gridview.get("children", []):
        if not c.get("clickable", False):
            continue
        b = c.get("bounds", {})
        t = b.get("t", -1)
        h = b.get("b", 0) - t
        # 必须高度合理 (> 中位数的 50%), 排除只剩几像素的残影
        if abs(t - title_bottom) <= 10 and h > 50:
            return True, t

    return False, None


def _panel_is_open():
    """检查选集面板是否还开着 (避免 overscroll 把面板关了还继续翻)。"""
    r = send({"id": "chk", "op": "find",
              "args": {"id": "episodeGridView", "limit": 1}})
    return bool(r.get("ok") and r.get("data", {}).get("nodes"))


def _get_top_item_title():
    """返回当前最顶部 item 的标题 (用于翻页前后对比, 检测边界)。"""
    items, _ = find_episode_items()
    if items:
        return items[0][2]
    return None


def do_scroll(direction, times):
    """滚动选集列表。direction: 'up' 或 'down'。

    每次"翻页"可能由 1~N 次 swipe 组成 (按 swipe:content=2:3 比例换算,
    超出视口的拆成多次), 目标内容位移 = (可见行数-1) × 行高,
    让原最后一行顶到新一页第一行, 对齐标题下沿。

    边界保护 (两道):
      1. 翻页前后比较顶部 item 标题, 没变 = 已到达边界, 停止
      2. 翻页后检查面板是否还在, 关了 = overscroll 触发关闭, 停止
    """
    print(f"向{direction}滚动 {times} 次...")

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

    # 验证翻页: 是否有 item 的 top 对齐标题下沿
    if _panel_is_open():
        ok, aligned_t = _check_scroll_success()
        if ok:
            print(f"[翻页成功] 有 item 顶格对齐标题下沿 (y={aligned_t})")
        else:
            print("[翻页可能未到位] 未检测到 item 对齐标题下沿")

        items, layout_type = find_episode_items()
        show_list(items, layout_type)
    else:
        print("[面板已关闭] 无法显示列表")


def _detect_grid_cols(items):
    """网格布局: 检测列数 (按 x 坐标分组, 数有多少个不同的 x)。

    比"数第一行有几个"更稳: 即使某行首列被过滤, 其他行仍有完整列。
    """
    if not items:
        return 1
    # 按 x 分组 (容差 30px, 同列 x 相差不会超过这个)
    xs = []
    for cx, _, _, _ in items:
        # 找已有组里最近的 (容差 30px)
        matched = False
        for i, x in enumerate(xs):
            if abs(cx - x) < 30:
                matched = True
                break
        if not matched:
            xs.append(cx)
    return len(xs)


def _group_items_by_row(items):
    """把 items 按 y 坐标分组为视觉行。

    同一 y (容差 30px) 的 items 归为一行; 行内按 x 排序;
    行与行按 y 排序。返回 list[list[item]]。

    比线性索引稳: 即使某行首列被过滤, 其余行仍按真实视觉行分组。
    """
    rows = []
    for item in items:
        cx, cy, title, lt = item
        matched = False
        for row in rows:
            if abs(cy - row[0][1]) < 30:
                row.append(item)
                matched = True
                break
        if not matched:
            rows.append([item])
    # 行内按 x, 行间按 y
    for row in rows:
        row.sort(key=lambda it: it[0])
    rows.sort(key=lambda r: r[0][1])
    return rows


def do_select(args):
    """选择项。

    args 可以是:
      - [N]:        选择第 N 个可见项 (通用, 列表/网格都行)
      - [row, col]: 选择第 row 行第 col 列 (网格布局专用, 更直观)
    """
    items, layout_type = find_episode_items()

    if not items:
        print("\n未找到剧集, 面板可能未打开")
        print("提示: 先运行 'open' 打开面板")
        return

    # 解析参数
    if len(args) == 1:
        # 单参数: 优先按集数匹配，失败则按位置
        try:
            n = int(args[0])
        except ValueError:
            sys.exit(f"序号非法: {args[0]}")

        # 尝试按集数匹配（标题 == str(n)）
        target = None
        for item in items:
            if item[2] == str(n):  # title == episode number
                target = item
                desc = f"第 {n} 集"
                break

        # 没找到则按位置
        if target is None:
            if n < 1 or n > len(items):
                print(f"\n集数 {n} 不存在且序号超出范围 (当前可见 {len(items)} 项)")
                show_list(items, layout_type)
                return
            target = items[n - 1]
            desc = f"第 {n} 个可见项 (集数 {n} 缺失)"
    elif len(args) == 2:
        # 双参数: row col (网格布局)
        if layout_type != 'grid':
            sys.exit(f"当前面板是 {layout_type} 布局, 不支持 row/col 选择, 请用 select N")
        try:
            row, col = int(args[0]), int(args[1])
        except ValueError:
            sys.exit(f"行列非法: {args[0]} {args[1]}")
        if row < 1 or col < 1:
            sys.exit(f"行列非法: row={row} col={col} (须 >= 1)")
        rows = _group_items_by_row(items)
        if row > len(rows):
            print(f"\n行超出范围: row={row} (当前 {len(rows)} 行)")
            show_list(items, layout_type)
            return
        if col > len(rows[row - 1]):
            print(f"\n列超出范围: col={col} (第 {row} 行只有 {len(rows[row - 1])} 列)")
            show_list(items, layout_type)
            return
        target = rows[row - 1][col - 1]
        desc = f"第 {row} 行第 {col} 列"
    else:
        sys.exit("用法: python aiqiyi/run-episode.py select N 或 select <行> <列>")

    cx, cy, title, _ = target
    send({"id": "31", "op": "tap", "args": {"x": cx, "y": cy}})

    t_short = title[:30] if len(title) > 30 else title
    print(f"\n已选择 {desc}: {t_short}")
    print(f"坐标: ({cx},{cy})")
    print("选集面板已关闭, 开始播放")


def do_close():
    """关闭选集面板。"""
    print("关闭选集面板...")
    send({"id": "40", "op": "tap", "args": {"x": CLOSE_X, "y": CLOSE_Y}})
    print("选集面板已关闭")


def do_next():
    """下一集(点控制条 im_play_next)。"""
    print("下一集...")
    send({"id": "50", "op": "tap", "args": {"x": WAKE_X, "y": WAKE_Y}})
    time.sleep(1.5)
    send({"id": "51", "op": "tap", "args": {"x": NEXT_X, "y": NEXT_Y}})
    print("已切换到下一集")


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python aiqiyi/run-episode.py open              # 打开选集面板")
        print("  python aiqiyi/run-episode.py list              # 显示当前列表")
        print("  python aiqiyi/run-episode.py scroll up N       # 向上滚动 N 次")
        print("  python aiqiyi/run-episode.py scroll down N     # 向下滚动 N 次")
        print("  python aiqiyi/run-episode.py select N          # 选择第 N 个")
        print("  python aiqiyi/run-episode.py select R C        # 选择第 R 行第 C 列 (网格)")
        print("  python aiqiyi/run-episode.py close             # 关闭面板")
        print("  python aiqiyi/run-episode.py next              # 下一集")
        print("\n支持两种面板类型(自动检测):")
        print("  - 综艺:   垂直列表(每行一期, 含标题/副标题/日期)")
        print("  - 电视剧: 网格布局(N 列 × M 行)")
        print("\n工作流示例:")
        print("  1. python aiqiyi/run-episode.py open           # 打开面板")
        print("  2. python aiqiyi/run-episode.py scroll up 2    # 向上滚 2 次")
        print("  3. python aiqiyi/run-episode.py select 3       # 选择第 3 个")
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
            sys.exit("用法: python aiqiyi/run-episode.py scroll <up|down> <次数>")
        direction = sys.argv[2].lower()
        if direction not in ("up", "down"):
            sys.exit(f"方向非法: {sys.argv[2]} (须 up 或 down)")
        try:
            times = int(sys.argv[3])
            if times < 1:
                sys.exit(f"次数非法: {times} (须 >= 1)")
        except ValueError:
            sys.exit(f"次数非法: {sys.argv[3]}")
        do_scroll(direction, times)
    elif cmd == "select":
        if len(sys.argv) < 3:
            sys.exit("用法: python aiqiyi/run-episode.py select <序号> 或 select <行> <列>")
        # 接受 select N 或 select R C
        do_select(sys.argv[2:])
    elif cmd == "close":
        do_close()
    elif cmd == "next":
        do_next()
    else:
        sys.exit(f"未知命令: {cmd}\n可选: open / list / scroll / select / close / next")


# ── Registry 入口函数 ──

def run_open(params=None):
    """aiqiyi.open_episode_panel — 打开选集面板。"""
    do_open()
    return success("aiqiyi.open_episode_panel", "episode_panel_opened")


def run_close(params=None):
    """aiqiyi.close_episode_panel — 关闭选集面板。"""
    do_close()
    return success("aiqiyi.close_episode_panel", "episode_panel_closed")


def run_scroll(direction, params=None):
    """aiqiyi.scroll_episode_up / scroll_episode_down — 滚动选集列表。"""
    count = parse_count(params)
    do_scroll(direction, count)
    return success(f"aiqiyi.scroll_episode_{direction}", f"scrolled_{direction}_x{count}")


def run_select(params=None):
    """aiqiyi.select_episode — 选择集数。

    params: {"values": [N]} 或 {"values": [row, col]}
    """
    values = []
    if params:
        raw = params.get("values", params.get("params", []))
        if isinstance(raw, list):
            values = [str(v) for v in raw]
    if not values:
        return error("BAD_PARAMS", "Missing parameter: values")
    do_select(values)
    return success("aiqiyi.select_episode", "episode_selected")


def run_next(params=None):
    """aiqiyi.next_episode — 下一集。"""
    do_next()
    return success("aiqiyi.next_episode", "next_episode")


def run_prev(params=None):
    """aiqiyi.prev_episode — 上一集（使用 MEDIA_PREVIOUS 按键）。"""
    r = remote_key("MEDIA_PREVIOUS", duration=1800)
    if r.get("ok"):
        return success("aiqiyi.prev_episode", "prev_episode")
    err = r.get("error", {})
    return error(err.get("code", "EXECUTION_FAILED"),
                 err.get("message", "remote_key MEDIA_PREVIOUS failed"))


if __name__ == "__main__":
    main()
