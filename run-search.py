# -*- coding: utf-8 -*-
"""搜索片源:whohuatv launcher,经 instruction-protocol 指令序列驱动。
用法: python run-search.py [关键词]   (默认 "")
前置: 设备已开 GUIAgent 无障碍服务(ws 随无障碍常驻;PC 直连设备填 GUIAGENT_WS_HOST=<设备IP> 或先 adb forward tcp:8322 tcp:8322)。"""
import json, sys, time
from send import send

KW = sys.argv[1] if len(sys.argv) > 1 else ""

def op(i, name, **args):
    r = send({"id": str(i), "op": name, "args": args})
    print(f"[{i}] {name} -> ok={r.get('ok')} {json.dumps(r.get('data', r.get('err')), ensure_ascii=False)}")
    return r

# 1. 确保 launcher 在前台
op(1, "start", pkg="com.wohuatv.launcher")
time.sleep(1.5)
# 2. 点搜索入口
op(2, "click_node", id="classsic_nav_search")
time.sleep(1.0)
# 3. 填关键词(优先 ACTION_SET_TEXT;失败降级粘贴)
r3 = op(3, "set_text", id="mid_search_text_et", text=KW)
if not r3.get("ok"):
    print("  set_text 失败,改走粘贴降级")
    op("3b", "set_text_fallback", id="mid_search_text_et", text=KW)
time.sleep(0.5)
# 4. 触发搜索
op(4, "click_node", id="mid_search_text")
time.sleep(1.8)
# 5. 读片源结果列表
r5 = op(5, "find", id="pop_mid_content_item_tv", limit=20)

if r5.get("ok"):
    nodes = r5["data"].get("nodes", [])
    print(f"\n=== 片源结果 {len(nodes)} 条 [{KW}] ===")
    for n in nodes:
        b = n.get("bounds", {})
        cx = (b.get("l", 0) + b.get("r", 0)) // 2
        cy = (b.get("t", 0) + b.get("b", 0)) // 2
        print(f"  - {n.get('text')}  @({cx},{cy})")
else:
    print("\n结果读取失败,用 dump 看当前页面")
    op(6, "dump", depth=3)
