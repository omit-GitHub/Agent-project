#!/usr/bin/env bash
# restore_keyboard.sh — 把设备默认输入法从 ADBKeyBoard 切回常规输入法
#
# 背景：type_and_search.sh 路径 C 会临时切到 ADBKeyBoard 注入中文，正常流程结束后会切回。
# 但若中途失败 / 用户手动打断，IME 可能停在 ADBKeyBoard，导致之后点搜索框只显示 ADBKeyBoard
# 而不弹原生键盘。本脚本独立恢复，无需执行搜索。
#
# 用法：
#   ANDROID_SERIAL=<serial> bash restore_keyboard.sh
#   ANDROID_SERIAL=<serial> bash restore_keyboard.sh <ime>   # 指定要切回的 IME（ime list -s 里的某一行）
#
# 行为：
#   - 列出设备所有 IME（ime list -s）
#   - 若当前默认已是 ADBKeyBoard：切回第一个非 ADBKeyBoard 的 IME（或用户指定的那个）
#   - 若当前默认不是 ADBKeyBoard：什么都不做，仅打印当前 IME

set -uo pipefail

SERIAL="${ANDROID_SERIAL:-}"
ADB=(adb); [[ -n "$SERIAL" ]] && ADB+=( -s "$SERIAL" )

CUR=$("${ADB[@]}" shell settings get secure default_input_method 2>/dev/null | tr -d '\r')
echo "# 当前默认输入法: ${CUR:-<空>}"

is_adbkb() {
  local x="$1"
  [[ -z "$x" ]] && return 1
  [[ "$x" == *"adbkeyboard"* || "$x" == *"AdbIME"* ]]
}

if ! is_adbkb "$CUR"; then
  echo "# 当前不是 ADBKeyBoard，无需恢复。"
  exit 0
fi

mapfile -t IMES < <("${ADB[@]}" shell ime list -s 2>/dev/null | tr -d '\r' | grep -v '^$')
echo "# 可用输入法："
idx=1
declare -a PICKS=()
for ime in "${IMES[@]}"; do
  flag=""
  if is_adbkb "$ime"; then flag="  (ADBKeyBoard)"; else PICKS+=("$ime"); fi
  echo "  $idx) $ime$flag"
  idx=$((idx+1))
done

TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
  if [[ ${#PICKS[@]} -eq 0 ]]; then
    echo "ERROR: 设备上除了 ADBKeyBoard 没有其它输入法。请安装一个常规输入法（如搜狗/百度/系统输入法）后重试。" >&2
    exit 1
  fi
  TARGET="${PICKS[0]}"
fi

echo "# 切回: $TARGET"
"${ADB[@]}" shell ime enable "$TARGET" >/dev/null 2>&1 || true
"${ADB[@]}" shell ime set "$TARGET" >/dev/null 2>&1
echo "# 完成。点任意输入框验证键盘是否恢复。"
