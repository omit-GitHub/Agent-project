---
name: device-app-search
description: Control a connected Android device's app UI to perform a search — discover devices via `adb devices`, locate the foreground app's search box, type the given text (Chinese/English/symbols), and trigger the search. Triggers on: search <text> on the device, search <movie/title> on the TV/box/phone, let the device search <text> via adb, 控制设备APP界面搜索, 在设备上搜索/搜一下 <文本>, adb 输入文本并搜索, 让设备搜索 <文本>.
---

# device-app-search — 通过 adb 控制设备 APP 界面完成搜索

把"待搜索文本"送到已连接的 Android 设备、在当前前台 APP 的搜索框里输入并触发搜索。
全程只用 `adb`，无需在设备端额外开发。

## 0. 入参

从用户消息抽取**待搜索文本**（中文 / 英文 / 符号均可），原样保留，不做转义预处理。
脚本统一用 ADBKeyBoard 广播注入（ASCII/中文均走此路径），需设备已装 ADBKeyBoard。

## 1. 发现设备

运行 `bash scripts/discover_device.sh`（多设备时传序号参数，如 `bash scripts/discover_device.sh 2`）。

- 无设备 → 提示用户检查 USB / `adb connect`；
- 恰好 1 台 → 直接使用；
- 多台 → 列出编号供用户选，选中后导出 `ANDROID_SERIAL` 供后续命令使用。

脚本顺带打印 `ro.build.version.sdk` 与当前默认输入法（供步骤 3 切/恢复 IME 用）。

## 2. 定位搜索框

运行 `bash scripts/find_search_box.sh`。

脚本执行 `uiautomator dump` 并解析当前界面，输出 JSON 风格结果：

```json
{
  "search_box": {"resource_id": "com.x.y:id/search_et", "text": "", "bounds": "[366,60][832,119]", "center": {"cx": 599, "cy": 89}},
  "clear_btn": {"resource_id": "...", "center": {"cx": 849, "cy": 89}},
  "search_btn": {"resource_id": "com.x.y:id/search_btn", "center": {"cx": 1015, "cy": 89}},
  "result_container": "com.x.y:id/search_result"
}
```

失败（dump 为空或无 EditText）→ 退出码 2，提示改用截图 + 视觉识别（本 skill 不覆盖）。

## 3. 输入并搜索

运行 `bash scripts/type_and_search.sh "<文本>"`，并把第 2 步得到的 JSON 结果通过环境变量或参数传入（见脚本头注释）。

脚本流程（方案 A，whohuatv TV 实战验证）：切 ADBKeyBoard → tap 聚焦搜索框 → 清空旧文本（仅当框内有真实输入）→ 广播 `ADB_INPUT_B64` 注入文本 → **立即 BACK 关掉弹出的键盘 UI** → tap 搜索按钮触发 → 恢复原 IME。

- 输入统一用 ADBKeyBoard 的 `ADB_INPUT_B64` 广播（ASCII / 中文均走此路径，规避 `input text` 对中文 Unicode 不可靠的坑）。
- ⚠️ tap 聚焦搜索框会弹出白色键盘 UI（即便切了 ADBKeyBoard，此 TV 上 ADBKeyBoard 仍弹 UI），会覆盖搜索按钮导致 tap 落空。故**广播输入后必须立即 `keyevent 4`(BACK) 关键盘，再 tap 搜索按钮触发**。
- ⚠️ 恢复原 IME 必须放在 tap 搜索按钮**之后**，否则拼音会把已 commit 的中文重新 commit 成错字（如「功夫」→「千香」）。
- ⚠️ `adb shell input text` 对中文 Unicode 不可靠（被静默丢弃或被拼音 IME 误读成无关汉字），**绝不要用 `input text` 硬塞 Unicode**。完整命令序列见 `references/input-paths.md`。

## 4. 验证（可选）

运行 `bash scripts/verify_result.sh`，dump 搜索结果界面，grep 结果区是否出现目标文本或相关候选项。

## 何时查 references

- 遇到中文 / 非 ASCII 输入问题、需要 ADBKeyBoard 细节 → `references/input-paths.md`。
- 命令在 Windows Git Bash 下行为异常（路径被改写）→ `references/windows-gotchas.md`。

## 已踩过的坑（务必留意）

- **Windows Git Bash 路径陷阱**：`adb shell` 里形如 `/sdcard/ui.xml` 会被改写成 `C:/Program Files/Git/sdcard/ui.xml`。
  所有含 `/` 开头路径的 adb 命令都要加前缀 `MSYS_NO_PATHCONV=1` 并把路径写成 `//sdcard/ui.xml`（双斜杠）。详见 `references/windows-gotchas.md`。
- **uiautomator dump 需界面稳定**：输入 / 跳转后 `sleep 0.5~1` 再 dump，否则取到的是旧界面。
- **清空旧文本**：用 `keyevent 123`(MOVE_END) 后按旧文本长度多次 `keyevent 67`(DEL)；Ctrl+A 全选无法用 `input keyevent` 拼出（分次按键不是和弦）。
- **清空判定（placeholder vs 真实输入）**：uiautomator dump **不提供 textColor**，无法按"浅色/黑色"直接判断。改用 EditText 节点 `text` 属性等价区分——`text` 为空 ⇔ 框内是浅色默认推荐文字（placeholder/hint，无需清空）；`text` 非空 ⇔ 是黑色真实输入（需清空，tap 清空按钮或按长度 DEL）。`find_search_box.sh` 已把 `text` 带进 JSON 供 `type_and_search.sh` 判定。
- **tap 聚焦会弹键盘 UI（方案 A 的核心坑）**：此 TV 上即便切了 ADBKeyBoard，tap 聚焦搜索框仍弹出白色键盘 UI，覆盖搜索按钮 → tap/ENTER 落空、`uiautomator dump` 报 `null root node`。**广播输入后必须立即 `keyevent 4`(BACK) 关键盘，再 tap 搜索按钮触发**；恢复 IME 放在触发之后，否则拼音把中文重 commit 成错字（「功夫」→「千香」）。若进程被强杀 IME 停在 ADBKeyBoard，手动恢复用 `bash scripts/restore_keyboard.sh`（可传参指定要切回的 IME，不传则选第一个非 ADBKeyBoard 的）。
