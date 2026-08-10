# 爱奇艺（iQiyi）播放器适配

> 本文件夹存放**爱奇艺 APP 播放页面**的所有独立适配内容。

---

## 一、背景与需求

### 1.1 当前系统架构

```
用户发指令 → run-search.py（通用搜索）→ 搜索结果页（多片源混合）
                                            ↓
                                      run-play.py（通用点击）
                                            ↓
                                  进入某片源的播放页（如爱奇艺）
                                            ↓
                              ┌─────────────────────────────────┐
                              │  以下操作需要按 APP 分别适配：    │
                              │  run-toggle.py    播放/暂停      │
                              │  run-episode.py   选集+下一集(自适应)   │
                              │  run-speed.py     调倍速         │
                              │  run-volume.py    调音量（右滑）  │
                              │  run-brightness.py 调亮度（左滑） │
                              │  run-detail.py    详情页 in/out(自适应) │
                              └─────────────────────────────────┘
```

### 1.2 为什么要分 APP 适配

`run-search.py` 和 `run-play.py` 操作的是 **whohuatv launcher**（统一搜索入口），所有片源集中管理，这两个脚本不需要改。

但点进某个供应商的片源后（比如选了爱奇艺的《飞驰人生》），就进入了**爱奇艺的播放页面**。此时：

- 每个 APP 的播放器 UI 架构完全不同（不同的 resource-id、不同的按钮布局、不同的手势规则）
- 当前通用脚本靠 desc/text 子串猜测（如 `["暂停","播放","pause","play"]`），容易误匹配或匹配不到
- 音量/亮度手势依赖播放器是否支持对应屏区的手势，各 APP 行为不一

**结论**：搜索和选片是通用的，但进入播放器后的所有操作必须按 APP 做独立适配。

---

## 二、设备信息

| 项目 | 值 |
|---|---|
| 中屏设备编号 | `7ZA6DJKWS3` |
| 连接方式 | USB（adb 直连） |
| 屏幕分辨率 | 1280×800（横屏） |
| SDK 版本 | 28 |
| 搜索入口 | whohuatv launcher（统一） |
| 目标播放器 | 爱奇艺 APP |
| 爱奇艺包名 | `com.qiyi.video.speaker`（中屏/音箱定制版，非手机版） |
| GUIAgent 服务 | `com.guiagent.executor` |
| adb 隧道 | `adb -s 7ZA6DJKWS3 forward tcp:8322 tcp:8322` |

---

## 三、爱奇艺播放页 UI 结构

> 详细节点数据见 [`ui-dump/iqiyi-player-ui.md`](ui-dump/iqiyi-player-ui.md)

### 3.1 控制条

控制条默认隐藏，需 tap 唤出，约 3-5 秒后自动隐藏。

**唤出方式**：`tap (640, 200)` — 视频区域**顶部**。
> ⚠️ **不要 tap 中心 (640, 400)**：中心在某些状态下会直接切换播放/暂停而不是唤出控制条。顶部 tap 始终可靠。

### 3.2 核心按钮坐标

| 功能 | res-id | 坐标中心 | 备注 |
|---|---|---|---|
| 播放/暂停 | `btn_pause` | (55, 724) | ImageView |
| 下一集 | `im_play_next` | (177, 724) | ImageView |
| 倍速入口 | `tv_change_speed_play` | (846, 724) | TextView, text="倍速" |
| 选集入口 | `tv_change_episode` | (1212, 724) | TextView, text="选集" |
| 画质 | `tv_play_rate` | (1029, 724) | 如"超清480P" |
| 只看TA | `tv_only_you` | (682, 724) | |
| 返回 | `btn_back` | (52, 53) | 顶部左上 |
| 更多 | `btn_more` | (1229, 53) | 顶部右上 |
| 标题 | `video_title` | — | 含当前集数，如"灿如繁星第2集" |

### 3.3 倍速面板

点击倍速入口后弹出，位于屏幕右半部分。

| 档位 | res-id | 坐标中心 |
|---|---|---|
| 0.75X | `textview_075_speed` | (999, 211) |
| 1.0X | `textview_normal_speed` | (999, 302) |
| 1.25X | `textview_125_speed` | (999, 399) |
| 1.5X | `textview_150_speed` | (999, 496) |
| 2.0X | `textview_200_speed` | (999, 587) |

### 3.4 选集面板

点击选集入口后弹出，位于屏幕右半部分。5 列网格。

| 组件 | res-id | 说明 |
|---|---|---|
| 面板标题 | `episodePanelTitle` | text="选集" |
| 关闭按钮 | `close` | (1237, 53) 面板右上角 |
| 剧集网格 | `episodeGridView` | 5列×N行, scrollable |
| 单集格子 | `episode_item` | TextView, text=集数 |

---

## 四、选集面板的正集/预告问题

### 4.1 问题描述

爱奇艺中屏版的选集面板中，**正集和预告是岔开排列的**（由于会员权益限制）。例如当前布局：

```
row0: 1(正集)  2(正集)  3(预告)  4(预告)  5(预告)
row1: 6(预告)  3(正集)  4(正集)  5(正集)  6(正集)
row2: 7(正集)  8(正集)  9(正集)  10(正集) 11(正集)
...
```

同一集数在 grid 中可能出现多次（一次预告、一次正集），它们的 `episode_item.text` 相同。

### 4.2 Accessibility 无法区分

从 accessibility dump 来看，正集和预告的 cell **属性完全一致**：
- `id`：空
- `cls`：RelativeLayout
- `clickable`：True
- `enabled`：True
- `desc`：空

**唯一区别在视觉层**（文字颜色、"预告"标签等），accessibility tree 抓不到这些信息。这是 iQiyi APP 的 accessibility 实现限制。

### 4.3 解决方案：用户看列表后指定序号

由于无法自动区分正集/预告，选集功能改为**用户看列表后指定序号**：
1. `python aiqiyi/run-episode.py open` 打开面板，脚本列出当前可见项
2. 用户在中屏上看面板，确定目标是哪一行（正集还是预告）
3. `python aiqiyi/run-episode.py select N` 选择第 N 个可见项
4. 如需滚动查看更多：`scroll up N` / `scroll down N` 后 `list` 再 `select`

这样用户可以直接看到哪个是正集、哪个是预告，避免脚本猜错。

---

## 五、时序规则（关键）

经过大量实测，发现以下时序规律：

### 5.1 控制条唤出与消失

- tap `(640, 200)` 唤出控制条
- 控制条约 3-5 秒后自动隐藏
- tap 后需等 ~2 秒让控制条完全渲染

### 5.2 dump/find 后的 tap 时序

- **dump/find 后必须立刻 tap 目标按钮**（不能再加 wait）
- 如果 dump 后等待再 tap，控制条可能已开始消失，导致 tap 落空
- 正确模式：`tap_wake → sleep(2s) → dump/find → 立刻 tap_target`

### 5.3 两轮操作之间的间隔

- 如果需要做多轮 wake-dump 操作（如先读 video_title，再开面板）
- 两轮之间需等 **5 秒以上**，让上一轮的控制条完全消失
- 否则新的 wake tap 可能与残留的控制条交互，导致异常

### 5.4 click_node vs 坐标 tap

- `click_node` 有网络往返延迟（发请求→设备找节点→返回），调用期间控制条可能消失
- **坐标 tap** 是 fire-and-forget，无等待，对控制条按钮更可靠
- 本适配全部使用坐标 tap，不走 click_node

---

## 六、编码问题

### 6.1 数据编码正常

video_title 等字段的中文文本是**标准 UTF-8 编码**，数据本身没有问题。

### 6.2 终端显示乱码

Git Bash 终端显示中文时出现乱码（如 `灿如繁星` 显示为 `緱ǵ`）。这是**终端编码问题，不是数据问题**。

### 6.3 解决方案

将输出写入 UTF-8 文件后 `cat` 查看，或用 Python 文件 I/O 处理：
```python
with open('result.txt', 'w', encoding='utf-8') as f:
    f.write(f'title: {text}\n')
```

---

## 七、手势支持实测

| 手势 | 区域 | 结果 |
|---|---|---|
| 右侧垂直滑动 (x=75%, 700ms) | 音量 | ✅ **有效**，每次滑动改变系统 STREAM_MUSIC 音量 |
| 左侧垂直滑动 (x=25%, 700ms) | 亮度 | ✅ **有效**，每次滑动改变窗口级亮度（`dumpsys display` 的 mBrightness 变化） |

**结论**：
- 音量：右侧滑动手势（改系统 STREAM_MUSIC）
- 亮度：左侧滑动手势（改窗口级覆盖，不改系统 settings，用 `dumpsys display` 可观测）

---

## 八、目录结构与脚本

```
aiqiyi/
├── run-toggle.py        # 通用 (电视剧+电影)
├── run-volume.py        # 通用
├── run-brightness.py    # 通用
├── run-detail.py        # 通用 (自适应: 任意影片标题长度都能点到)
├── run-speed.py         # 自动适配 (检测有无选集按钮)
├── run-resolution.py    # 自动适配 (检测有无选集按钮)
├── detect.py            # 检测模块 (备用)
└── run-episode.py       # 电视剧+综艺通用: open/list/scroll/select/close/next
```

### 自动适配机制

`run-speed.py` 和 `run-resolution.py` 通过检测 UI 中是否存在 `tv_change_episode`（选集）按钮来判断当前内容类型：
- **有选集按钮** → TV 模式（电视剧/综艺/动画片等）
- **无选集按钮** → 电影模式

对应的按钮坐标：

| 按钮 | TV 模式坐标 | 电影模式坐标 |
|---|---|---|
| 倍速 (`tv_change_speed_play`) | (846, 724) | (988, 724) |
| 清晰度 (`tv_play_rate`) | (1029, 724) | (1171, 724) |

用户无需关心当前是电视剧还是电影，只需执行：
```bash
python aiqiyi/run-resolution.py 720    # 自动适配
python aiqiyi/run-speed.py 1.5         # 自动适配
```

### 8.1 run-toggle.py — 播放/暂停 [通用]

- tap 顶部唤控制条 → tap `(55, 724)` 点击 btn_pause
- 用法：`python aiqiyi/run-toggle.py`

### 8.2 run-episode.py — 选集 [电视剧+综艺，自适应布局]

- **自动检测面板类型**：
  - **综艺**：垂直列表（每行一期，含标题/副标题/日期）
  - **电视剧**：网格布局（N 列 × M 行，单集格子）
- **所有坐标从 UI 树动态读取**，不依赖写死行列（标题再长/布局再变都不怕）
- 命令：
  - `open`：打开选集面板（带重试），面板保持打开
  - `list`：显示当前可见列表（面板需已打开）
  - `scroll up N`：向上滚动 N 次（面板保持打开，看更早的集）
  - `scroll down N`：向下滚动 N 次（面板保持打开，看更晚的集）
  - `select N`：选择第 N 个可见项（选择后面板关闭）
  - `close`：手动关闭面板（点右上角 close，**不能用 back**）
  - `next`：下一集（点控制条 `im_play_next`，不需要打开面板）
- 用法：
  ```
  python aiqiyi/run-episode.py open              # 打开选集面板
  python aiqiyi/run-episode.py list              # 查看列表
  python aiqiyi/run-episode.py scroll up 2       # 向上滚动 2 次
  python aiqiyi/run-episode.py scroll down 1     # 向下滚动 1 次
  python aiqiyi/run-episode.py select 3          # 选择第 3 个
  python aiqiyi/run-episode.py close             # 关闭面板
  python aiqiyi/run-episode.py next              # 下一集
  ```
- 典型工作流：
  ```
  1. python aiqiyi/run-episode.py open           # 打开面板
  2. python aiqiyi/run-episode.py list           # 看当前可见集
  3. python aiqiyi/run-episode.py scroll up 1    # 不够就往上滚
  4. python aiqiyi/run-episode.py select 2       # 选第 2 个
  ```

### 8.3 run-speed.py — 调倍速 [自动适配]

- 自动检测 TV/电影模式，选择对应坐标
- tap 顶部唤控制条 → 检测模式 → tap 倍速按钮 → 选择档位
- 用法：
  ```
  python aiqiyi/run-speed.py 0.75    # 0.75倍速
  python aiqiyi/run-speed.py 1.0     # 1.0倍速（正常速度）
  python aiqiyi/run-speed.py 1.5     # 1.5倍速
  python aiqiyi/run-speed.py 2.0     # 2.0倍速
  ```

### 8.4 run-resolution.py — 调清晰度 [自动适配]

- 自动检测 TV/电影模式，选择对应坐标
- tap 顶部唤控制条 → 检测模式 → tap 清晰度按钮 → 选择选项
- 清晰度选项: 1080P(VIP) / 720P(登录) / 480P(免费)
- 点击非当前清晰度会跳转登录/会员页面，跳转即表示点击成功
- 用法：
  ```
  python aiqiyi/run-resolution.py 1080   # 切到1080P
  python aiqiyi/run-resolution.py 720    # 切到720P
  python aiqiyi/run-resolution.py 480    # 切到480P
  ```

### 8.5 run-volume.py — 调音量 [通用]

- 屏幕右侧 (x=75%) 垂直慢滑
- **音量幅度控制**：通过滑动距离（占屏高百分比）和 duration 调节每次改变的音量幅度
  - 当前参数：滑动距离 15% 屏高（0.425-0.575），duration 400ms
  - 每次 up/down 约改变 5 级音量（总范围 0-255）
  - 如需调整：减小距离/缩短 duration → 音量变化更小；反之更大
- 用法：`python aiqiyi/run-volume.py up|down [次数]`

### 8.6 run-brightness.py — 调亮度 [通用]

- 屏幕左侧 (x=25%) 垂直慢滑
- **亮度幅度控制**：通过滑动距离（占屏高百分比）和 duration 调节每次改变的亮度幅度
  - 当前参数：滑动距离 15% 屏高（0.425-0.575），duration 400ms
  - 爱奇艺走窗口级亮度覆盖（`dumpsys display` mBrightness），不改系统 settings
  - 如需调整：减小距离/缩短 duration → 亮度变化更小；反之更大
- 用法：`python aiqiyi/run-brightness.py up|down [次数]`

### 8.7 run-detail.py — 详情页 [通用/自适应]

- **自适应找按钮（不依赖固定坐标）**：
  1. `tap (640, 200)` 唤出控制条
  2. `dump` UI 树，**子串匹配 id 含 `video_detail` 的节点**（兼容 `video_detail1` / `video_detail2` / 将来任何版本）
  3. 用找到节点的 `bounds` 算中心，直接 `tap`
  - 影片标题再长都不怕——按钮被挤到哪就点到哪，不再靠写死坐标
- `out`：tap `(200, 400)` 屏幕左侧空白区域返回播放页（详情页在右侧，点左侧即关闭）
- 用法：
  ```
  python aiqiyi/run-detail.py in              # 进入详情页
  python aiqiyi/run-detail.py out             # 退出详情页
  ```

---

## 九、注意事项

1. **广告/会员弹窗**：进入播放页后可能有广告，需要先跳过或等待结束
2. **控制条自动隐藏**：操作前需要先 tap 顶部唤出
3. **横屏坐标**：所有坐标基于 1280×800 横屏，dump 出的坐标以实际屏幕方向为准
4. **版本号差异**：爱奇艺 APP 不同版本的 UI 结构可能不同，当前适配基于 `com.qiyi.video.speaker` 当前安装版本
5. **选集面板关闭**：必须点面板右上角 `close` 按钮关闭，**不要用 back**（back 会退出播放页）
6. **正集/预告**：选集面板中正集和预告岔排，无法自动区分，需用户看列表后指定序号（`open` → `list` → `select N`）

---

## 十、执行步骤

### 10.1 建 adb 隧道

```bash
adb -s 7ZA6DJKWS3 forward tcp:8322 tcp:8322
```

### 10.2 进入爱奇艺播放页

```bash
set PYTHONUTF8=1
python run-search.py 飞驰人生
python run-play.py <序号>    # 选爱奇艺的片源
```

### 10.3 使用适配脚本

```bash
# 通用脚本 (电视剧+电影通用)
python aiqiyi/run-toggle.py              # 播放/暂停
python aiqiyi/run-volume.py up 3         # 音量调高3格
python aiqiyi/run-brightness.py up 2     # 亮度调亮2格
python aiqiyi/run-detail.py in           # 进入详情页
python aiqiyi/run-detail.py out          # 退出详情页

# 自动适配脚本 (自动检测电视剧/电影)
python aiqiyi/run-speed.py 1.5           # 倍速 1.5x
python aiqiyi/run-resolution.py 720      # 清晰度 720P

# 电视剧 + 综艺通用 (自适应布局)
python aiqiyi/run-episode.py open            # 打开选集面板
python aiqiyi/run-episode.py list            # 查看列表
python aiqiyi/run-episode.py scroll up 2     # 向上滚动 2 次
python aiqiyi/run-episode.py scroll down 1   # 向下滚动 1 次
python aiqiyi/run-episode.py select 3        # 选择第 3 个
python aiqiyi/run-episode.py close           # 关闭面板
python aiqiyi/run-episode.py next            # 下一集
```

---

## 十一、参考文档

- [`README.md`](../README.md) — GUIAgent 总体架构与使用指南
- [`instruction-protocol.md`](../instruction-protocol.md) — 指令格式规约 v1.2
- [`video-player-ops.md`](../video-player-ops.md) — 视频播放器原子操作清单
- [`ui-dump/iqiyi-player-ui.md`](ui-dump/iqiyi-player-ui.md) — 爱奇艺播放页 UI 树详细数据
