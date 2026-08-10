# GUIAgent HTTP 复合命令 API

> HTTP Server 监听端口 **8765**，接收 JSON 复合命令，编排原子操作控制视频 APP。

---

## 零、快速对接

### 连上设备

设备和 PC 在同一局域网，通过设备 IP 直连（无需 USB/adb）：

```bash
# 查设备 IP（adb 连上后执行）
adb shell ip addr show wlan0 | grep "inet "
# 例: inet 192.168.1.100/24
```

如果只能 USB 连接，用 adb 转发端口：
```bash
adb forward tcp:8765 tcp:8765
# 之后用 127.0.0.1:8765 访问
```

### 验证连通

```bash
curl http://<设备IP>:8765/v1/health
# 返回 {"ok":true,"data":{"status":"healthy","available_commands":[...]}} 就通了
```

### ⚠️ 前提条件

1. **无障碍服务必须开启**（否则 HTTP Server 不存在）：
   ```bash
   adb shell settings put secure enabled_accessibility_services com.huawei.aifttr.digitalpersonshell/com.guiagent.executor.GuiAgentService
   adb shell settings put secure accessibility_enabled 1
   ```
2. **目标 APP 必须在前台**（如爱奇艺播放页），命令才能操作对应 UI
3. **命令串行执行**（同一时刻只处理一条），不要并发发送

### 一次完整交互

```bash
# 1. 健康检查
curl http://192.168.1.100:8765/v1/health

# 2. 在爱奇艺播放页选第 3 集
curl -X POST http://192.168.1.100:8765/v1/compound \
  -H "Content-Type: application/json" \
  -d '{"command":"aiqiyi.select_episode","params":[3]}'

# 成功响应:
# {"ok":true,"data":{"command":"aiqiyi.select_episode","result":"selected_episode_3_by_text (35 items, 5 cols)"}}

# 失败响应:
# {"ok":false,"error":{"code":"NO_MATCH","message":"Episode 3 not found"}}
```

---

## 一、HTTP 接口

### 1.1 复合命令

```
POST http://<设备IP>:8765/v1/compound
Content-Type: application/json

{
  "command": "命令名",
  "params": { ... }    // 可选，对象或数组
}
```

`params` 支持两种格式：
- **对象格式**：`{"speed": "1.5"}` → 直接传给命令
- **数组格式**：`[3]` 或 `[2, 3]` → 自动包装为 `{"values": [3]}`

### 1.2 健康检查

```
GET http://<设备IP>:8765/v1/health
```

返回 `{"ok": true, "data": {"status": "healthy", "version": "0.1.0", "available_commands": [...]}}`

### 1.3 响应格式

**成功：**
```json
{"ok": true, "data": {"command": "命令名", "result": "执行结果描述", "state": {"pkg": "前台包名", "summary": ["页面文本"]}}}
```

**失败：**
```json
{"ok": false, "error": {"code": "错误码", "message": "错误描述"}, "state": {"pkg": "前台包名", "summary": ["页面文本"]}}
```

> `state` 为命令执行后的前台状态（App 包名 + 页面文本摘要，成功时等待页面稳定后采集、上限 5s，失败时立即采集）。响应已自带状态字段的命令（如 `get_state`）不重复附加。

---

## 二、爱奇艺命令清单

### 2.1 播放控制

| 命令 | params | 说明 |
|------|--------|------|
| `aiqiyi.toggle_play` | 无 | 播放/暂停切换 |
| `aiqiyi.toggle_control_bar` | 无 | 打开/关闭控制条 |
| `aiqiyi.next_episode` | 无 | 下一集 |
| `aiqiyi.prev_episode` | 无 | 上一集（⚠️ 部分设备不支持） |

### 2.2 选集

| 命令 | params | 说明 |
|------|--------|------|
| `aiqiyi.open_episode_panel` | 无 | 打开选集面板 |
| `aiqiyi.close_episode_panel` | 无 | 关闭选集面板 |
| `aiqiyi.scroll_episode_up` | `{"count": N}` | 选集面板向上翻页，默认 1 |
| `aiqiyi.scroll_episode_down` | `{"count": N}` | 选集面板向下翻页，默认 1 |
| `aiqiyi.select_episode` | `[N]` 或 `[R, C]` | 选集，详见下方说明 |

**`select_episode` 参数说明：**
- `[N]` — 选第 N 个（自动按文本匹配或位置选择）
- `[R, C]` — 选第 R 行第 C 列（仅多列网格布局有效）
- 示例：`{"command": "aiqiyi.select_episode", "params": [3]}` 或 `"params": [2, 3]`

### 2.3 倍速/清晰度

| 命令 | params | 说明 |
|------|--------|------|
| `aiqiyi.set_speed` | `{"speed": "倍速值"}` | 设置倍速 |
| `aiqiyi.set_quality` | `{"quality": "清晰度"}` | 设置清晰度 |

**`set_speed` 可选值：** `"0.75"`, `"1.0"`, `"1.25"`, `"1.5"`, `"2.0"`

**`set_quality` 可选值：** `"480P"`, `"720P"`, `"1080P"`（不区分大小写）

### 2.4 亮度

| 命令 | params | 说明 |
|------|--------|------|
| `aiqiyi.brightness_up` | `{"count": N}` | 亮度+，默认 1 |
| `aiqiyi.brightness_down` | `{"count": N}` | 亮度-，默认 1 |

### 2.5 详情页

| 命令 | params | 说明 |
|------|--------|------|
| `aiqiyi.open_detail` | 无 | 进入详情页（简介页） |
| `aiqiyi.close_detail` | 无 | 退出详情页 |

---

## 三、通用命令

| 命令 | params | 说明 |
|------|--------|------|
| `go_back` | 无 | 返回 |
| `go_home` | 无 | 主页 |
| `get_state` | 无 | 查询前台状态：当前 App 包名 + 页面文本摘要 |
| `volume_up` | 无 | 音量+ |
| `volume_down` | 无 | 音量- |
| `volume_mute` | 无 | 静音 |
| `launcher_search` | `{"keyword": "关键词"}` | 聚合平台搜索片源（爱奇艺/优酷/腾讯/芒果，~4s，返回结果列表及坐标） |
| `play` | `{"index": N}` | 播放搜索结果第 N 个（从 1 开始） |

---

## 四、错误码

| 错误码 | 说明 |
|--------|------|
| `UNKNOWN_COMMAND` | 未知的命令名 |
| `BAD_PARAMS` | 参数错误（缺参数、格式错、值越界） |
| `BAD_JSON` | JSON 解析失败 |
| `EXECUTION_FAILED` | 执行失败 |
| `TIMEOUT` | 命令执行超时（默认 15 秒） |
| `NO_MATCH` | 未找到目标 UI 元素 |
| `DPAD_UNAVAILABLE` | 遥控器服务不可用 |
| `DPAD_TIMEOUT` | 遥控器服务超时 |

---

## 五、调用示例

```json
// 播放/暂停
{"command": "aiqiyi.toggle_play", "params": {}}

// 选第 3 集
{"command": "aiqiyi.select_episode", "params": [3]}

// 查询当前前台状态（在哪个 App、页面上有什么）
{"command": "get_state", "params": {}}

// 选第 2 行第 3 列
{"command": "aiqiyi.select_episode", "params": [2, 3]}

// 倍速 1.5x
{"command": "aiqiyi.set_speed", "params": {"speed": "1.5"}}

// 清晰度 720P
{"command": "aiqiyi.set_quality", "params": {"quality": "720P"}}

// 搜索片源
{"command": "launcher_search", "params": {"keyword": "庆余年"}}

// 播放搜索结果第 1 个
{"command": "play", "params": {"index": 1}}

// 播放第 2 排第 3 个搜索结果
{"command": "play", "params": {"row": 2, "col": 3}}
```

---

## 六、使用注意

### 命令执行超时

默认 **15 秒**。`launcher_search` 命令通常需要 3-5 秒（涉及启动 launcher + 输入 + 等待结果），其他命令 1-3 秒。

### 推荐调用顺序

```
launcher_search → play → 播放控制（toggle_play / set_speed / ...）→ 选集（select_episode）
```

- `launcher_search` 返回 `query/search_status/count/items`；仅按 `search_status` 判断搜索是否有结果
- `play` 支持 `{"index":N}` 和 `{"row":R,"col":C}` 两种选择方式
- 播放器打开后再发播放控制命令
- `select_episode` 会自动打开选集面板（如果没打开的话）

### 状态依赖

命令假设 APP 已在正确的前台页面：
- `aiqiyi.*` → 需要爱奇艺播放页在前台
- `tencent.*` → 需要腾讯视频播放页在前台
- `launcher_search` → 任意页面可直接调用（内部自动先回 launcher 主页）
- `play` → 需要 `launcher_search` 之后的搜索结果页在前台

如果 APP 不在前台，命令可能返回 `NO_MATCH` 或 `EXECUTION_FAILED`。

### 并发限制

**串行执行**——同一时刻只处理一条命令。如果前一条还在执行，后一条会排队。超过 15 秒返回 `TIMEOUT`。

---

## 七、启用无障碍服务

```bash
adb shell settings put secure enabled_accessibility_services com.huawei.aifttr.digitalpersonshell/com.guiagent.executor.GuiAgentService
adb shell settings put secure accessibility_enabled 1
```

---

**文档版本**：v3.0
**更新日期**：2026-08-03
