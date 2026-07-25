#!/usr/bin/env bash
# type_and_search.sh — 方案A（whohuatv TV 实战验证）：
#   切 ADBKeyBoard → tap 聚焦搜索框 → 清空旧文本 → 广播输入文本 → 立即 BACK 关键盘 UI → tap 搜索按钮触发 → 恢复 IME
#
# 用法：
#   ANDROID_SERIAL=<serial> bash type_and_search.sh "<待搜索文本>" '<find_search_box 输出的 JSON>'
#   （JSON 也可通过环境变量 SEARCH_BOX_JSON 传入）
#
# 设计要点：
#   - tap 聚焦搜索框会弹出白色键盘 UI（即便已切 ADBKeyBoard，此 TV 上 ADBKeyBoard 仍弹 UI），
#     该 UI 覆盖搜索按钮 → tap/ENTER 落空、uiautomator dump 报 null root node。
#     故广播输入后必须立即 BACK(keyevent 4) 关掉键盘 UI，再 tap 搜索按钮触发。
#   - 触发搜索前不能先恢复拼音 IME，否则拼音会把已 commit 的中文重新 commit 成错字
#    （如「功夫」→「千香」）。故恢复 IME 放在 tap 搜索按钮触发之后。
#   - 输入统一用 ADBKeyBoard 的 ADB_INPUT_B64 广播（ASCII/中文均适用），避免 input text 的中文千香坑。
#     前提：设备已装 ADBKeyBoard。
#
# 退出码：
#   0  成功
#   2  参数/JSON 无效 或 未装 ADBKeyBoard
#   5  流程异常

set -uo pipefail

TEXT="${1:-}"
JSON="${2:-${SEARCH_BOX_JSON:-}}"

if [[ -z "$TEXT" ]]; then
  echo "ERROR: 缺少待搜索文本参数。用法: bash type_and_search.sh \"<文本>\" '<json>'" >&2
  exit 2
fi
if [[ -z "$JSON" ]]; then
  echo "ERROR: 缺少搜索框 JSON（来自 find_search_box.sh）。" >&2
  exit 2
fi

SERIAL="${ANDROID_SERIAL:-}"

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

"$PY" - "$TEXT" "$JSON" "$SERIAL" <<'PY'
import json, os, sys, base64, subprocess, time

text, json_str, serial = sys.argv[1], sys.argv[2], sys.argv[3]

try:
    info = json.loads(json_str)
except Exception as e:
    print("ERROR: 搜索框 JSON 无效: %s" % e, file=sys.stderr); sys.exit(2)

sb = info.get('search_box') or {}
center = sb.get('center') or {}
cx, cy = center.get('cx'), center.get('cy')
if cx is None or cy is None:
    print("ERROR: 搜索框 JSON 缺少 center 坐标。", file=sys.stderr); sys.exit(2)
clear = info.get('clear_btn') or {}
clear_center = clear.get('center') or {}
sbtn = info.get('search_btn') or {}
sbtn_center = sbtn.get('center') or {}
sx, sy = sbtn_center.get('cx'), sbtn_center.get('cy')

def adb_shell(cmdstr):
    full = ['adb']
    if serial: full += ['-s', serial]
    full += ['shell', cmdstr]
    env = dict(os.environ); env['MSYS_NO_PATHCONV']='1'
    return subprocess.run(full, capture_output=True, text=True, env=env)

def sh(cmdstr): return adb_shell(cmdstr)
def tap(x,y): sh('input tap %d %d' % (x,y)); time.sleep(0.4)
def keyevent(k): sh('input keyevent %d' % k)

# IME 工具
def list_imes():
    return [l.strip() for l in sh('ime list -s').stdout.splitlines() if l.strip()]
def current_ime():
    return sh('settings get secure default_input_method').stdout.strip()
def is_adbkeyboard(ime):
    return bool(ime) and ('adbkeyboard' in ime.lower() or 'AdbIME' in ime)
def pick_non_adbkeyboard(imes):
    for ime in imes:
        if not is_adbkeyboard(ime): return ime
    return None
def find_adbkeyboard():
    # ADBKeyBoard 可能处于 disabled 状态（ime list -s 不列），需从 ime list -a -s（含 disabled）查找
    all_imes = [l.strip() for l in sh('ime list -a -s').stdout.splitlines() if l.strip()]
    for line in all_imes:
        if 'adbkeyboard' in line.lower() or 'AdbIME' in line:
            return line
    return None

orig_ime = current_ime()
adbkb = find_adbkeyboard()

def restore_ime():
    # 恢复到非 ADBKeyBoard 的 IME：orig 本身非 ADBKeyBoard 则回 orig，否则挑一个非 ADBKeyBoard 的
    restore = orig_ime if (orig_ime and not is_adbkeyboard(orig_ime)) else pick_non_adbkeyboard(list_imes())
    if restore and restore != adbkb:
        sh('ime set %s' % restore)
        print('# 已恢复 IME = %s' % restore, file=sys.stderr)

if not adbkb:
    print("ERROR: 未检测到 ADBKeyBoard，无法输入。请安装 ADBKeyBoard（com.android.adbkeyboard）后重试。", file=sys.stderr)
    sys.exit(2)

try:
    # 0. 切 ADBKeyBoard
    sh('ime enable %s' % adbkb)
    sh('ime set %s' % adbkb)
    print('# 已切 ADBKeyBoard', file=sys.stderr)

    # 1. tap 聚焦搜索框（会弹白色键盘 UI，不可避免）
    print('# 聚焦搜索框 tap(%d,%d)' % (cx,cy), file=sys.stderr)
    tap(cx,cy)

    # 2. 清空旧文本（仅当框内有真实输入）。统一用 MOVE_END + DEL，不依赖清空按钮 tap
    #    （键盘 UI 弹出后清空按钮 tap 易落空；DEL 在 EditText 聚焦时可靠）
    cur_text = sb.get('text') or ''
    if cur_text:
        n = len(cur_text) + 5
        print('# 清空旧文本(%d 字)：MOVE_END + %d DEL' % (len(cur_text), n), file=sys.stderr)
        keyevent(123)  # MOVE_END
        for _ in range(n): keyevent(67)  # DEL
    else:
        print('# 搜索框为空，跳过清空', file=sys.stderr)

    # 3. 广播输入文本（ADB_INPUT_B64，ASCII/中文通用，规避 input text 的中文千香坑）
    b64 = base64.b64encode(text.encode('utf-8')).decode('ascii')
    sh('am broadcast -a ADB_INPUT_B64 --es msg %s' % b64)
    time.sleep(0.6)
    print('# 已广播输入 %r' % text, file=sys.stderr)

    # 4. 立即 BACK 关掉弹出的白色键盘 UI（否则覆盖搜索按钮，tap 落空）
    keyevent(4)
    time.sleep(0.6)
    print('# BACK 关闭键盘 UI', file=sys.stderr)

    # 5. 触发搜索：tap 搜索按钮（有坐标）或 ENTER 兜底
    if sx is not None and sy is not None:
        print('# 触发搜索：tap 搜索按钮(%d,%d)' % (sx,sy), file=sys.stderr)
        tap(sx,sy)
    else:
        print('# 无搜索按钮坐标，触发搜索：ENTER（部分 TV 不响应，建议 find_search_box 识别搜索按钮）', file=sys.stderr)
        keyevent(66)  # ENTER
    time.sleep(2.5)
finally:
    # 6. 恢复原 IME（必须放在触发之后，避免拼音把中文重 commit 成错字）
    restore_ime()

print('# 完成', file=sys.stderr)
PY
