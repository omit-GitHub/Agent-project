# GUIAgent 指令格式规约 v1.2

> 本规约只定义指令的**格式与语义**。指令的接收(传输载体)与执行(调用无障碍 API)由设备侧宿主进程实现,不在本文件范围内。
> 宿主进程寄生在某个 APP 中并注册 AccessibilityService;指令格式与宿主无关,可被任意进程构造。

## 1. 传输载体(仅示例,不影响格式)

- 宿主 APP 在设备内监听一个 **WebSocket 服务**:`0.0.0.0:8322`,路径 `/guiagent`。
- 内网任意可信机器经 `ws://<设备IP>:8322/guiagent` 连接,无需 adb forward、无需是设备本机进程。请求=一个 ws 文本帧(一行 NDJSON),响应=一个文本帧,经 `LineHandler` 转 `Protocol.handle`。
- ws 仅作网络隧道,不参与语义;换传输层只换隧道,指令字节不变。

## 2. 帧格式

- **NDJSON**:一行 UTF-8 JSON = 一条指令,以 `\n` 结尾。
- **一问一答**:每条请求恰好对应一行响应。
- 大返回(如 `dump`)也压成一行,内部结构化承载。
- v1 不做异步事件流。

## 3. 请求 / 响应统一结构

请求:
```json
{"id":"<必填,客户端生成,建议单调递增>","op":"<枚举>","args":{...}}
```
响应:
```json
{"id":"<原样回显>","ok":true,"data":{...}}
{"id":"<原样回显>","ok":false,"err":{"code":"<枚举>","msg":"..."}}
```
- `id` 强制存在并原样回显,用于配对。
- `ok` 为布尔,二值,无三态。

## 4. op 枚举与参数

### 4.1 控制与读屏

| op | args | data | 说明 |
|---|---|---|---|
| `ping` | `{}` | `{pong:true,pkg,screen:{w,h,sdk}}` | 健康检查 |
| `dump` | `{depth?:int, include?:[field...]}` | `{pkg,window:{...,nodes:[树]}}` | 当前 active window UI 树;遍历顺序=树前序 |
| `find` | `{text?:子串, id?:res-id, desc?:子串, cls?:类名, limit?:int}` | `{nodes:[{nid,id,text,bounds,clickable,scrollable,...}]}` | 按条件查节点 |

`dump` / `find` 的 `include` 可选字段:`bounds,text,id,cls,desc,clickable,scrollable,enabled`。

### 4.2 节点级操作(优先于坐标级,更稳)

| op | args | 执行 |
|---|---|---|
| `click_node` | `{<find 条件>, index?:int 默认0}` | ACTION_CLICK |
| `long_click_node` | `{<find 条件>, index?:int 默认0}` | ACTION_LONG_CLICK |
| `set_text` | `{<find 条件>, text:string}` | ACTION_SET_TEXT(绕输入法,中文直塞) |
| `scroll_node` | `{<find 条件>, dir:"up"\|"down"\|"left"\|"right"}` | ACTION_SCROLL_* |
| `set_text_fallback` | `{<find 条件>, text:string}` | ACTION_SET_TEXT 降级备选(见 §4.2.1) |

`<find 条件>` = `find` 的子集 `{text?,id?,desc?,cls?,nid?}`。`nid` 见 §5。

### 4.2.1 `set_text_fallback` 语义

`set_text` 的降级备选,用于目标控件拒收 `ACTION_SET_TEXT`(自定义非 `EditText` 输入框、部分富文本控件)。执行链固定为:
1. 对匹配节点 `ACTION_FOCUS`(若不可聚焦则 `ACTION_CLICK` 聚焦);
2. 将 `text` 写入系统剪贴板;
3. 对该节点 `performAction(ACTION_PASTE)`。

任一步失败 → `err.code`:`NO_FOCUS` / `PASTE_UNSUPPORTED` / `NOT_CLICKABLE`。
响应 `data:{used:"paste"}` 标明实际走通粘贴路径。

注意:依赖剪贴板,会覆盖用户当前剪贴内容;调用方负责在前后保存/恢复剪贴。优先用 `set_text`,拒收时再用本 op。

### 4.3 坐标级操作(dispatchGesture,API 24+)

| op | args | 说明 |
|---|---|---|
| `tap` | `{x,y}` | 坐标点击 |
| `long_press` | `{x,y,duration?:默认1000}` | 坐标长按 |
| `swipe` | `{x1,y1,x2,y2,duration?:默认300}` | 滑动 |
| `gesture` | `{points:[{x,y}...],duration}` | 任意路径 |

### 4.4 系统级

| op | args | 执行 |
|---|---|---|
| `global` | `{action:"back"\|"home"\|"recents"\|"notif"\|"qs"\|"screenshot"}` | performGlobalAction |
| `wait` | `{ms:int}` 或 `{event:"WINDOW_STATE_CHANGED"\|...,timeout:int}` | 睡眠 / 等事件,超时→`TIMEOUT`(event 形态见 §4.5) |
| `start` | `{pkg:string, cls?:string}` | 拉起指定包的 launcher(或显式 Activity 类名),`FLAG_ACTIVITY_NEW_TASK` |

## 4.5 实现注记(v1.2)

- **scroll 方向映射**:Android 只提供 `ACTION_SCROLL_FORWARD`/`ACTION_SCROLL_BACKWARD` 两个方向 int 动作(无 UP/DOWN/LEFT/RIGHT)。约定 `down`/`right`→FORWARD、`up`/`left`→BACKWARD。竖直列表按 `down`/`up` 用即可。
- **`set_text` 失败 → 降级**:`ACTION_SET_TEXT` 返回 false 时返回 `err.code=SET_TEXT_FAILED`,调用方据此改发 `set_text_fallback`(聚焦→剪贴板→ACTION_PASTE)。错误码枚举新增 `SET_TEXT_FAILED`。
- **`wait(event)`**:v1.2 仅占位,未实现;设备侧宿主接入事件流后再补,现只支持 `{ms}` 睡眠。
- **`set_text` 的 `text` 是值不是匹配条件**:`set_text`/`set_text_fallback` 的 `args.text` 为"要填入的文本",**不**作为 find 条件;匹配仅靠 `id`/`desc`/`cls`。宿主实现 parseMatch 时须特判(否则会去找"文本含关键词"的 EditText 而失败)。
- **载体(已落地)**:设备侧宿主 APP(`com.guiagent.executor`)在 `onServiceConnected` 起 `WsCommandServer` 监听 `0.0.0.0:8322`,路径 `/guiagent`(手写 RFC 6455,纯 Java)。内网机器经 `ws://<设备IP>:8322/guiagent` 连接,文本帧载荷即一行 NDJSON。握手 `WsHandshake`、帧编解码 `WsFrame` 为无 Android 依赖的纯逻辑,可 JVM 单测。

## 5. 确定性原则(强制)

1. **坐标**:屏幕左上原点,单位 px,绝对坐标。
2. **单位**:时间 ms、坐标 px,字段名不带单位后缀。
3. **多匹配规则**:树前序第一个;`index` 显式选第 n 个(默认 0);多匹配时**仍取第一个**,不报歧义。
4. **节点句柄 `nid`**:`dump`/`find` 响应里每个节点带进程内 `nid`,可在紧接着的下一条指令里作为 find 条件复用,避免重复文本匹配漂移;`nid` 在节点 GC 前有效,过期→`STALE`。
5. **一问一答**:无悬挂响应、无乱序;`id` 保证可配对。
6. **错误码固定枚举**:`UNKNOWN_OP` / `BAD_ARGS` / `NO_MATCH` / `INDEX_OOB` / `NOT_CLICKABLE` / `NO_FOCUS` / `PASTE_UNSUPPORTED` / `SET_TEXT_FAILED` / `STALE` / `SVC_DOWN`(无障碍未开)/ `TIMEOUT` / `INTERNAL`。
7. **向后兼容**:只增字段不删不改语义;客户端忽略未知字段。

## 6. 载体无关性示例

指令字节与传输层无关。下面用 `send.py` 经 ws 发(设 `GUIAGENT_WS_HOST` 为设备 IP;Windows 加 `PYTHONUTF8=1`):

```bash
PYTHONUTF8=1 GUIAGENT_WS_HOST=192.168.1.10 python send.py '{"id":"1","op":"ping","args":{}}'
PYTHONUTF8=1 GUIAGENT_WS_HOST=192.168.1.10 python send.py '{"id":"2","op":"tap","args":{"x":540,"y":1200}}'
PYTHONUTF8=1 GUIAGENT_WS_HOST=192.168.1.10 python send.py '{"id":"3","op":"set_text","args":{"id":"search_box","text":"庆余年"}}'
PYTHONUTF8=1 GUIAGENT_WS_HOST=192.168.1.10 python send.py '{"id":"4","op":"dump","args":{"depth":3}}'
```
无 adb 隧道时,经 `adb forward tcp:8322 tcp:8322` 后用默认 host `127.0.0.1` 即可,指令一字不改。

## 7. 选定默认值(本版采用)

- op 命名:`snake_case`。
- 多匹配默认:取第一个(可被 `index` 覆盖)。
- 节点句柄 `nid`:保留。
- 传输载体:WebSocket `0.0.0.0:8322 /guiagent`。
