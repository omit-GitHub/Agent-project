# GUIAgent 无 Dump 双通路视觉操作框架：Cursor 实施任务书

> 本文直接交给 Cursor 执行。目标是在现有 GUIAgent 仓库内，将当前“全图 VLM 自由坐标点击”和“dump+OCR 独立观察”改造成：**OCR 文字通路 + Visual UI Detector 图标通路并行生成候选，VLM 优先选择 candidate_id，Harness 统一校验、执行、验证和恢复**。最终运行链路不得调用 UI dump。

## 0. 必须遵守的改造边界

### 0.1 保留的现有能力

不得重写或绕过以下资产：

- Android `GuiAgentService`、`WsCommandServer` 和现有原子操作协议；
- `tap`、`swipe`、`remote_key`、`global_action`、媒体键和文本输入能力；
- Python `server.py + registry.py + send.py` 命令体系；
- `observation/harness/` 的动作白名单、步数预算和敏感操作拦截；
- `reveal_controls`、DPAD、验证、恢复、trace；
- 千问 VLM OpenAI-compatible API 接入；
- App 专属命令的外部命令名，迁移期间保持兼容。

### 0.2 最终必须移除的依赖

最终感知、状态、验证和 App 操作链路均不得依赖：

- Accessibility UI tree dump；
- `ws_dump()`、`find_nodes()`、`find_node_in_tree()`；
- dump node 的 `clickable`、`resource_id` 或 bounds；
- 完整截图 hash 作为动态视频页面的页面版本；
- VLM 对整张截图一次性给出的自由坐标作为默认点击依据。

迁移期间可以暂时保留旧代码用于对照，但完成验收前必须停止注册或删除活动调用。不得把 dump 留作“可选主路径”。

### 0.3 当前代码中的关键问题

1. `observation/screen/cmd_observe_screen.py` 已实现 OCR，但同时依赖 dump，并把 OCR-only 文本框中心当作可点击点。
2. `observation/harness/action_loop.py` 没有调用 `observe_screen`，因此 OCR 结果没有进入 VLM 决策；当前仍是“截图 → VLM bbox → 点击”。
3. `tap_to_pixel()` 假设千问内部使用 1024×1024 padding，这不是稳定 API 契约，可能产生二次坐标偏移。
4. `registry.capture_state()` 和 `state/resolver.py` 仍依赖 dump。
5. `NextAction` 支持 `type_text`，但 `execute_action()` 未实现对应动作。
6. `max_steps=6`、`max_observations=3`，而每步都会 observe，实际最多只能运行 3 步。
7. 动态视频每帧都变化，不能用整图 hash 判断 screen 是否过期或 UI 是否稳定。

## 1. 目标运行链路

```text
用户子目标
  → Memory Router
  → 高置信 Shortcut：当前截图 → ROI 快速重定位/验证
      → 命中：直接进入 ActionGuard
      → 未命中：降级到通用探索
  → 通用探索：截图
  → OCRGenerator 与 VisualDetector 带独立 deadline 并行
  → CandidateMerger 合并、去重、评分
  → SoMRenderer 绘制候选编号
  → Qwen VLM 选择唯一 candidate_id 或非点击动作
  → ActionGuard 校验 candidate、页面版本、安全策略
  → Executor 使用原始像素坐标执行
  → LocalVerifier 快速验证
  → 不确定时 VLMVerifier
  → 成功后更新 Experience Memory
```

正常路径中，VLM 不输出坐标，只选择候选。只有候选生成失败时才允许：

```text
全图 VLM 粗定位 ROI → 裁剪 → 局部 VLM 精定位 → tap_visual → 强验证
```

## 2. 目标目录结构

在现有 `app/src/main/java/com/guiagent/executor/commands/observation/` 下整理为：

```text
observation/
├── screen/
│   ├── provider.py                 # ScreenshotProvider 抽象和 ADB 实现
│   ├── models.py                   # ScreenshotFrame
│   └── cmd_observe_screen.py       # 无 dump 的统一观察入口
├── ocr/
│   ├── engine.py                   # RapidOCR 单例和 OCRCandidate 生成
│   └── normalizer.py               # 文本清洗、噪声过滤
├── detector/
│   ├── interface.py                # UiDetector Protocol
│   ├── sidecar_client.py           # 视觉检测 sidecar HTTP 客户端
│   └── fallback.py                 # 检测器不可用时的受控降级
├── candidates/
│   ├── schemas.py                  # UiCandidate、CandidateMap
│   ├── builder.py                  # 并行执行候选生成器
│   ├── merger.py                   # IoU/包含关系合并与去重
│   ├── scorer.py                   # clickable_likelihood
│   ├── som_renderer.py             # 生成带编号截图
│   ├── fingerprint.py              # 动态页面 UI 指纹
│   └── cache.py                    # 替换旧 observation_cache
├── grounding/
│   ├── roi.py                      # ROI 裁剪和坐标映射
│   └── vlm_grounder.py             # 最后兜底的局部 VLM 定位
├── vlm/
│   ├── client.py
│   ├── prompts.py
│   ├── schemas.py
│   └── screenshot.py               # 改为调用 screen/provider
├── harness/
│   ├── action_guard.py
│   ├── action_loop.py
│   ├── executor.py
│   └── control_revealer.py
├── verify/
│   ├── local_verifier.py
│   ├── vlm_verifier.py
│   └── recovery.py
└── memory/
    ├── models.py
    ├── repository.py
    ├── matcher.py
    ├── recorder.py
    └── extractor.py
```

可以在现有文件上重构，不要求机械地全部新建，但职责和公开接口必须与本文一致。

## 3. 配置与依赖

### 3.1 环境变量

```dotenv
VLM_API_KEY=
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
VLM_MODEL=qwen-vl-plus
VLM_ENABLE_THINKING=false
VLM_TIMEOUT_SECONDS=20
VLM_MAX_TOKENS=500

GUIAGENT_MAX_STEPS=8
GUIAGENT_COMMON_MAX_VLM_CALLS=4
GUIAGENT_HARD_MAX_VLM_CALLS=6
GUIAGENT_MAX_RECOVERIES=2
GUIAGENT_COMMAND_TIMEOUT_SECONDS=20
GUIAGENT_TRACE_DIR=./runtime/traces
GUIAGENT_SCREENSHOT_DIR=./runtime/screenshots

OCR_ENABLED=true
OCR_MIN_CONFIDENCE=0.35
OCR_LANGUAGE=ch

UI_DETECTOR_ENABLED=true
UI_DETECTOR_URL=http://127.0.0.1:8790
UI_DETECTOR_TIMEOUT_MS=900
UI_DETECTOR_MIN_CONFIDENCE=0.25
UI_DETECTOR_FAILURES_TO_OPEN=3
UI_DETECTOR_CIRCUIT_OPEN_SECONDS=30

CANDIDATE_MAX_COUNT=40
CANDIDATE_CACHE_TTL_SECONDS=10
CANDIDATE_MIN_CLICK_CONFIDENCE=0.65
VISUAL_FALLBACK_MIN_CONFIDENCE=0.80
SHORTCUT_ROI_FAST_PATH=true
SIGNATURE_TEMPORAL_SAMPLE_MS=250

MEMORY_ENABLED=false
MEMORY_PATH=./runtime/memory/skills.jsonl
MEMORY_MATCH_CONFIG=./config/memory_match.json
```

兼容读取现有 `DASHSCOPE_API_KEY`，但内部统一映射成一个配置对象，禁止散落读取环境变量。

### 3.2 Python 依赖

```text
openai
pydantic>=2
rapidocr-onnxruntime
opencv-python-headless
Pillow
numpy
requests
```

视觉检测模型不要部署在 RK3566 设备上。默认实现为 PC/服务器 sidecar。可参考 OmniParser 的 interactive-region detector，但 GUIAgent 只依赖自定义 JSON HTTP 协议，不直接耦合其仓库内部 API。仓库中保留第三方许可证与来源说明。

## 4. 数据模型

在 `candidates/schemas.py` 实现：

```python
from typing import Literal
from pydantic import BaseModel, Field, model_validator

class PixelBBox(BaseModel):
    x1: int = Field(ge=0)
    y1: int = Field(ge=0)
    x2: int = Field(gt=0)
    y2: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_order(self):
        if self.x1 >= self.x2 or self.y1 >= self.y2:
            raise ValueError("invalid bbox")
        return self

    def center(self) -> tuple[int, int]:
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)

class UiCandidate(BaseModel):
    candidate_id: str
    source: Literal["ocr", "visual", "ocr+visual", "memory", "vlm_fallback"]
    kind: Literal[
        "text", "icon", "button", "menu_item", "card", "image",
        "input", "slider", "progress", "switch", "unknown"
    ]
    text: str | None = None
    bbox_px: PixelBBox
    text_bbox_px: PixelBBox | None = None
    detector_label: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    clickable_likelihood: float = Field(ge=0.0, le=1.0)
    metadata: dict = Field(default_factory=dict)

class CandidateMap(BaseModel):
    screen_version: str
    package: str
    activity: str
    page_type: str = "unknown"
    width: int
    height: int
    screenshot_path: str
    annotated_path: str
    candidates: list[UiCandidate]
    ocr_status: Literal[
        "ok", "empty", "timeout", "failed", "circuit_open", "disabled"
    ]
    detector_status: Literal[
        "ok", "empty", "timeout", "failed", "circuit_open", "disabled"
    ]
    degradation_mode: Literal[
        "none", "ocr_only", "visual_only", "no_candidates"
    ]
    provider_latency_ms: dict[str, float] = Field(default_factory=dict)
    created_at: float
```

provider 的内部返回值不要用异常或空列表混淆状态：

```python
class ProviderResult(BaseModel):
    provider: Literal["ocr", "visual"]
    status: Literal[
        "ok", "empty", "timeout", "failed", "circuit_open", "disabled"
    ]
    candidates: list[UiCandidate] = Field(default_factory=list)
    latency_ms: float
    error_code: str | None = None
```

`CandidateBuilder` 只合并本次 `ScreenshotFrame` 的 `ProviderResult`，禁止从缓存补入另一个 screen_version 的候选。

在 `vlm/schemas.py` 将动作协议改成：

```python
class NextAction(BaseModel):
    type: Literal[
        "tap_candidate", "tap_visual", "swipe", "type_text",
        "remote_key", "media_key", "wait", "back",
        "reveal_controls", "done", "ask_user"
    ]
    candidate_id: str | None = None
    target_label: str | None = None
    bbox_px: PixelBBox | None = None       # 仅 tap_visual
    direction: Literal["up", "down", "left", "right"] | None = None
    distance: float | None = Field(default=None, ge=0.05, le=0.95)
    text: str | None = None
    key: str | None = None
    wait_ms: int | None = Field(default=None, ge=100, le=3000)
    confidence: float = Field(ge=0.0, le=1.0)

class ObserveResult(BaseModel):
    page_type: Literal[
        "player", "detail", "search", "list", "grid",
        "dialog", "overlay", "unknown"
    ]
    control_bar_visible: bool | None = None
    overlay: str | None = None
    task_status: Literal["in_progress", "done", "blocked", "unknown"]
    next_action: NextAction
    target_evidence: str
    confidence: float = Field(ge=0.0, le=1.0)
```

使用 model validator 强制：

- `tap_candidate` 必须有 `candidate_id`，不得有 `bbox_px`；
- `tap_visual` 必须有 `bbox_px` 和 `target_label`；
- `type_text` 必须有 `text`；
- `swipe` 必须有方向；
- `remote_key/media_key` 必须有 key。

## 5. ScreenshotProvider

将 `vlm/screenshot.py` 和 `cmd_observe_screen.py` 中重复的 ADB 截图合并：

```python
class ScreenshotProvider(Protocol):
    def capture(self, request_id: str | None = None) -> ScreenshotFrame: ...
```

初版 `AdbScreenshotProvider` 必须显式支持 `ANDROID_SERIAL`，所有命令使用同一设备：

```text
adb -s $ANDROID_SERIAL exec-out screencap -p
```

不得在一次 action loop 内混用多个截图实现。后续可添加 MediaProjection/设备上传实现，但不改变上层接口。

整图 hash 只用于 trace 去重，不作为动态播放器的 stale 判据。`screen_signature` 和 `screen_version` 必须由 `candidates/fingerprint.py` **程序化生成**，不得要求 VLM自由输出字符串。

先定义结构化输入：

```python
class ScreenIdentity(BaseModel):
    signature_schema_version: Literal["v1"] = "v1"
    package: str
    activity: str
    page_type: str
    control_bar_visible: bool | None
    overlay: str | None
    stable_ocr_tokens: list[tuple[str, int, int]]
    candidate_layout: list[tuple[str, int, int, int, int]]
```

生成规则：字符串清洗、枚举归一化、位置量化、列表排序、canonical JSON序列化，再计算 SHA-256；同时保留可读的 debug key。VLM只允许提供 `page_type/control_bar_visible/overlay` 等 schema字段，不能提供最终 signature。

```text
debug_key = v1|package|activity|page_type|bar_state|overlay
layout_hash = sha256(canonical_json(stable_ocr_tokens, candidate_layout))[:16]
screen_signature = debug_key + "|" + layout_hash
screen_version = screen_signature + "|" + observation_timestamp_or_nonce
```

技能匹配比较 `ScreenIdentity` 子字段，不对 signature字符串计算编辑距离。`screen_signature` 用于缓存、去重、索引和调试，`screen_version` 用于一次观察的陈旧性校验。

稳定特征包括：

```text
package + activity + page_type
+ 归一化后的稳定 OCR token/位置
+ 归一化后的候选类型/位置
+ overlay/control_bar 状态
```

位置量化到 2%～5% 网格，避免检测框轻微抖动导致版本变化。

`stable_ocr_tokens` 不是 OCR 的全量输出。必须新增 `DynamicRegionMasker` 和页面类型策略：

- `player` 页面先排除视频内容 ROI，再保留顶部栏、底部控制条、菜单和弹窗中的文字；
- 字幕、弹幕、滚动通知、系统时钟、播放时间和进度百分比等动态 token 永不进入 signature；
- token 只有位于稳定交互候选/控制区内，或在相隔约 250ms 的两个可复用观察帧中保持“文本 + 量化位置”一致，才可进入 `stable_ocr_tokens`；
- 时间采样优先复用 action loop 已有的前后帧，不得为了普通点击固定增加一次截图；只有记忆写入或 stale 判定仍不确定时才主动补采样；
- 视频区域边界不确定时宁可少纳入 token，也不要把动态内容写进指纹。

同一播放器 UI 仅字幕、弹幕或进度时间变化时，`screen_signature` 必须保持一致；控制条显隐、菜单或弹窗变化时则必须改变。

## 6. 双通路候选生成

### 6.1 OCR 通路

`ocr/engine.py`：

- RapidOCR 使用进程级懒加载单例，不得每次观察重新初始化；
- 返回原始像素坐标；
- 过滤空串、低置信文本、状态栏时间等明显噪声；
- 产生 `source=ocr, kind=text` 候选；
- OCR bbox 是文字锚点，默认 `clickable_likelihood <= 0.55`，不得直接假设为完整按钮。

### 6.2 视觉 UI 检测通路

#### Phase B0：先做模型准入实验，再冻结接口

第一候选明确为 Microsoft OmniParser 的 `icon_detect_v3` interactive-region detector，部署在 PC/GPU sidecar；初版只接交互区域检测，不加载 icon caption 模型，因为图标语义由 Qwen VLM 判断。实现完整 adapter 前，先用真实中屏截图做一次有退出条件的技术 spike：

1. 收集 100～200 张爱奇艺、腾讯视频、夸克等真实截图，覆盖 player/detail/list/grid/dialog、控制条显隐、纯图标、小图标、广告和深浅主题；
2. 标注每个任务目标的 bbox、控件类型和是否纯图标；
3. 统计目标召回率、纯图标召回率、每帧候选数、p50/p95 延迟、显存/内存和部署复杂度；小图标以“预测框中心落入 GT”或 `IoU >= 0.3` 作为命中，避免只用高 IoU 错杀；
4. 初始准入线：总体目标召回率 `>= 0.90`、纯图标召回率 `>= 0.85`、目标部署硬件 p95 `<= 900ms`、候选数 p95 `<= 40`；阈值和原始结果一并版本化；
5. 未达线时不把该模型焊进主链路：先调置信阈值/输入尺寸，再对比第二 detector 或继续使用 Qwen 粗定位兜底，最后才决定默认 provider。

模型与权重必须 pin commit/revision，并记录各子组件许可证。当前工程可把 OmniParser 作为首个可验证实现，但不能在 B0 结果出来前把它写成不可替换依赖。

```python
class UiDetector(Protocol):
    def detect(self, screenshot_path: str) -> list[UiCandidate]: ...
```

`sidecar_client.py` 调用：

```http
POST /v1/detect
Content-Type: multipart/form-data
image=<png>
```

约定响应：

```json
{
  "width": 1280,
  "height": 800,
  "elements": [
    {
      "kind": "icon",
      "bbox_px": [590, 650, 670, 730],
      "label": null,
      "confidence": 0.88
    }
  ]
}
```

检测器负责提出交互区域，不要求正确描述图标语义。VLM根据截图、位置和用户目标判断它是播放、全屏还是其他图标。

### 6.3 并行执行与故障隔离

`CandidateBuilder` 是主链路必经的抽象，但 OCR、Visual UI Detector 都只是可失效的 `CandidateProvider`，任何一个 provider 都不得成为单点。`candidates/builder.py` 使用最多两个 worker 并行执行；每路单独设置 deadline、异常边界和熔断器，并且无论 provider 是空、超时还是熔断，都返回一份带状态的 `CandidateMap`，不得无限等待或复用旧候选。

初始降级矩阵写成显式代码和测试，不依赖开发者从 fallback 文案自行推断：

| OCR | Detector | `degradation_mode` | 下一步 |
|---|---|---|---|
| ok/empty | ok/empty | `none` | 合并现有候选；目标不存在时进入 no-candidate fallback |
| ok | timeout/failed/circuit_open/disabled | `ocr_only` | 有匹配文字时走 OCR anchor refinement；纯图标/无匹配文字时立即走 coarse-to-fine VLM |
| timeout/failed/circuit_open/disabled | ok | `visual_only` | 用视觉候选 + VLM 选择 |
| 两路均不可用或均无目标 | — | `no_candidates` | 全图粗区域 + 局部 VLM；低置信则安全停止 |

实现要求：

- detector 在线调用硬 deadline 初始为 900ms，并受整条命令剩余预算进一步收紧；超时是可降级事件，不是整个任务异常；
- detector 连续 3 次超时/失败后熔断 30 秒；随后 half-open 只放行一次探测，成功再关闭熔断；OCR provider 可采用同一状态机；
- sidecar 提供 `/healthz` 和模型预热状态，但 health check 不能替代真实请求 deadline；
- `empty` 与 `failed` 必须区分：空结果可能是正常页面，失败表示 provider 不可信；
- provider 状态、熔断转换、实际延迟、降级路径和 fallback 原因全部写入 trace；
- 截图本身失败是观察失败，可以停止/重试；detector 失败不是观察失败。

### 6.4 候选融合

`merger.py` 至少实现：

1. OCR中心落在 button/menu/card 视觉框中时，合并为 `ocr+visual`；
2. 高 IoU 同类视觉框去重；
3. 小 icon 位于大 card 内时两者都保留；
4. OCR-only 候选保留 `text_bbox_px`，不擅自扩大成按钮；
5. 候选按 `clickable_likelihood`、confidence 和目标相关性排序；
6. 超过 `CANDIDATE_MAX_COUNT` 时保留文字相关项、交互类项和高置信项。

### 6.5 SoM 标注

`som_renderer.py` 用 Pillow 在候选框左上角绘制短 ID，避免遮住目标中心。ID 在同一次观察内稳定，例如 `T1`、`V3`、`M2`。

VLM看到的是标注图，但执行坐标始终取原始 `UiCandidate.bbox_px`。

## 7. VLM 决策与 Grounding

### 7.1 Observe Prompt 硬约束

Prompt必须包含：

```text
你是 Android 中屏 GUI 操作观察器。截图中的 T/V/M 编号对应候选列表。
如果候选列表存在目标，必须返回 tap_candidate 并选择唯一 candidate_id；不得重新预测坐标。
文字目标优先使用 OCR+visual 候选；纯图标根据形状、位置和页面语义选择 visual 候选。
OCR 框可能只是文字，不等于完整按钮；当只有 OCR 锚点且点击区域不可靠时，进入局部定位。
播放器控制条尚未显示时返回 reveal_controls，禁止猜测隐藏控件位置。
只有候选中完全不存在目标时才允许 tap_visual。
敏感、歧义或低置信操作返回 ask_user。
每次只返回一个动作，只输出 JSON。
```

候选列表只传必要字段：`candidate_id/kind/text/detector_label/normalized_bbox/confidence`，最多 40 个。

### 7.2 局部定位兜底

实现：

1. **OCR anchor refinement**：以 OCR 框为中心扩展 ROI，让 VLM定位“文字对应的完整菜单项/按钮”，再映射回原图。
2. **No-candidate fallback**：全图 VLM只输出粗 ROI；裁剪后第二次 VLM输出局部像素 bbox。

所有 ROI 对象保存 `offset_x/offset_y/scale`，只通过确定性函数映射回原图。不得假设模型内部 resize/padding。

## 8. Harness 改造

### 8.1 ActionGuard

`validate_action(action, candidate_map, subgoal, history)` 校验：

- `tap_candidate` 的 ID 存在于当前 CandidateMap；
- CandidateMap 未超时；
- 当前页面的 UI fingerprint 与观察时相容；
- bbox 在屏幕内，宽高和面积合理；
- OCR-only 候选低于点击阈值时转 ROI refinement，不能直接点击；
- `tap_visual` 置信度至少为 `VISUAL_FALLBACK_MIN_CONFIDENCE`；
- 敏感目标必须 `ask_user`；
- 同一 screen_version、同一 candidate 连续失败后禁止再次点击；
- 任何 VLM动作都不能包含 shell、包安装、系统配置修改。

删除“屏幕底部 10% 一律敏感”的固定规则，播放器合法控件大量位于底部。敏感性由动作语义、候选文字、页面状态和用户目标共同判断。

### 8.2 Executor

新增并实现：

```python
tap_candidate(candidate_id, candidate_map)
tap_visual(bbox_px)
type_text(text)
```

点击点默认使用 bbox 中心，并预留按 kind 定制策略：

- slider/progress：根据任务参数计算比例；
- card：避开内部小 icon；
- menu_item/button/icon：使用安全中心点；
- OCR-only：只有 refinement 后才允许执行。

修复现有 `type_text` schema 与 executor 不一致问题。

### 8.3 Action Loop

```python
for step in range(max_steps):
    frame = screen_provider.capture()
    candidate_map = candidate_builder.build(frame, context)
    memory_hints = memory.match(...) if enabled else []

    decision = vlm.observe(
        annotated_path=candidate_map.annotated_path,
        candidates=candidate_map.candidates,
        goal=subgoal,
        trajectory=trajectory,
        memory_hints=memory_hints,
    )

    if decision.next_action.type == "reveal_controls":
        execute_bounded_reveal()
        continue

    if decision.next_action.type == "done":
        return verify_before_returning()

    guarded = guard.validate(decision.next_action, candidate_map, subgoal, trajectory)
    if guarded.requires_refinement:
        guarded = grounder.refine(guarded, frame, candidate_map)
    if not guarded.allowed:
        return blocked_or_failed(guarded)

    execution = executor.execute(guarded.action, candidate_map)
    after = screen_provider.capture()
    verification = verifier.verify(before=frame, after=after, expected=expected)
    trace.append(...)

    if verification == "success":
        memory.record_verified_success(...)
        return success
    recover_boundedly_or_continue()
```

计数器分开维护：`step_count`、`vlm_call_count`、`recovery_count`。删除当前互相冲突的 `max_observations` 语义。

## 9. Control Revealer

隐藏控件属于状态转换，不属于候选检测失败：

```text
判断 player 且 control_bar_visible=false
→ DPAD_CENTER → 截图验证
→ MENU → 截图验证
→ 安全中心点击 → 截图验证
```

成功条件不使用 dump，而使用：

- 底部/顶部新增多个 UI候选；
- OCR出现“倍速/清晰度/选集”等播放器文本；
- VLM确认控制条可见；
- UI区域差异显著，视频主体区域变化被屏蔽。

Reveal策略不是永久常量，必须和 Shortcut一样有生命周期。新增 `RevealStrategyRecord`：

```python
class RevealStrategyRecord(BaseModel):
    strategy_id: str
    app: str
    activity_pattern: str | None = None
    orientation: str | None = None
    actions: list[dict]
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    latency_ema_ms: float | None = None
    last_verified_at: float | None = None
    state: Literal["active", "probation", "stale"] = "active"
```

选择策略时优先考虑匹配范围、平滑成功率和历史延迟。只有 `CONTROL_BAR_NOT_REVEALED` 这类语义失败才计入策略失败；ADB断开、截图失败、VLM超时等基础设施错误不能把策略标 stale。建议连续 2 次语义失败进入 `probation`，连续 3 次或最近窗口成功率过低标记 `stale`，随后回退通用策略并允许新成功序列生成新版本。

## 10. 无 Dump 状态与验证

### 10.1 registry 状态捕获

重写 `registry.capture_state()`：

```json
{
  "pkg": "com.tencent.qqlive",
  "activity": "...",
  "page_type": "player",
  "ocr_summary": ["倍速", "清晰度"],
  "candidate_summary": {"icon": 5, "text": 2, "menu_item": 1},
  "ui_fingerprint": "..."
}
```

包名/Activity 从现有 `ping` 获取，不调用 dump。

### 10.2 动态页面稳定性

`await_stable()` 不比较完整截图。按页面类型选择 UI mask：

- player：比较控制条、顶部栏、弹窗、稳定 OCR token 和候选布局；视频主体以及其中的字幕、弹幕、滚动通知、播放时间等动态 OCR 全部忽略；
- list/grid：比较 OCR token、卡片布局和滚动停止；
- dialog/overlay：比较弹窗 ROI；
- unknown：使用候选布局 + 感知哈希组合。

### 10.3 分层验证

先本地、后 VLM：

1. 包名/Activity变化；
2. 目标 OCR出现/消失；
3. 候选布局变化；
4. 目标局部 patch 变化；
5. 选中态/弹窗/控制条检测；
6. 仍不确定才调用 VLM Verify。

“原子操作返回 ok”只能表示动作已下发，不能表示用户目标完成。

## 11. 延迟与调用预算

20秒是硬超时，不是性能目标。必须对 trace 中各阶段单独计时，并以真机 p50/p95 验收。初始目标：

| 阶段 | p50目标 | p95上限 |
|---|---:|---:|
| ADB/设备截图 | 200ms | 500ms |
| OCR与Visual Detector并行 | 400ms | 900ms |
| 单次VLM决策 | 1.5s | 3.0s |
| 原子动作与动画等待 | 500ms | 1.2s |
| 本地验证 | 250ms | 600ms |
| 必要时VLM验证 | 1.5s | 3.0s |

端到端目标：简单点击 p95 ≤ 5s；包含一次 reveal 的倍速/清晰度子目标 p95 ≤ 12s；恢复场景必须在 20s 硬超时前停止。

优化规则：

- OCR和视觉检测并行；
- 同一 ScreenshotFrame只做一次OCR/检测/VLM上传；
- reveal每一步优先用本地候选变化验证，不为每个按键固定调用VLM；
- 本地验证明确成功时跳过VLM Verify；
- 普通子目标最多4次VLM调用，只有发生一次受控恢复时才允许扩展到硬上限6次；
- 超时预算按剩余时间传给每次外部调用，禁止单次调用吃完整体预算。

指标必须拆开记录，禁止只用“模型调用次数下降”代表性能提升：

- `ocr_latency_ms`、`detector_latency_ms`、并行后的 `candidate_generation_latency_ms`，均统计 p50/p95/timeout rate；
- `detector_calls`、`detector_circuit_open_rate`、`vlm_decision_calls`、`vlm_verify_calls` 分开统计；
- `shortcut_roi_fast_path_rate`、`shortcut_full_builder_rate`、`shortcut_vlm_fallback_rate`；
- exploration、Shortcut ROI 快路径、Shortcut 全量降级三种路径分别报告端到端 p50/p95。

因此 Shortcut 的承诺是“减少全屏 detector/VLM 调用和规划成本”，不是笼统宣称零模型成本；如果 ROI 快路径未命中，它的端到端延迟可能不会明显低于通用探索。

## 12. Experience Memory

Phase 1 默认 `MEMORY_ENABLED=false`，闭环稳定后开启。

记忆保存：app、activity、page_type、intent、参数schema、UI fingerprint、前置条件、候选语义、kind、相对区域、局部视觉指纹、动作模板、后置条件、成功/失败统计。

Shortcut轨迹必须**语义优先**：能表达为 `tap_target(role/text/template)` 的步骤不得固化为 `tap_normalized`。固定坐标只允许用于经过命名和约束的稳定原语，例如 `reveal_safe_center`；即使保存坐标，也只能作为带局部视觉校验的低优先级 fallback。

同类意图必须尽量抽取为参数化技能。例如只保存一个 `set_speed`：

```json
{
  "skill_id": "tencent_player_set_speed_v1",
  "intent": "set_speed",
  "parameter_schema": {
    "speed": {"type": "enum", "values": ["0.75", "1.0", "1.25", "1.5", "2.0"]}
  },
  "trajectory_template": [
    {"type": "reveal_controls"},
    {"type": "tap_target", "role": "speed_entry"},
    {"type": "tap_target", "text_template": "{speed}倍"}
  ],
  "locator_plan": [
    "roi_text_or_patch",
    "roi_visual_detector",
    "full_candidate_builder",
    "vlm_fallback"
  ]
}
```

`match_key`比较参数兼容性，而不是要求参数值与历史样本完全相等。运行时先校验参数schema，再渲染目标文本；页面不支持该值时回到通用探索。

禁止只保存绝对坐标。回放时必须对当前截图重新定位并确认局部视觉相似度，但“重新定位”不等于每次都跑全屏 OCR + detector。高置信 Shortcut 按以下逐级 locator 执行：

1. 根据 `region_hint` 裁剪当前截图 ROI；
2. 文字目标优先做 ROI OCR，纯图标优先做局部 patch/template 校验；
3. 仍不确定时只对 ROI 调 visual detector；
4. ROI 未命中或前置状态不匹配时，才运行全屏 `CandidateBuilder`；
5. 全屏候选仍没有目标时，才进入 VLM fallback。

ROI 结果也要封装为当前 `screen_version` 下的临时候选并经过 ActionGuard，不能直接点击历史坐标。任一级定位失败只触发下一级，不得复用上次 CandidateMap；连续两次最终验证失败才把 Shortcut 标记 `stale`。

匹配权重和阈值不得硬编码在 matcher 中。放入 `config/memory_match.json`，文档里的权重只能作为初始假设。各分量定义明确为0～1：

- app/package：规范化后精确匹配；
- activity：精确匹配或显式别名映射；
- page state：对 `page_type/control_bar_visible/overlay` 做字段级加权命中；
- intent：由Agent归一化后的 intent ID精确匹配；
- params：按 parameter schema 做兼容性评分；
- OCR/layout：`stable_ocr_tokens` Jaccard与候选类型/量化位置匹配，不比较 signature字符串编辑距离；
- reliability：带先验的平滑成功率；
- recentness：按可配置半衰期衰减。

在评测阶段使用独立验证任务集调优权重和阈值，以“错误回放率优先受控、覆盖率次之”为目标，输出 precision/coverage 曲线。生产/演示默认选择高精度阈值，不直接把某组经验系数视为结论。

只允许经过 Verifier 判定 `success` 的轨迹写入；支付、发送、删除、登录、验证码、授权等任务不写入 Shortcut。

## 13. 现有文件逐项修改清单

### 必改

- `observation/screen/cmd_observe_screen.py`：删除 dump，改为 CandidateBuilder 入口。
- `observation/observation_cache.py`：改存 CandidateMap，可保留旧模块名兼容 import。
- `observation/screen/cmd_click_element.py`：内部改为 candidate_id，保留命令别名。
- `observation/vlm/schemas.py`：增加 `tap_candidate`，废弃普通路径 `bbox_normalized`。
- `observation/vlm/prompts.py`：改为候选选择协议。
- `observation/vlm/client.py`：接收标注图和候选列表。
- `observation/harness/action_guard.py`：基于 CandidateMap 校验。
- `observation/harness/action_loop.py`：串起 CandidateBuilder，修复计数器。
- `registry.py`：移除 `ws_dump` 状态捕获。
- `observation/state/resolver.py`：改为截图、候选和 VLM/本地分类器。

### 后续迁移

- `aiqiyi/`、`Tencent/`、`quark/` 中依赖节点搜索的命令，逐个迁移为媒体键、DPAD、candidate_id 或记忆技能；
- 迁移完成后删除 Python 中所有 dump 调用；
- 最终停止注册 Android WS `dump` 操作，清理只为 dump 服务的数据模型。

## 14. Trace

每一步写一个 JSONL 事件，至少包含：任务ID、步骤、目标、前后截图路径、标注图、screen_version、两路感知状态、候选数、VLM原始输出、决策、Guard、执行、验证、各阶段时延和模型usage。

API key、截图 base64、用户密码和验证码不得写 trace。

## 15. 测试

### 15.1 单元测试

- OCR候选生成、噪声过滤和中文文本；
- visual sidecar超时/空结果/非法框；
- detector超时后 OCR-only 降级不阻塞，纯图标自动进入 coarse-to-fine VLM；
- detector连续失败触发熔断、half-open成功后恢复；
- 两路都不可用时 CandidateBuilder仍返回 `no_candidates` 而不是抛出未处理异常；
- OCR框与视觉按钮框融合；
- 图标嵌套卡片不被误合并；
- SoM编号稳定且不修改原始坐标；
- `tap_candidate` 缺 ID 被拒绝；
- stale candidate被拒绝；
- OCR-only低置信候选进入 refinement；
- `tap_visual`低置信被拒绝；
- 动态视频帧变化时 UI fingerprint保持稳定；
- 仅字幕、弹幕、滚动通知或播放时间变化时 `stable_ocr_tokens` 与 signature不变；控制条/菜单变化时 signature改变；
- `reveal_controls` 不调用 dump；
- `done` 仍执行验证；
- `type_text` 可执行且敏感文本被阻断；
- 步骤、VLM和恢复预算分别生效；
- memory只有 verified success 才写入。
- signature由canonical builder确定性生成，同一结构化输入字节级一致；
- matcher不使用signature字符串编辑距离；
- 参数化 `set_speed` 能用一个技能覆盖多个合法倍率；
- 轨迹提炼器把可语义化的固定坐标改写为 `tap_target`；
- Reveal语义失败触发统计，基础设施失败不触发 stale；
- 连续Reveal失败能够进入probation/stale并选择其他策略；
- 普通路径VLM调用不超过4次，恢复路径不超过6次。
- Shortcut ROI命中时不调用全屏 detector，ROI失败时能升级到 full builder/VLM；

### 15.2 固定截图评测集

建立 `tests/fixtures/screens/manifest.jsonl`，每条包含 screenshot、app/page_type、场景类别、用户目标、ground-truth target bbox、expected candidate 和 expected action。

统计候选召回率、纯图标召回率、VLM候选选择准确率、点击命中率、错误点击率、候选数分布和 detector p50/p95。

### 15.3 真实设备冒烟测试

1. 文字：选择 `1.5倍`；
2. 图标：播放/暂停、全屏；
3. 混合：打开清晰度并选择某档；
4. 隐藏：控制条隐藏后设置倍速；
5. 卡片：搜索并进入指定内容；
6. 动态：播放中 screen_version 不被每帧击穿；
7. 安全：登录/订阅/付款入口不会自动确认；
8. 恢复：错误首选候选能够被排除并重新观察。

每个用例连续运行 10 次，记录任务成功率、平均动作数、detector调用数、VLM决策/验证调用数、候选生成时延、端到端时延、候选召回率和错误点击数。Shortcut ROI快路径、全量候选路径和通用探索必须分组报告。

### 15.4 Memory匹配调优

建立带正负技能对的验证集，至少包含同App同页面、同App不同overlay、App改版、相似文字不同意图和同意图不同参数。对候选权重和阈值做网格/随机搜索，报告错误回放率、匹配precision、coverage、平均节省VLM调用数；配置版本与评测结果一起保存。

## 16. 实施顺序

1. **Phase A：无 dump 观察底座**：ScreenshotProvider、OCR单例、CandidateMap、缓存、UI fingerprint、重写 observe/state。
2. **Phase B0：Detector准入 spike**：真实中屏标注集、OmniParser `icon_detect_v3` 基线、召回/延迟/资源/许可证报告和 go/no-go 决策。
3. **Phase B：视觉候选与 SoM**：在 B0 通过后实现默认 sidecar adapter、provider deadline/熔断/降级矩阵、builder、merger、renderer和固定截图测试。
4. **Phase C：VLM候选选择与 Harness**：schema/prompt/client/action_loop/guard/executor、两类 refinement。
5. **Phase D：验证、隐藏控件和恢复**：DynamicRegionMasker、稳定 OCR token、本地验证、VLM验证、reveal、排除失败候选。
6. **Phase E：旧命令迁移与 dump 删除**：迁移 App 节点命令，清除活动 dump 调用和协议注册。
7. **Phase F：经验记忆**：确定性signature、参数化Shortcut、ROI locator plan、语义轨迹、匹配配置、回放、失效与权重/阈值调优。

每个 Phase 单独提交，不进行与本任务无关的语音、UI或构建系统重构。

## 17. 完成定义

全部满足才算完成：

- 文字和纯图标场景都能通过候选 ID 操作；
- OCR和视觉检测任一路失败时系统可降级；
- detector超时/熔断不会阻塞主链路，且降级矩阵有自动化测试；
- 正常路径不执行 VLM 自由坐标；
- 隐藏控件先 reveal 后定位；
- 动态视频不因整图变化导致 candidate立即过期；
- 所有动作经过 Harness，且有后置验证；
- 无敏感不可逆操作被自动执行；
- 现有 `vlm_execute`、App命令名和 HTTP接口保持兼容；
- 最终运行链路中不存在 UI dump 调用；
- 单元测试、固定截图评测和真实设备冒烟测试均通过；
- README补充视觉检测 sidecar、环境变量、第三方许可和故障排查说明。
- signature由程序确定性生成，VLM不能直接提供最终值；
- Reveal策略和Shortcut都具备统计、probation、stale和版本更新机制；
- 一个参数化技能能够覆盖同意图的多个合法参数值；
- 播放器动态 OCR不进入稳定 signature，字幕/弹幕变化测试通过；
- Shortcut报告 ROI快路径率，并分别统计候选生成、detector、VLM和端到端成本；
- 真机报告包含各阶段p50/p95和端到端延迟；
- Phase B0已给出默认 detector 的真实设备准入报告和可复现的模型 revision。

## 18. 禁止事项

- 不得重新引入 dump 作为 OCR或VLM失败时的兜底；
- 不得将 OCR文字框中心无条件视为按钮中心；
- 不得让 VLM同时规划并执行多步动作；
- 不得依据 VLM自报 confidence 单独决定点击；
- 不得用全屏截图 hash 判断播放中页面稳定；
- 不得在检测器或 VLM异常时继续使用未验证旧坐标；
- 不得为了快速通过测试硬编码单个 App 的绝对坐标到通用模块；
- 不得绕过 Harness 直接调用 `send({"op": "tap"})`。
- 不得由VLM自由生成screen_signature；
- 不得把匹配权重和阈值散落硬编码；
- 不得为每个倍率值复制一份结构相同的Shortcut；
- 不得把可语义化的技能步骤固化为裸坐标。
