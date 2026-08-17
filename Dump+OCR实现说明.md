# Dump + OCR 融合方案 — 实现说明

> **实现日期**：2026-08-12  
> **版本**：v2.1（按新方案实现）

---

## 一、已实现的核心功能

### 1.1 `observe_screen()` — 纯观察

**文件位置**：`commands/ocr/cmd_observe_screen.py`

**功能**：
- 获取当前屏幕信息（包名、Activity、尺寸）
- 截图并计算哈希（screen_version 的一部分）
- dump UI 树并计算哈希
- 提取可操作候选容器（clickable 祖先节点）
- 运行 OCR 识别文本
- 融合 dump 和 OCR，返回统一元素列表
- 更新观察缓存

**返回格式**：
```json
{
  "screen_version": "pkg:activity:shotHash:treeHash",
  "package": "com.example.video",
  "activity": "PlayerActivity",
  "screen_size": {"width": 1280, "height": 800},
  "dump_status": "ok|partial|unavailable",
  "ocr_status": "ok|empty|failed",
  "element_count": 42,
  "elements": [
    {
      "element_id": "e_17",
      "label": "第3集",
      "action_rect": [800, 590, 960, 690],
      "action_point": [880, 640],
      "source": "dump+ocr",
      "click_confidence": 0.94,
      "evidence": {
        "ocr": {"text": "第3集", "bounds": [...], "confidence": 0.98},
        "dump": {"text": "", "resource_id": "episode_item", "clickable": true}
      }
    }
  ]
}
```

**关键设计**：
- **纯观察**：不改变设备状态（不 tap、不滑动）
- **可操作候选容器**：找 clickable 祖先节点，不是只找文本节点
- **融合逻辑**：多条件匹配（包含关系、重叠度、语义证据）
- **screen_version**：pkg + activity + screenshot_hash + tree_hash

### 1.2 `click_element(element_id, screen_version)` — 按 ID 点击

**文件位置**：`commands/ocr/cmd_click_element.py`

**功能**：
- 校验 element_id 存在于观察缓存
- 校验 screen_version 未过期
- 点击元素的 action_point
- 动作后失效观察缓存

**关键设计**：
- **必须提供 screen_version**：防止过期点击
- **校验 element_id**：确保元素存在且未过期
- **动作后失效缓存**：强制重新观察

### 1.3 `reveal_controls()` — 显式唤出控件

**文件位置**：`commands/ocr/cmd_reveal_controls.py`

**功能**：
- 点击屏幕中央（640, 400）唤出播放器控制条
- 等待 0.8 秒让动画完成
- 失效观察缓存
- 返回提示让 Agent 重新观察

**关键设计**：
- **独立命令**：不与 observe_screen 混合
- **Agent 判断需要时才调用**：不是自动执行
- **动作后失效缓存**：强制重新观察

### 1.4 观察缓存

**文件位置**：`commands/ocr/observation_cache.py`

**功能**：
- 存储最近一次 observe_screen 的结果
- 提供 element_id 查询
- 提供 screen_version 校验
- 动作后自动失效

**缓存策略**：
- 只保留最近一次观察结果
- 30 秒有效期
- 任何动作后失效

---

## 二、文件结构

```
app/src/main/java/com/guiagent/executor/commands/
├── ocr/
│   ├── __init__.py
│   ├── cmd_observe_screen.py      # 观察命令
│   ├── cmd_click_element.py        # 点击命令
│   ├── cmd_reveal_controls.py      # 唤出控件命令
│   └── observation_cache.py        # 观察缓存
├── server.py                       # 已更新，注册新命令
└── ...

agent/
├── agent.py                        # 已更新 system prompt
├── commands.py                     # 已更新 COMMAND_DOCS
└── ...
```

---

## 三、测试步骤

### 3.1 启动设备端服务

```bash
# 在设备上启动 GUIAgent 无障碍服务
# 确保 WS :8322 和 HTTP :8765 都已启动

# 启动 Python HTTP 服务
cd /d/GUIAPP-main/app/src/main/java/com/guiagent/executor/commands
python server.py --port 8765
```

### 3.2 测试 observe_screen

```python
import requests

# 调用 observe_screen
resp = requests.post("http://127.0.0.1:8765/v1/compound", json={
    "command": "observe_screen",
    "params": {}
})

data = resp.json()
print(f"screen_version: {data['data']['screen_version']}")
print(f"dump_status: {data['data']['dump_status']}")
print(f"ocr_status: {data['data']['ocr_status']}")
print(f"element_count: {data['data']['element_count']}")

# 打印前 5 个元素
for elem in data['data']['elements'][:5]:
    print(f"  {elem['element_id']}: {elem['label']} @ {elem['action_point']}")
```

### 3.3 测试 click_element

```python
# 从上一步获取 element_id 和 screen_version
element_id = "e_17"  # 替换为实际值
screen_version = data['data']['screen_version']

# 点击元素
resp = requests.post("http://127.0.0.1:8765/v1/compound", json={
    "command": "click_element",
    "params": {
        "element_id": element_id,
        "screen_version": screen_version
    }
})

print(resp.json())
```

### 3.4 测试 reveal_controls

```python
# 唤出播放器控件
resp = requests.post("http://127.0.0.1:8765/v1/compound", json={
    "command": "reveal_controls",
    "params": {}
})

print(resp.json())

# 再次观察
resp = requests.post("http://127.0.0.1:8765/v1/compound", json={
    "command": "observe_screen",
    "params": {}
})

# 检查是否出现控制条元素
```

### 3.5 端到端测试（Agent）

```python
from agent import VideoAgent

agent = VideoAgent()

# 测试：暂停播放
reply = agent.chat("暂停播放")
print(f"Agent: {reply}")

# 测试：播放第3集
reply = agent.chat("播放第3集")
print(f"Agent: {reply}")
```

---

## 四、验收标准

### 4.1 功能验收

- [ ] `observe_screen` 能返回元素列表
- [ ] 元素包含 element_id、label、action_point、source、click_confidence
- [ ] dump_status 和 ocr_status 正确反映数据可用性
- [ ] `click_element` 能正确点击元素
- [ ] screen_version 不匹配时拒绝点击
- [ ] `reveal_controls` 能唤出播放器控件
- [ ] 动作后观察缓存自动失效

### 4.2 融合逻辑验收

- [ ] OCR 文本正确绑定到 clickable 祖先容器
- [ ] 纯图标元素（有 content-desc 或 resource-id）被保留
- [ ] 相邻列表项不会错误绑定
- [ ] dump 失效时仍能返回 OCR-only 元素

### 4.3 Agent 验收

- [ ] Agent 能正确调用 observe_screen
- [ ] Agent 能根据元素列表选择目标
- [ ] Agent 能正确调用 click_element
- [ ] Agent 能在点击后重新观察验证
- [ ] Agent 不会暴露技术细节（element_id、screen_version）

---

## 五、已知限制

1. **OCR 性能**：截图 + OCR 耗时约 500ms-1s
2. **隐藏控件**：需要 Agent 主动调用 reveal_controls
3. **纯图标**：OCR 无法识别无文本的图标，依赖 dump 的 content-desc
4. **缓存有效期**：30 秒，超时后需要重新观察

---

## 六、下一步优化

1. **性能优化**：
   - 按需 OCR（某些场景可以只用 dump）
   - 截图缩放后 OCR
   - 缓存优化

2. **融合逻辑优化**：
   - 多条件匹配权重调整
   - 歧义拒绝策略优化

3. **页面操作记忆**：
   - 实现跨会话的定位策略缓存
   - 高频页面的加速层

4. **Agent prompt 优化**：
   - 根据实际失败案例调整
   - 添加更多示例

---

**文档版本**：v1.0  
**创建日期**：2026-08-12
