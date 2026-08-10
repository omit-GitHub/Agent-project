# -*- coding: utf-8 -*-
"""点击播放第 X 个片源:在 whohuatv 搜索结果页(多列网格)上,把片源按
"先从左到右、再从上到下"(逐行,行优先)排序,取第 X 个点击。

用法:
    CLI:  python run-play.py X            # X 从 1 开始
    API:  from run_play import run; run({"index": X})

前置: 当前已在搜索结果页(先跑 `python run-search.py <关键词>`)。
      设备已开 GUIAgent 无障碍服务(ws 随无障碍常驻;PC 直连设备填 GUIAGENT_WS_HOST=<设备IP> 或先 adb forward tcp:8322 tcp:8322)。

点击目标: 每个片源 item 的可点击节点是海报 `pop_mid_content_item_pic`
(clickable=true);标题 `pop_mid_content_item_tv` 不可点击,只用来显示片名。
故: find 海报节点拿 bounds 排序+点击, find 标题节点拿 text 按 cx 配对显示。

排序规则: 主序=行(cy 从上到下),次序=列(cx 从左到右)。同一行靠 cy 容差
判定,容差取节点高度中位数的一半(下限 20px),网格行参差也能归对行。
"""
import json
import sys
import time
from statistics import median
from send import send


def op(i, name, **args):
    r = send({"id": str(i), "op": name, "args": args})
    print(f"[{i}] {name} -> ok={r.get('ok')} "
          f"{json.dumps(r.get('data', r.get('err')), ensure_ascii=False)}")
    return r


def center(b):
    cx = (b.get("l", 0) + b.get("r", 0)) // 2
    cy = (b.get("t", 0) + b.get("b", 0)) // 2
    return cx, cy


def find_retry(i, rid, tries=5, gap=0.6):
    """find 片源节点; RecyclerView 渲染动画期间可能瞬时返回空,故重试。"""
    for k in range(tries):
        r = op(f"{i}.{k}", "find", id=rid, limit=50)
        if r.get("ok"):
            ns = [n for n in r["data"].get("nodes", []) if n.get("bounds") and
                  n["bounds"].get("b", 0) > n["bounds"].get("t", 0)]
            if ns:
                return ns
        time.sleep(gap)
    return []


def run(params=None):
    """播放第 X 个片源（封装为可调用的 API）。

    Args:
        params: 可选 dict，支持:
            {"index": N} — 第 N 个（从 1 开始）
            {"values": [N]} — 同 index
            若不提供，默认 index=1

    Returns:
        dict: {"ok": true/false, "data": {...}} 或 {"ok": false, "error": {...}}
              data 包含 index, title, x, y, total 等字段。
    """
    if params is None:
        params = {}

    # 解析 index
    index = 1
    if "index" in params:
        try:
            index = int(params["index"])
        except (ValueError, TypeError):
            return {"ok": False, "error": {"code": "BAD_PARAMS", "message": "index must be an integer"}}
    elif "values" in params:
        vals = params["values"]
        if isinstance(vals, list) and len(vals) > 0:
            try:
                index = int(vals[0])
            except (ValueError, TypeError):
                return {"ok": False, "error": {"code": "BAD_PARAMS", "message": "values[0] must be an integer"}}

    if index < 1:
        return {"ok": False, "error": {"code": "BAD_PARAMS", "message": "index must be >= 1"}}

    # 1a. 读可点击的海报节点(拿 bounds 排序+点击); RecyclerView 渲染期可能瞬时空,重试
    pics = find_retry(1, "pop_mid_content_item_pic")
    if not pics:
        return {
            "ok": False,
            "error": {
                "code": "NO_MATCH",
                "message": "当前页没有可点击的片源海报——请先跑 run-search.py <关键词> 进入结果页,或结果未加载完。"
            }
        }
    if len(pics) < index:
        return {
            "ok": False,
            "error": {
                "code": "NO_MATCH",
                "message": f"只有 {len(pics)} 条片源,不足第 {index} 个(RecyclerView 可能只渲染了可见项,需上滑加载更多)"
            }
        }

    # 1b. 读标题节点(仅用于显示片名), 按 cx 配对到对应海报
    titles = {}
    tvs = find_retry("t", "pop_mid_content_item_tv")
    for n in tvs:
        if n.get("text"):
            titles[center(n["bounds"])[0]] = n["text"]

    def title_of(p):
        if not titles:
            return ""
        cx, _ = center(p["bounds"])
        k = min(titles, key=lambda k: abs(k - cx))
        return titles[k]

    # 2. 行优先排序: 先从左到右(列内 cx), 再从上到下(行 cy)
    hs = [n["bounds"]["b"] - n["bounds"]["t"] for n in pics]
    tol = max(median(hs) * 0.5, 20)
    ordered = sorted(pics, key=lambda n: (round(center(n["bounds"])[1] / tol),
                                           center(n["bounds"])[0]))

    # CLI 模式下打印排序结果
    if _is_cli_mode():
        print(f"\n=== 片源(行优先, 行容差={tol:.0f}px) 共 {len(ordered)} 条 ===")
        for i, n in enumerate(ordered, 1):
            cx, cy = center(n["bounds"])
            mark = "   <== 第%d个, 即将点击" % index if i == index else ""
            print(f"  {i:>2}. {title_of(n)}  @({cx},{cy}){mark}")

    # 3. 点击第 X 个: 海报节点 clickable=true, 但无 nid 可复用,
    #    且 click_node 的 index 是树前序非视觉序,故直接坐标 tap 中心点最稳
    target = ordered[index - 1]
    cx, cy = center(target["bounds"])
    op(2, "tap", x=cx, y=cy)

    title = title_of(target)

    if _is_cli_mode():
        print(f"\n已点击第 {index} 个片源: {title}  @({cx},{cy})")

    return {
        "ok": True,
        "data": {
            "command": "play",
            "index": index,
            "title": title,
            "x": cx,
            "y": cy,
            "total": len(ordered),
        }
    }


def _is_cli_mode():
    """判断是否为 CLI 模式（直接运行脚本）而非被 import。"""
    import inspect
    frame = inspect.currentframe()
    try:
        caller = frame.f_back
        if caller and caller.f_globals.get("__name__") == "__main__":
            return True
    finally:
        del frame
    return False


if __name__ == "__main__":
    if len(sys.argv) < 2 or not sys.argv[1].lstrip("-").isdigit():
        sys.exit("用法: python run-play.py X   (X 从 1 开始,如 python run-play.py 2)")
    x = int(sys.argv[1])
    if x < 1:
        sys.exit("X 从 1 开始")

    result = run({"index": x})
    # 额外打印 JSON 结果
    print(json.dumps(result, ensure_ascii=False, indent=2))
