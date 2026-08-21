# Step 3A — 真实中屏截图静态 Harness 回放报告

> 边界声明：仅做**静态安全回放**（Action Guard 校验），不接真机 / ADB / VLM，
> 不伪造点击后的下一页，不计算端到端或真机点击成功率。

## 1. 纳入截图

- 真实中屏截图：**103** 张（1280×800）
- 成功生成 CandidateMap：**103** 张
- 无候选（skipped/unavailable）：**0** 张
- OCR 可用截图：**0** 张（无 OCR 后端，降级 unavailable）

## 2. 真实 CandidateMap 上的 Guard 注入阻断结果

| 场景 | 数量 | 匹配 |
|---|---|---|
| bbox_bottom_out | 103 | 103/103 |
| bbox_negative | 103 | 103/103 |
| bbox_right_out | 103 | 103/103 |
| inject_delete_risk | 103 | 103/103 |
| inject_payment_risk | 103 | 103/103 |
| low_clickable_likelihood | 103 | 103/103 |
| low_confidence | 103 | 103/103 |
| nonexistent_candidate | 103 | 103/103 |
| normal_tap | 103 | 103/103 |
| ocr_only_no_refine | 103 | 103/103 |
| previously_failed | 103 | 103/103 |
| stale_candidate_map | 103 | 103/103 |

- 全部断言通过：**True** （1236/1236）

## 3. 关键结论

- 所有 reject/refine 场景：`executor_calls == 0`，`error_code` / `risk_level` / `requires_refinement` 与预期一致。
- 校验对象为真实截图生成的 `CandidateMap`（故障注入到其副本），未脱离截图重建 map。
- 负坐标 bbox 由 `BBox` 类型层在构造时拒绝，未进入 Guard。

## 4. 红框标注 / recall

- 无验证红框标注集，不报告 recall。

## 5. 明确不报告

- 真机点击成功率、真实端到端任务成功率、Reveal 成功率、VLM 决策效果、
无真实计时器的延迟性能。
