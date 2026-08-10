# -*- coding: utf-8 -*-
"""搜索片源:whohuatv launcher,经 instruction-protocol 指令序列驱动。

用法:
    CLI:  python run-search.py [关键词]   (默认 "")
    API:  from run_search import run; run({"keyword": "xxx"})

前置: 设备已开 GUIAgent 无障碍服务(ws 随无障碍常驻;PC 直连设备填 GUIAGENT_WS_HOST=<设备IP> 或先 adb forward tcp:8322 tcp:8322)。
"""
import json
import sys
import time

from send import send


def op(i, name, **args):
    r = send({"id": str(i), "op": name, "args": args})
    print(f"[{i}] {name} -> ok={r.get('ok')} {json.dumps(r.get('data', r.get('err')), ensure_ascii=False)}")
    return r


def run(params=None):
    """搜索片源（封装为可调用的 API）。

    Args:
        params: 可选 dict，支持 {"keyword": "xxx"}。
                若不提供 keyword，默认为空字符串。

    Returns:
        dict: {"ok": true/false, "data": {...}} 或 {"ok": false, "error": {...}}
              data 包含 items 列表（搜索到的片源）。
    """
    if params is None:
        params = {}

    keyword = params.get("keyword", "")
    if not isinstance(keyword, str):
        keyword = str(keyword)
    keyword = keyword.strip()

    # 1. 确保 launcher 在前台
    op(1, "start", pkg="com.wohuatv.launcher")
    time.sleep(1.5)

    # 2. 点搜索入口
    r2 = op(2, "click_node", id="classsic_nav_search")
    if not r2.get("ok"):
        return {"ok": False, "error": {"code": "NO_MATCH", "message": "Search entry not found"}}
    time.sleep(1.0)

    # 3. 填关键词(优先 ACTION_SET_TEXT;失败降级粘贴)
    r3 = op(3, "set_text", id="mid_search_text_et", text=keyword)
    if not r3.get("ok"):
        print("  set_text 失败,改走粘贴降级")
        op("3b", "set_text_fallback", id="mid_search_text_et", text=keyword)
    time.sleep(0.5)

    # 4. 触发搜索
    r4 = op(4, "click_node", id="mid_search_text")
    if not r4.get("ok"):
        return {"ok": False, "error": {"code": "NO_MATCH", "message": "Search trigger not found"}}
    time.sleep(1.8)

    # 5. 读片源结果列表
    r5 = op(5, "find", id="pop_mid_content_item_tv", limit=20)

    items = []
    if r5.get("ok"):
        nodes = r5["data"].get("nodes", [])
        for n in nodes:
            b = n.get("bounds", {})
            cx = (b.get("l", 0) + b.get("r", 0)) // 2
            cy = (b.get("t", 0) + b.get("b", 0)) // 2
            items.append({
                "index": len(items) + 1,
                "text": n.get("text", ""),
                "x": cx,
                "y": cy,
            })

    result = {
        "ok": True,
        "data": {
            "command": "launcher_search",
            "query": keyword,
            "count": len(items),
            "items": items,
        },
    }

    # CLI 模式下打印结果
    if _is_cli_mode():
        if items:
            print(f"\n=== 片源结果 {len(items)} 条 [{keyword}] ===")
            for item in items:
                print(f"  - {item['text']}  @({item['x']},{item['y']})")
        else:
            print("\n结果读取失败,用 dump 看当前页面")
            op(6, "dump", depth=3)

    return result


def _is_cli_mode():
    """判断是否为 CLI 模式（直接运行脚本）而非被 import。"""
    import inspect
    frame = inspect.currentframe()
    try:
        caller = frame.f_back
        # 如果调用者模块名是 __main__ 或当前文件就是 __main__
        if caller and caller.f_globals.get("__name__") == "__main__":
            return True
    finally:
        del frame
    return False


if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else ""
    result = run({"keyword": kw})
    # CLI 模式下额外打印 JSON 结果
    if not _is_cli_mode() or True:
        print(json.dumps(result, ensure_ascii=False, indent=2))
