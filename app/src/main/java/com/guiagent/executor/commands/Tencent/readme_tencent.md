# 腾讯视频（Tencent Video）播放器适配

> 本文件夹存放**腾讯视频 APP 播放页面**的所有独立适配内容。

---

## 一、应用信息

| 项目 | 值 |
|---|---|
| 包名 | `com.tencent.qqlive.audiobox` |
| 说明 | 中屏/音箱定制版（非手机版 com.tencent.qqlive） |
| 设备 | 7ZA6DJKWS3 |
| 屏幕 | 1280×800（横屏） |
| Android | 9 (SDK 28) |

---

## 二、操作手册

### 2.1 播放/暂停

**脚本**: `run-toggle.py`

```bash
python Tencent/run-toggle.py
```

**功能**: 切换播放/暂停状态

**实现**:
- 唤出控制条（tap 顶部 640,200）
- 点击播放/暂停按钮（127,749）
- res-id: `playBtn`

---

### 2.2 倍速控制

**脚本**: `run-speed.py`

```bash
python Tencent/run-speed.py <倍速>
```

**参数**:
- `0.5` — 0.5 倍速
- `0.75` — 0.75 倍速
- `1.0` — 正常速度
- `1.25` — 1.25 倍速
- `1.5` — 1.5 倍速

**示例**:
```bash
python Tencent/run-speed.py 1.5    # 切换到 1.5 倍速
python Tencent/run-speed.py 0.75   # 切换到 0.75 倍速
```

**实现**:
- 唤出控制条
- 点击倍速按钮（1027,749）
- 选择对应倍速选项
- 5 档可选：0.5X, 0.75X, 1.0X, 1.25X, 1.5X

---

### 2.3 清晰度控制

**脚本**: `run-resolution.py`

```bash
python Tencent/run-resolution.py <清晰度>
```

**参数**:
- `270` — 270P
- `480` — 480P
- `720` — 720P（取决于影片支持）
- `1080` — 1080P（取决于影片支持）

**示例**:
```bash
python Tencent/run-resolution.py 480    # 切换到 480P
python Tencent/run-resolution.py 720    # 切换到 720P
```

**实现**:
- 唤出控制条
- 点击清晰度按钮（1138,749）
- 选择对应清晰度选项
- 可用选项取决于影片支持（当前测试影片有 270P 和 480P）

---

### 2.4 选集控制（综艺/电视剧）

**脚本**: `run-episode.py`

**自动页面类型检测**：
- 脚本会自动检测当前页面是**电视剧**还是**综艺**
- 检测方式：打开选集面板后，分析布局类型
  - **网格布局**（4 列 × N 行）→ 电视剧
  - **垂直列表**（单列）→ 综艺
- 检测结果会在打开面板时显示

**重试机制**：
- 如果面板未正确打开，脚本会自动重试最多 3 次
- 每次重试会等待 1 秒让面板充分渲染
- 如果 3 次都失败，会输出错误信息和可能原因

**支持两种布局**：
- **综艺**：垂直列表（每次显示约 8 集）
- **电视剧**：网格布局（4 列 × N 行，约 32 集可见）
- 脚本自动检测布局类型并采用相应的显示方式

#### 命令列表

```bash
python Tencent/run-episode.py open       # 打开选集面板
python Tencent/run-episode.py list       # 显示当前可见列表
python Tencent/run-episode.py scroll N   # 向上滚动 N 次
python Tencent/run-episode.py select N   # 选择第 N 个（面板关闭）
python Tencent/run-episode.py close      # 手动关闭面板
python Tencent/run-episode.py next       # 下一期/集
```

#### 工作流示例

```bash
# 1. 打开选集面板
python Tencent/run-episode.py open

# 2. 查看当前可见列表
python Tencent/run-episode.py list

# 3. 滚动查看更多剧集
python Tencent/run-episode.py scroll 2

# 4. 再次查看列表
python Tencent/run-episode.py list

# 5. 选择想要的剧集
python Tencent/run-episode.py select 3
```

#### 命令说明

| 命令 | 功能 | 面板状态 |
|---|---|---|
| `open` | 打开选集面板并显示列表 | 面板打开 |
| `list` | 显示当前可见列表（不执行操作） | 面板保持 |
| `scroll N` | 向上滚动 N 次，显示新列表 | 面板保持 |
| `select N` | 选择第 N 个可见剧集 | 面板关闭 |
| `close` | 手动关闭面板 | 面板关闭 |
| `next` | 切换到下一期/集 | 不涉及面板 |

#### 特性

- **面板保持打开**: 选集面板一旦打开就保持打开，不会自动关闭
- **独立命令**: 每个命令独立执行，不依赖前一个命令的状态
- **即时反馈**: 滚动后立即显示新列表，方便用户确认
- **可见列表**: 每次显示约 8 集，滚动可查看更多

---

### 2.5 详情页

**脚本**: `run-detail.py`

```bash
python Tencent/run-detail.py
```

**功能**: 打开影片简介/详情页

**实现**:
- 唤出控制条
- 点击简介按钮（928,749）
- res-id: `tv_plot_introduction`

---

### 2.6 下一期/集（快捷方式）

**脚本**: `run-episode.py next`

```bash
python Tencent/run-episode.py next
```

**功能**: 快速切换到下一期/集（不打开选集面板）

**实现**:
- 唤出控制条
- 点击下一期按钮（214,749）
- res-id: `nextPlay`

---

## 三、UI 结构

### 3.1 控制条

**唤出方式**: tap 屏幕顶部 (640, 200)

**自动隐藏**: 约 3-5 秒后自动隐藏

**关键按钮坐标**:

| 功能 | 坐标 | res-id |
|---|---|---|
| 播放/暂停 | (127, 749) | `playBtn` |
| 下一期 | (214, 749) | `nextPlay` |
| 选集 | (828, 749) | `episode_select_list` |
| 简介 | (928, 749) | `tv_plot_introduction` |
| 倍速 | (1027, 749) | `player_play_speed_text` |
| 清晰度 | (1138, 749) | `player_definition_text` |

### 3.2 倍速面板

**入口**: 点击倍速按钮 (1027, 749)

**选项**（5 档）:

| 倍速 | 坐标 |
|---|---|
| 0.5X | (684, 183) |
| 0.75X | (852, 183) |
| 1.0X | (1020, 183) |
| 1.25X | (1187, 183) |
| 1.5X | (684, 284) |

**注意**: 所有选项 res-id 相同（`play_speed_tv`），通过文本匹配区分

### 3.3 清晰度面板

**入口**: 点击清晰度按钮 (1138, 749)

**选项**（取决于影片）:

| 清晰度 | 坐标 |
|---|---|
| 270P | (757, 170) |
| 480P | (906, 170) |

**注意**: 更高清晰度（720P, 1080P）需要影片支持

### 3.4 选集面板

**入口**: 点击选集按钮 (828, 749)

**特性**:
- 面板打开后保持打开，不会自动关闭
- **自动检测布局类型**：
  - **综艺**：垂直列表（每次显示约 8 集）
  - **电视剧**：网格布局（4 列 × N 行，约 32 集可见）
- 可滚动查看更多
- 点击左侧空白区域关闭面板

#### 综艺 - 垂直列表

- 每个剧集是一个 `container` 元素
- 有 `desc` 属性（剧集描述/标题）
- 垂直排列，y 坐标间隔约 96 像素
- 包含部分可见的顶部和底部项目

**示例输出**：
```
面板类型: list
当前可见 8 集:
(垂直列表)
   1. (921,48) 致命的孽缘
   2. (921,134) 悍匪末路
   3. (921,230) 12岁少年手刃3位至亲
   ...
```

#### 电视剧 - 网格布局

- 每个剧集是一个 `container` 元素
- 4 列网格，每列 x 坐标：681, 838, 995, 1152
- 行 y 坐标间隔约 96 像素
- 每个 container 的 `desc` 是集数（如 "1", "2", "10"）
- 每次显示约 32 集（4 列 × 8 行）

**示例输出**：
```
面板类型: grid
当前可见 32 集:
(网格布局: 4 列)
   1. [行1列1] (681,97) 1
   2. [行1列2] (838,97) 2
   3. [行1列3] (995,97) 3
   4. [行1列4] (1152,97) 4
   5. [行2列1] (681,193) 5
   ...
  10. [行3列2] (838,289) 10
  ...
```

**布局检测逻辑**：
- 检查是否有多个 container 具有相同的 y 坐标（容差 20 像素）
- 如果有 → 网格布局
- 如果没有 → 垂直列表

---

## 四、手势支持

**结论**: ❌ 腾讯视频**不支持**左右侧滑手势调节音量/亮度

- 右侧滑动调音量: ❌ 不支持
- 左侧滑动调亮度: ❌ 不支持

**原因**: 腾讯视频播放页未实现手势识别，或手势被其他功能占用。

**替代方案**: 
- 使用设备物理音量键
- 或通过系统设置调节

---

## 五、脚本清单

| 脚本 | 功能 | 状态 |
|---|---|---|
| `run-toggle.py` | 播放/暂停 | ✅ 已完成 |
| `run-speed.py` | 调倍速 | ✅ 已完成 |
| `run-resolution.py` | 调清晰度 | ✅ 已完成 |
| `run-detail.py` | 打开详情页 | ✅ 已完成 |
| `run-episode.py` | 选集控制 | ✅ 已完成 |

---

## 六、时序规则

### 6.1 控制条

- **唤出延迟**: tap 后约 1.5-2 秒完全显示
- **自动隐藏**: 约 3-5 秒后自动隐藏
- **操作窗口**: 唤出后需在 3-5 秒内完成操作

### 6.2 选集面板

- **打开延迟**: tap 选集按钮后约 0.8 秒面板完全显示
- **保持打开**: 面板不会自动关闭，需手动关闭或选择剧集后关闭
- **滚动响应**: 滚动后立即更新显示

### 6.3 其他面板

- **倍速面板**: 打开后需等待约 1 秒再选择选项
- **清晰度面板**: 打开后需等待约 1 秒再选择选项

---

## 七、边缘情况

### 7.1 VIP 内容

当前页面有"开通VIP"按钮，说明可能存在 VIP 付费墙：
- 免费内容可正常播放
- VIP 内容可能需要登录或付费
- 试看结束后会提示开通会员

### 7.2 编码问题

UI dump 中的中文文本在终端显示时可能乱码，但数据本身是 UTF-8。

**处理方式**:
- 写入文件时用 `encoding='utf-8'`
- 脚本内部使用 `errors='replace'` 处理编码

### 7.3 选集列表滚动

选集列表是可滚动的，每次只显示部分剧集（约 8 集）。需要使用 `scroll` 命令查看更多。

---

## 八、参考文档

- [`../android-video-app-adapter/SKILL.md`](../android-video-app-adapter/SKILL.md) — 适配方法论
- [`../android-video-app-adapter/references/iqiyi-example.md`](../android-video-app-adapter/references/iqiyi-example.md) — 爱奇艺案例
- [`ui-dump/`](ui-dump/) — UI 树快照

---

## 九、使用示例

### 完整工作流

```bash
# 1. 搜索影片（使用通用脚本）
python run-search.py 庆余年

# 2. 选择腾讯视频片源（使用通用脚本）
python run-play.py 3

# 3. 进入播放页后，使用腾讯视频专用脚本
python Tencent/run-toggle.py              # 播放/暂停
python Tencent/run-speed.py 1.5           # 1.5 倍速
python Tencent/run-resolution.py 480      # 480P 清晰度

# 4. 选集
python Tencent/run-episode.py open        # 打开选集面板
python Tencent/run-episode.py list        # 查看列表
python Tencent/run-episode.py scroll 2    # 滚动 2 次
python Tencent/run-episode.py select 3    # 选择第 3 个

# 5. 查看详情
python Tencent/run-detail.py              # 打开详情页
```
