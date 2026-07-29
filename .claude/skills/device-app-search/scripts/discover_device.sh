#!/usr/bin/env bash
# discover_device.sh — 步骤1：发现并选择已连接的 Android 设备
#
# 用法：
#   bash discover_device.sh            # 单设备直接用；多设备列出编号并退出（退出码 3，请带序号重跑）
#   bash discover_device.sh 2          # 选第 2 台
#
# 输出（stdout）：
#   第一行形如  ANDROID_SERIAL=<serial>   ← 供调用者 eval
#   随后以 # 开头的设备信息行（SDK / 默认输入法 / 前台包名），供步骤 3 选输入路径
#
# 调用示例：
#   eval "$(bash discover_device.sh 2)"
#
# 退出码：
#   0  成功，ANDROID_SERIAL 已打印
#   1  无可用设备
#   3  多设备但未指定序号
#   4  序号越界

set -uo pipefail

PICK="${1:-}"

# 读取所有 state=device 的设备 serial
mapfile -t DEVS < <(adb devices -l 2>/dev/null | awk 'NR>1 && $2=="device"{print $1}')

if [[ ${#DEVS[@]} -eq 0 ]]; then
  echo "ERROR: 没有可用设备。请检查 USB 连接或执行 adb connect <ip:port>，再运行 adb devices -l 确认。" >&2
  echo "  （设备处于 offline / unauthorized 状态也不计入，需先在设备上授权 USB 调试）" >&2
  exit 1
fi

if [[ ${#DEVS[@]} -eq 1 ]]; then
  SERIAL="${DEVS[0]}"
else
  if [[ -z "$PICK" ]]; then
    echo "检测到多台设备，请选择序号后重跑：" >&2
    idx=1
    for d in "${DEVS[@]}"; do
      # 顺带取 model 便于辨认
      model=$(adb devices -l 2>/dev/null | awk -v s="$d" '$1==s{for(i=3;i<=NF;i++) if($i ~ /^model:/){gsub("model:","",$i);print $i}}')
      echo "  $idx) $d  ${model:-}" >&2
      idx=$((idx+1))
    done
    echo "用法: bash discover_device.sh <序号>" >&2
    exit 3
  fi
  if ! [[ "$PICK" =~ ^[0-9]+$ ]] || [[ "$PICK" -lt 1 ]] || [[ "$PICK" -gt ${#DEVS[@]} ]]; then
    echo "ERROR: 序号越界。共 ${#DEVS[@]} 台设备，请传 1~${#DEVS[@]}。" >&2
    exit 4
  fi
  SERIAL="${DEVS[$((PICK-1))]}"
fi

# 打印 serial（供 eval）
echo "ANDROID_SERIAL=$SERIAL"

# 设备信息（注释行，供步骤3选输入路径参考）
SDK=$(adb -s "$SERIAL" shell getprop ro.build.version.sdk 2>/dev/null | tr -d '\r')
IME=$(adb -s "$SERIAL" shell settings get secure default_input_method 2>/dev/null | tr -d '\r')
PKG=$(adb -s "$SERIAL" shell dumpsys window 2>/dev/null | grep -m1 -E 'mCurrentFocus' | sed -E 's/.*u0 ([^ ]+)\/.*/\1/' | tr -d '\r')
echo "# SDK=$SDK  默认输入法=$IME  前台包名=${PKG:-unknown}"
echo "# 中文输入建议：SDK<29 或 IME 非 adbkeyboard → 优先 deeplink(路径A)，其次 ADBKeyBoard(路径C)，最后剪贴板(路径D)"

# 导出（子进程内），方便本脚本被 source 时直接用
export ANDROID_SERIAL="$SERIAL"
