#!/usr/bin/env bash
# find_search_box.sh — 步骤2：dump 当前界面并定位搜索框
#
# 用法：
#   ANDROID_SERIAL=<serial> bash find_search_box.sh
#   （未设置 ANDROID_SERIAL 时默认走唯一/首选设备）
#
# 输出（stdout）：一行 JSON，形如
#   {"search_box":{"resource_id":"...","bounds":"[366,60][832,119]","center":{"cx":599,"cy":89}},"clear_btn":{"resource_id":"...","center":{"cx":849,"cy":89}},"search_btn":{"resource_id":"...","center":{"cx":1015,"cy":89}},"result_container":"..."}
# 失败时退出码 2 并在 stderr 给出原因。
#
# Windows Git Bash：dump/pull 路径用 //sdcard/... 前缀 + MSYS_NO_PATHCONV=1，详见 references/windows-gotchas.md

set -uo pipefail

SERIAL="${ANDROID_SERIAL:-}"
ADB=(adb); [[ -n "$SERIAL" ]] && ADB+=( -s "$SERIAL" )

DUMP_DEVICE="//sdcard/_das_ui.xml"
DUMP_LOCAL="$(mktemp).xml"
# adb.exe / python.exe 是 Windows 原生程序，不认 MSYS 虚拟路径 /tmp/...，需转成 Windows 路径
if command -v cygpath >/dev/null 2>&1; then
  DUMP_LOCAL="$(cygpath -w "$DUMP_LOCAL")"
fi

# 1. dump 当前界面（界面需稳定，调用者应确保无动画/加载中）
if ! MSYS_NO_PATHCONV=1 "${ADB[@]}" shell uiautomator dump "$DUMP_DEVICE" >/dev/null 2>&1; then
  echo "ERROR: uiautomator dump 失败。请确认界面已稳定（无加载动画/弹窗），重试。" >&2
  exit 2
fi

# 2. pull 到本地
if ! MSYS_NO_PATHCONV=1 "${ADB[@]}" pull "$DUMP_DEVICE" "$DUMP_LOCAL" >/dev/null 2>&1; then
  echo "ERROR: pull ui.xml 失败。" >&2
  exit 2
fi
"${ADB[@]}" shell rm -f /sdcard/_das_ui.xml >/dev/null 2>&1 || true

# 3. 选择 python 解释器（Windows Store 的 python3 占位符会执行失败，需探测）
PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c '1' >/dev/null 2>&1; then PY="$c"; break; fi
done
if [[ -z "$PY" ]]; then
  echo "ERROR: 未找到可用的 python 解释器（python3/python/py），请安装 Python 后重试。" >&2
  exit 2
fi
# Windows 中文 locale 下 python 从 stdin 读源码/输出默认 gbk 会乱码，强制 UTF-8
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8

"$PY" - "$DUMP_LOCAL" <<'PY'
import json, re, sys

ui_path = sys.argv[1]

try:
    xml = open(ui_path, encoding='utf-8').read()
except Exception as e:
    print("ERROR: 读取 ui.xml 失败: %s" % e, file=sys.stderr); sys.exit(2)

# 抓所有 <node ...> 开始标签
nodes = re.findall(r'<node\b[^>]*>', xml)

def attr(tag, name):
    mm = re.search(name + r'="([^"]*)"', tag)
    return mm.group(1) if mm else ""

def bounds_xy(b):
    # [x1,y1][x2,y2]
    nums = re.findall(r'\[(\d+),(\d+)\]', b)
    if len(nums) >= 2:
        x1, y1 = int(nums[0][0]), int(nums[0][1])
        x2, y2 = int(nums[1][0]), int(nums[1][1])
        return x1, y1, x2, y2
    return None

candidates = []  # (score, dict)
for t in nodes:
    cls = attr(t,'class'); rid = attr(t,'resource-id'); txt = attr(t,'text')
    desc = attr(t,'content-desc'); b = attr(t,'bounds')
    if not b: continue
    bb = bounds_xy(b)
    if not bb: continue
    x1,y1,x2,y2 = bb
    area = max(0,(x2-x1))*max(0,(y2-y1))
    cx, cy = (x1+x2)//2, (y1+y2)//2
    is_edit = 'EditText' in cls
    kw = any(k in (rid+' '+txt+' '+desc).lower() for k in ('search','搜索','query','输入','keyword','find'))
    if not (is_edit or kw):
        continue
    # 评分：可编辑 +50；关键词 +20；面积大加分
    score = (50 if is_edit else 0) + (20 if kw else 0) + min(area//1000, 30)
    candidates.append((score, {'resource_id':rid,'text':txt,'class':cls,'bounds':b,
                              'center':{'cx':cx,'cy':cy},'area':area,'is_edit':is_edit,'kw':kw}))

if not candidates:
    print("ERROR: 当前界面未找到搜索框（无 EditText 且无 search/搜索 字样节点）。"
          "可能是搜索框在二级页面——先 tap 搜索入口再重试；或改用截图+视觉识别。", file=sys.stderr)
    sys.exit(2)

candidates.sort(key=lambda c: c[0], reverse=True)
sb = candidates[0][1]

# 找清空按钮：遍历所有节点（清空按钮通常不是 EditText、不含 search 关键词，不在 candidates 里）
clear = None
for t in nodes:
    rid = attr(t,'resource-id'); desc = attr(t,'content-desc'); txt = attr(t,'text'); b = attr(t,'bounds')
    if not b: continue
    if any(k in (rid+' '+desc+' '+txt).lower() for k in ('clear','清除','_del','delete','清空')):
        bb = bounds_xy(b)
        if bb:
            x1,y1,x2,y2 = bb
            clear = {'resource_id':rid,'center':{'cx':(x1+x2)//2,'cy':(y1+y2)//2}}; break

# 找搜索按钮：clickable + text/content-desc 含"搜索"/"search" + 非 EditText + 非搜索框本身
sbtn = None
for t in nodes:
    cls = attr(t,'class'); rid = attr(t,'resource-id'); txt = attr(t,'text')
    desc = attr(t,'content-desc'); b = attr(t,'bounds'); clk = attr(t,'clickable')
    if not b or clk != 'true': continue
    if 'EditText' in cls or rid == sb['resource_id']: continue
    if '搜索' in (txt+desc) or 'search' in (txt+desc).lower():
        bb = bounds_xy(b)
        if bb:
            x1,y1,x2,y2 = bb
            sbtn = {'resource_id':rid,'center':{'cx':(x1+x2)//2,'cy':(y1+y2)//2}}; break

# 找结果容器：id 含 result/list，非可编辑
rc = ""
for t in nodes:
    rid = attr(t,'resource-id')
    if rid and any(k in rid.lower() for k in ('search_result','result','list')) and 'EditText' not in attr(t,'class'):
        rc = rid; break

print(json.dumps({
    'search_box': {'resource_id':sb['resource_id'],'text':sb['text'],'bounds':sb['bounds'],
                   'center':sb['center']},
    'clear_btn': clear, 'search_btn': sbtn, 'result_container': rc
}, ensure_ascii=False))
PY

rm -f "$DUMP_LOCAL" 2>/dev/null || true
