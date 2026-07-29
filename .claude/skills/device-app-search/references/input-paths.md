# 输入与触发路径（references/input-paths.md）

`type_and_search.sh` 现在只走**一条路径（方案 A）**：ADBKeyBoard 广播 `ADB_INPUT_B64` 输入 + BACK 关键盘 + tap 搜索按钮触发。不再区分 ASCII/中文，不再用 `adb shell input text`。

> 核心结论：`adb shell input text` 对中文 Unicode 不可靠——可能被静默丢弃，也可能被活动的拼音 IME
> 把字节误读成无关汉字（实测「功夫」→「千香」）。故**统一用 ADBKeyBoard 的 ADB_INPUT_B64 广播注入**，
> ASCII/中文均适用，绕开 `input text` 的坑。

## 前提：设备已装 ADBKeyBoard

```bash
adb shell ime list -s | grep -iE 'adbkeyboard|AdbIME'   # 形如 com.android.adbkeyboard/.AdbIME
```

未装 → 脚本退出码 2，提示安装 [ADBKeyBoard](https://github.com/senzhk/ADBKeyBoard)（com.android.adbkeyboard）。

## 方案 A 完整命令序列

```bash
# 0. 记录原输入法，切 ADBKeyBoard
ORIG_IME=$(adb shell settings get secure default_input_method)
adb shell ime enable com.android.adbkeyboard/.AdbIME
adb shell ime set   com.android.adbkeyboard/.AdbIME
# 1. tap 聚焦搜索框（此 TV 上会弹白色键盘 UI，不可避免）
adb shell input tap <cx> <cy>
# 2. 清空旧文本（仅当框内有真实输入）：tap 清空按钮 或 MOVE_END(123)+多次 DEL(67)
# 3. 用 base64 传文本，规避转义与编码问题
adb shell am broadcast -a ADB_INPUT_B64 --es msg "$(printf '%s' '<文本>' | base64)"
# 4. 立即 BACK 关掉弹出的白色键盘 UI（否则会覆盖搜索按钮，tap 落空）
adb shell input keyevent 4
# 5. tap 搜索按钮触发（坐标来自 find_search_box 的 search_btn；无坐标则 ENTER 兜底）
adb shell input tap <sx> <sy>
# 6. 恢复原 IME（必须在 tap 搜索按钮之后，否则拼音会把中文重 commit 成错字）
adb shell ime set <ORIG_IME>
```

## 关键判定与坑

- **am broadcast 返回码恒为 0、输出恒含 `result=0`**，无法据此判定是否被接收。脚本不再做输入后的 dump 验证（精简），改由 `verify_result.sh` 在结果页验证。
- **白色键盘 UI 覆盖坑**：tap 聚焦搜索框会弹白色键盘 UI（即便切了 ADBKeyBoard，此 TV 上 ADBKeyBoard 也弹 UI）。该 UI 覆盖搜索按钮区域 → tap「搜索」按钮落空、ENTER/KEYCODE_SEARCH 不响应、`uiautomator dump` 报 `null root node returned by UiTestAutomationBridge`。**必须广播输入后立即 BACK(4) 关键盘再 tap 搜索按钮**。
- **千香坑**：触发搜索前若先恢复拼音 IME，拼音会把已 commit 的中文重新 commit 成错字（「功夫」→「千香」）。**恢复 IME 必须放在 tap 搜索按钮触发之后**。
- **ENTER 不响应**：此 TV 搜索页不响应 ENTER(66)，必须 tap 搜索按钮。故 `find_search_box.sh` 会识别搜索按钮（clickable + text/content-desc 含「搜索」/「search」 + 非 EditText + 非搜索框本身）并输出 `search_btn.center`。
