# Windows Git Bash 陷阱（references/windows-gotchas.md）

本 skill 的脚本在 Windows Git Bash 下运行 `adb shell` 时，需注意路径被改写的问题。

## 1. MSYS 路径转换（最常踩的坑）

Git Bash（MSYS2）会把命令行里以 `/` 开头的参数当作 Unix 路径，自动改写成 Windows 路径：

```
adb shell uiautomator dump /sdcard/ui.xml
# 实际执行：adb shell uiautomator dump C:/Program Files/Git/sdcard/ui.xml  ← 设备上找不到
```

### 解决：`MSYS_NO_PATHCONV=1` + 双斜杠 `//sdcard/...`

所有含 `/` 开头路径的 `adb shell` 命令都要：
- 加环境变量前缀 `MSYS_NO_PATHCONV=1`
- 路径写成 `//sdcard/...`（双斜杠，确保不被改写且设备端解析为 `/sdcard/...`）

```bash
MSYS_NO_PATHCONV=1 adb shell uiautomator dump //sdcard/_das_ui.xml
MSYS_NO_PATHCONV=1 adb pull //sdcard/_das_ui.xml ./ui.xml
```

本 skill 的所有脚本内部已统一加 `MSYS_NO_PATHCONV=1`，调用者无需重复处理。

## 2. `adb shell` 输出带 `\r\n`

`adb shell` 在 Windows 下返回的文本行尾是 `\r\n`，直接用 bash 字符串比较 / 赋值会带 `\r`，导致匹配失败。

处理：管道接 `tr -d '\r'`。

```bash
SDK=$(adb -s "$SERIAL" shell getprop ro.build.version.sdk | tr -d '\r')
```

本 skill 脚本里取 SDK / IME / 前台包名时已加 `tr -d '\r'`。

## 3. `uiautomator dump` 需要界面稳定

dump 抓取的是当前帧。若界面正在跳转 / 加载 / 有动画，会取到中间态或旧界面。

- 触发搜索 / 跳转后 `sleep 0.5~1` 再 dump。
- 弹窗 / 加载圈未消失前不要 dump。

## 4. `input keyevent` 拼不出 Ctrl+A 等和弦

`adb shell input keyevent` 是逐次发送按键，无法模拟 Ctrl+A（同时按下）这类组合键。
因此清空搜索框旧文本不能用"全选 + 删除"，只能用 `MOVE_END`(123) 后按旧文本长度多次 `DEL`(67)。
若界面有清空按钮，优先 tap 清空按钮中心点。
