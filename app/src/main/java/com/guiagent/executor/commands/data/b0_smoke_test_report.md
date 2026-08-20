# Phase B0: Visual Detector 准入实验报告

## 实验概述

**目标**: 评估 Visual Detector 是否满足项目需求

**Detector**: OpenCVDetector (基于边缘检测 + 轮廓分析)

**数据集**:
- 总截图数：103 张
- B0 最小标注集：30 张（自动标注，待人工审核）

---

## 定量结果

### 1. 延迟测试

| 指标 | 结果 | 目标 | 状态 |
|------|------|------|------|
| p50 延迟 | 17ms | - | - |
| p95 延迟 | 22ms | <= 900ms | ✅ PASS |

### 2. 候选数测试

| 指标 | 结果 | 目标 | 状态 |
|------|------|------|------|
| p50 候选数 | 15 | - | - |
| p95 候选数 | 30 | <= 40 | ✅ PASS |

### 3. 召回率测试

**状态**:  待完成（需要人工标注 ground truth）

当前 auto-annotations 由 OpenCVDetector 自动生成，不能作为 ground truth。

---

## 定性观察

### 检测效果

**优势**:
- ✅ 延迟极低（22ms p95）
- ✅ 候选数合理（30 p95）
- ✅ 能检测规则形状的按钮/卡片
- ✅ 对高对比度边缘敏感

**劣势**:
-  无法区分元素类型（icon vs button vs card）
- ❌ 对低对比度元素不敏感
-  无法识别文字内容
-  对圆角矩形检测不稳定
- ❌ 容易检测到非交互区域（如装饰边框）

### 典型场景

| 场景 | 检测效果 |
|------|----------|
| 播放器控制条（矩形按钮） | 良好 |
| 网格布局卡片 | 良好 |
| 纯图标（小尺寸） | 一般 |
| 文字按钮（无边框） | 差 |
| 浮层菜单 | 一般 |

---

## 结论

### 当前状态

OpenCVDetector 通过延迟和候选数门槛，但：
- **召回率未知**（需要 ground truth 标注）
- **分类能力有限**（无法准确区分 icon/button/card）
- **规则基于形状**（对自绘控件效果有限）

### 建议

**选项 A**: 继续使用 OpenCVDetector + 人工标注
- 标注 30 张截图的 ground truth
- 计算实际召回率
- 若召回率 >= 90%，则通过 B0

**选项 B**: 升级到更高级 Detector
- OmniParser icon_detect_v3（需要 GPU 服务器）
- YOLO UI 检测模型（需要训练数据）
- 商业 API（如 AWS Rekognition）

**选项 C**: 混合方案
- OpenCVDetector 作为 fallback
- 主要依赖 observe_screen() 的 OCR 候选
- VLM 做最终候选选择

---

## 下一步

1. **人工标注 30 张截图**（预计 2-4 小时）
2. **计算召回率**
3. **根据结果决定**:
   - 通过 → 进入 Phase B (Candidate Builder)
   - 未通过 → 更换/升级 Detector

---

**报告日期**: 2026-08-20
**实验者**: GUIAgent Team
**Detector 版本**: OpenCVDetector v1.0.0
