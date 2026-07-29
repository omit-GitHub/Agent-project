#!/usr/bin/env bash
# verify_result.sh — 步骤4：dump 搜索结果界面，确认搜索已执行
#
# 用法：
#   ANDROID_SERIAL=<serial> bash verify_result.sh "<待搜索文本>" '[可选]<find_search_box JSON>'
#
# 输出：列出结果界面里所有非空 text 节点（供人工确认是否出现目标文本/相关结果）。
#       若结果区出现目标文本或候选项，打印 # MATCH: <文本片段>。

set -uo pipefail

TEXT="${1:-}"
JSON="${2:-${SEARCH_BOX_JSON:-}}"

SERIAL="${ANDROID_SERIAL:-}"
ADB=(adb); [[ -n "$SERIAL" ]] && ADB+=( -s "$SERIAL" )

DUMP_DEVICE="//sdcard/_das_r.xml"
DUMP_LOCAL="$(mktemp).xml"
# adb.exe / python.exe 是 Windows 原生程序，不认 MSYS 虚拟路径 /tmp/...，需转成 Windows 路径
if command -v cygpath >/dev/null 2>&1; then
  DUMP_LOCAL="$(cygpath -w "$DUMP_LOCAL")"
fi

# 等界面稳定
sleep 1

if ! MSYS_NO_PATHCONV=1 "${ADB[@]}" shell uiautomator dump "$DUMP_DEVICE" >/dev/null 2>&1; then
  echo "ERROR: 结果界面 dump 失败。" >&2
  exit 2
fi
MSYS_NO_PATHCONV=1 "${ADB[@]}" pull "$DUMP_DEVICE" "$DUMP_LOCAL" >/dev/null 2>&1
"${ADB[@]}" shell rm -f /sdcard/_das_r.xml >/dev/null 2>&1 || true

# 选择 python 解释器（Windows Store 的 python3 占位符会执行失败，需探测）
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

"$PY" - "$DUMP_LOCAL" "$TEXT" "$JSON" <<'PY'
import re, sys, json
xml_path, text, json_str = sys.argv[1], sys.argv[2], sys.argv[3]
xml = open(xml_path, encoding='utf-8').read()

# 结果容器 id（来自 find_search_box）
rc = ""
try:
    info = json.loads(json_str)
    rc = (info.get('result_container') or "")
except Exception: pass

# 抓所有非空 text
texts = []
for node in re.findall(r'<node\b[^>]*>', xml):
    m = re.search(r'text="([^"]*)"', node)
    if m and m.group(1).strip():
        texts.append(m.group(1))

print('# 结果界面非空文本节点（共 %d 个）：' % len(texts))
for t in texts[:40]:
    mark = '  <== MATCH' if (text and text in t) else ''
    print('  - %s%s' % (t, mark))

if text:
    matches = [t for t in texts if text in t]
    if matches:
        print('# MATCH: 结果区出现目标文本「%s」' % text)
    else:
        print('# 未直接命中目标文本，但可能已展示搜索结果列表（见上方节点）—— 人工确认即可。')
PY

rm -f "$DUMP_LOCAL" 2>/dev/null || true
