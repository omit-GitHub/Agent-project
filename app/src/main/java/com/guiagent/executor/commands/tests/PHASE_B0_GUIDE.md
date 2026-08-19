# Phase B0: Visual Detector 准入实验 — 操作指南

## 目标
收集 100-200 张真实中屏截图，用于评估 Visual UI Detector（OmniParser）的性能。

## 步骤

### 1. 准备环境
```bash
# 确保 ADB 连接正常
adb devices

# 如果有多个设备，指定序列号
export ANDROID_SERIAL=<设备序列号>
```

### 2. 运行截图采集
```bash
cd app/src/main/java/com/guiagent/executor/commands
python tests/collect_screenshots.py --output ./data/screenshots --count 150
```

**交互模式**（推荐）：
- 每张截图后会询问页面类型、控制条状态、特殊标签
- 按 Enter 继续下一张

**自动模式**：
```bash
python tests/collect_screenshots.py --output ./data/screenshots --count 150 --auto
```

### 3. 场景覆盖要求

| 场景类别 | 目标数量 | 说明 |
|---------|---------|------|
| **player** | 30-40 | 播放器页面（控制条显隐各半） |
| **detail** | 15-20 | 影片详情页 |
| **search** | 10-15 | 搜索结果页 |
| **list/grid** | 20-25 | 列表/网格页（选集、推荐） |
| **dialog/overlay** | 15-20 | 弹窗/浮层（倍速、清晰度面板） |
| **其他** | 10-15 | 主页、设置等 |

**特殊标签**（尽量覆盖）：
- `pure_icon`: 纯图标按钮（播放/暂停、全屏）
- `small_icon`: 小图标（<50x50 像素）
- `ad`: 广告页面
- `dark_theme`: 深色主题
- `light_theme`: 浅色主题

### 4. App 覆盖

| App | 包名 | 目标截图数 |
|-----|------|-----------|
| 爱奇艺 | com.qiyi.video.speaker | 50-60 |
| 腾讯视频 | com.tencent.qqlive | 50-60 |
| 夸克网盘 | com.quark.browser | 20-30 |

### 5. 操作提示

1. **播放器页面**：
   - 打开视频，截取控制条显示状态
   - 等待控制条自动隐藏，再截取隐藏状态
   - 尝试打开倍速/清晰度面板，截取弹窗状态

2. **详情页**：
   - 从搜索结果进入影片详情
   - 截取不同布局（横版/竖版海报）

3. **列表页**：
   - 选集列表（网格布局）
   - 推荐列表（卡片布局）

4. **特殊场景**：
   - 广告播放时截取
   - 深色/浅色主题切换后截取

### 6. 数据集结构

采集完成后，目录结构如下：
```
data/screenshots/
├── manifest.jsonl          # 元信息（每行一个 JSON）
├── screen_20260819_120000_000.png
├── screen_20260819_120030_001.png
── ...
```

`manifest.jsonl` 格式：
```json
{
  "filename": "screen_20260819_120000_000.png",
  "timestamp": "20260819_120000",
  "package": "com.tencent.qqlive",
  "activity": ".audiobox.PlayerActivity",
  "page_type": "player",
  "control_bar_visible": "visible",
  "tags": ["pure_icon"],
  "width": 1280,
  "height": 800
}
```

### 7. 下一步

数据集收集完成后，运行评估脚本：
```bash
python tests/evaluate_detector.py --data ./data/screenshots --model omni-parser
```

评估指标：
- 总体目标召回率（>= 0.90 通过）
- 纯图标召回率（>= 0.85 通过）
- p95 延迟（<= 900ms 通过）
- 候选数 p95（<= 40 通过）

---

## 快速开始

```bash
# 1. 连接设备
adb connect <设备 IP>:5555

# 2. 开始采集（交互模式）
cd app/src/main/java/com/guiagent/executor/commands
python tests/collect_screenshots.py --output ./data/screenshots --count 150

# 3. 按提示标记每张截图的场景
# 4. 完成后通知 Claude 继续评估
```
