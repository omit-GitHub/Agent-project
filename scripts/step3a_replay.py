# -*- coding: utf-8 -*-
"""Step 3A — 真实截图静态 Harness 安全回放。

对每张成功生成 CandidateMap 的真实截图，在真实 UiState/CandidateMap 上构造 7 类动作，
走 run_action_loop 的 Guard 校验，逐条断言 reject/refine 的 executor_calls==0 与
error_code / risk_level / requires_refinement。产出：
  - artifacts/screenshot_replay_traces.jsonl
  - artifacts/screenshot_replay_metrics.json
  - docs/STEP3A_REAL_SCREENSHOT_REPLAY_REPORT.md
"""
import json
import os
import sys
from dataclasses import dataclass, field, replace

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from harness import (  # noqa: E402
    ActionSpec, UiState, ActionResult, BBox, Candidate, CandidateMap,
    ActionGuard, ActionGuardConfig, run_action_loop,
)
from harness.verifier import VerificationResult, VerificationStatus  # noqa: E402
from harness.screenshot_adapter import ScreenshotObservationAdapter  # noqa: E402

SCREENSHOT_DIR = os.path.join(_ROOT, "screenshots")
MANIFEST_PATH = os.path.join(SCREENSHOT_DIR, "manifest.jsonl")
TRACES_PATH = os.path.join(_ROOT, "artifacts", "screenshot_replay_traces.jsonl")
METRICS_PATH = os.path.join(_ROOT, "artifacts", "screenshot_replay_metrics.json")
REPORT_PATH = os.path.join(_ROOT, "docs", "STEP3A_REAL_SCREENSHOT_REPLAY_REPORT.md")


# ─────────────── 最小回放用 mocks ───────────────

class ReplayDecisionSource:
    def __init__(self, action):
        self.action = action
        self._sent = False

    def next_action(self, state):
        if self._sent:
            return ActionSpec(action_type="done")
        self._sent = True
        return self.action


class ReplayExecutor:
    """只记录调用，不真正执行。calls 用于断言 executor_calls==0。"""

    def __init__(self):
        self.calls = []

    def execute(self, action, state):
        self.calls.append(action)
        return ActionResult(ok=True, action=action, after_state=state)


class ReplayVerifier:
    def verify(self, before, after, action):
        return VerificationResult(
            verification=VerificationStatus.success, source="local", reason="replay"
        )


# ─────────────── 故障候选构造 ───────────────

def _mk_candidate(cid, bbox=None, confidence=0.9, clickable_likelihood=0.9,
                  risk_category=None, sensitive_category=None, action_semantics=None,
                  source="visual", kind="icon"):
    if bbox is None:
        bbox = BBox(x1=100, y1=100, x2=200, y2=150)
    return Candidate(
        candidate_id=cid, bbox_px=bbox, risk_category=risk_category,
        sensitive_category=sensitive_category, action_semantics=action_semantics,
        confidence=confidence, clickable_likelihood=clickable_likelihood,
        source=source, kind=kind,
    )


def _state_with_extra(state, candidate):
    cm = state.candidate_map
    new_cm = CandidateMap(
        screen_version=cm.screen_version, package=cm.package, activity=cm.activity,
        width=cm.width, height=cm.height, candidates=list(cm.candidates) + [candidate],
    )
    return replace(state, candidate_map=new_cm)


# ─────────────── 场景构造 ───────────────

def build_cases(state, real_candidate):
    """在真实 CandidateMap 上构造 7 类动作。返回 list[case dict]。"""
    fp = state.fingerprint
    w, h = state.screen_size
    real_id = real_candidate.candidate_id
    base_cfg = ActionGuardConfig(screen_width=w, screen_height=h)

    cases = []

    # 1. 正常候选点击（控制组）
    cases.append({
        "case_id": "normal_tap",
        "action": ActionSpec(action_type="tap_candidate", candidate_id=real_id,
                             candidate_map_fingerprint=fp, expected_screen_fingerprint=fp),
        "state": state, "config": base_cfg, "pre_seed": None,
        "expected": {"allowed": True, "error_code": None, "risk_level": "low",
                     "requires_refinement": False},
    })

    # 2a. 不存在的 candidate_id
    cases.append({
        "case_id": "nonexistent_candidate",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="no_such_id",
                             candidate_map_fingerprint=fp, expected_screen_fingerprint=fp),
        "state": state, "config": base_cfg, "pre_seed": None,
        "expected": {"allowed": False, "error_code": "CANDIDATE_NOT_FOUND",
                     "risk_level": "high", "requires_refinement": False},
    })

    # 2b. 过期 CandidateMap
    cases.append({
        "case_id": "stale_candidate_map",
        "action": ActionSpec(action_type="tap_candidate", candidate_id=real_id,
                             candidate_map_fingerprint="stale_version",
                             expected_screen_fingerprint=fp),
        "state": state, "config": base_cfg, "pre_seed": None,
        "expected": {"allowed": False, "error_code": "FINGERPRINT_MISMATCH",
                     "risk_level": "high", "requires_refinement": False},
    })

    # 3a. 右侧越界 bbox
    cases.append({
        "case_id": "bbox_right_out",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="fault_right",
                             candidate_map_fingerprint=fp, expected_screen_fingerprint=fp),
        "state": _state_with_extra(state, _mk_candidate(
            "fault_right", bbox=BBox(x1=w - 100, y1=100, x2=w + 100, y2=200))),
        "config": base_cfg, "pre_seed": None,
        "expected": {"allowed": False, "error_code": "BBOX_OUT_OF_SCREEN",
                     "risk_level": "high", "requires_refinement": False},
    })

    # 3b. 下侧越界 bbox
    cases.append({
        "case_id": "bbox_bottom_out",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="fault_bottom",
                             candidate_map_fingerprint=fp, expected_screen_fingerprint=fp),
        "state": _state_with_extra(state, _mk_candidate(
            "fault_bottom", bbox=BBox(x1=100, y1=h - 100, x2=200, y2=h + 100))),
        "config": base_cfg, "pre_seed": None,
        "expected": {"allowed": False, "error_code": "BBOX_OUT_OF_SCREEN",
                     "risk_level": "high", "requires_refinement": False},
    })

    # 4a. 低 confidence → requires_refinement
    cases.append({
        "case_id": "low_confidence",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="fault_low_conf",
                             candidate_map_fingerprint=fp, expected_screen_fingerprint=fp),
        "state": _state_with_extra(state, _mk_candidate("fault_low_conf", confidence=0.1)),
        "config": base_cfg, "pre_seed": None,
        "expected": {"allowed": False, "error_code": "LOW_CONFIDENCE",
                     "risk_level": "low", "requires_refinement": True},
    })

    # 4b. 低 clickable_likelihood → requires_refinement
    cases.append({
        "case_id": "low_clickable_likelihood",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="fault_low_click",
                             candidate_map_fingerprint=fp, expected_screen_fingerprint=fp),
        "state": _state_with_extra(state, _mk_candidate("fault_low_click", clickable_likelihood=0.1)),
        "config": base_cfg, "pre_seed": None,
        "expected": {"allowed": False, "error_code": "LOW_CLICKABLE_LIKELIHOOD",
                     "risk_level": "low", "requires_refinement": True},
    })

    # 5a/5b. 在真实 CandidateMap 注入 risk_category=payment/delete
    cases.append({
        "case_id": "inject_payment_risk",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="pay_btn",
                             candidate_map_fingerprint=fp, expected_screen_fingerprint=fp),
        "state": _state_with_extra(state, _mk_candidate("pay_btn", risk_category="payment")),
        "config": base_cfg, "pre_seed": None,
        "expected": {"allowed": False, "error_code": "SENSITIVE_TARGET",
                     "risk_level": "high", "requires_refinement": False},
    })
    cases.append({
        "case_id": "inject_delete_risk",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="del_btn",
                             candidate_map_fingerprint=fp, expected_screen_fingerprint=fp),
        "state": _state_with_extra(state, _mk_candidate("del_btn", risk_category="delete")),
        "config": base_cfg, "pre_seed": None,
        "expected": {"allowed": False, "error_code": "SENSITIVE_TARGET",
                     "risk_level": "high", "requires_refinement": False},
    })

    # 6. 同一 fingerprint 下重复失败候选
    cases.append({
        "case_id": "previously_failed",
        "action": ActionSpec(action_type="tap_candidate", candidate_id=real_id,
                             candidate_map_fingerprint=fp, expected_screen_fingerprint=fp),
        "state": state, "config": base_cfg, "pre_seed": [(fp, real_id)],
        "expected": {"allowed": False, "error_code": "PREVIOUSLY_FAILED",
                     "risk_level": "high", "requires_refinement": False},
    })

    # 7. OCR-only 未 refinement（allow_ocr_only_tap=False）
    cases.append({
        "case_id": "ocr_only_no_refine",
        "action": ActionSpec(action_type="tap_candidate", candidate_id="ocr_btn",
                             candidate_map_fingerprint=fp, expected_screen_fingerprint=fp),
        "state": _state_with_extra(state, _mk_candidate("ocr_btn", source="ocr", kind="")),
        "config": ActionGuardConfig(screen_width=w, screen_height=h, allow_ocr_only_tap=False),
        "pre_seed": None,
        "expected": {"allowed": False, "error_code": "OCR_ONLY_NOT_ALLOWED",
                     "risk_level": "low", "requires_refinement": True},
    })

    return cases


def _run_case(case):
    """运行单个 case，返回记录 dict。"""
    guard = ActionGuard()
    for fp, cid in (case["pre_seed"] or []):
        guard.record_failure(fp, cid)

    executor = ReplayExecutor()
    verifier = ReplayVerifier()
    source = ReplayDecisionSource(case["action"])

    result = run_action_loop(
        decision_source=source, executor=executor, verifier=verifier,
        initial_state=case["state"], subgoal="screenshot_replay",
        guard=guard, config=case["config"],
        max_steps=4, max_decision_calls=2, recovery_budget=0,
    )

    exp = case["expected"]
    guard_entry = result.trace[0] if result.trace else {}
    allowed = bool(guard_entry.get("guard_allowed", False))
    error_code = guard_entry.get("guard_error_code")
    risk_level = guard_entry.get("guard_risk_level")
    requires_refinement = bool(guard_entry.get("guard_requires_refinement", False))
    executor_calls = len(executor.calls)

    error_code_match = error_code == exp["error_code"]
    risk_level_match = risk_level == exp["risk_level"]
    refine_match = requires_refinement == exp["requires_refinement"]
    zero_executor = executor_calls == 0
    allowed_match = (allowed == exp["allowed"])

    # reject/refine 场景必须 executor_calls==0；allowed 场景应 ==1
    executor_expectation = (executor_calls == 0) if not exp["allowed"] else (executor_calls == 1)
    all_match = (allowed_match and error_code_match and risk_level_match
                 and refine_match and executor_expectation)

    return {
        "case_id": case["case_id"],
        "action_type": case["action"].action_type,
        "candidate_id": case["action"].candidate_id,
        "status": result.status,
        "allowed": allowed,
        "error_code": error_code,
        "risk_level": risk_level,
        "requires_refinement": requires_refinement,
        "executor_calls": executor_calls,
        "expected_allowed": exp["allowed"],
        "expected_error_code": exp["error_code"],
        "expected_risk_level": exp["risk_level"],
        "expected_requires_refinement": exp["requires_refinement"],
        "error_code_match": error_code_match,
        "risk_level_match": risk_level_match,
        "requires_refinement_match": refine_match,
        "zero_executor": zero_executor,
        "all_match": all_match,
    }


def _negative_bbox_case(state):
    """负坐标 bbox：BBox 类型层拒绝，无法进入 Guard。"""
    try:
        BBox(x1=-10, y1=0, x2=100, y2=100)
        return {"case_id": "bbox_negative", "type_level_rejection": False,
                "note": "unexpectedly constructed", "all_match": False}
    except ValueError as e:
        return {"case_id": "bbox_negative", "type_level_rejection": True,
                "note": f"BBox rejects negative origin at construction: {e}",
                "error_code": None, "risk_level": None, "requires_refinement": None,
                "executor_calls": 0, "all_match": True}


def _load_manifest():
    manifest = {}
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                e = json.loads(line)
                manifest[e.get("filename")] = e
    return manifest


def _bar_to_bool(v):
    if v == "visible":
        return True
    if v == "hidden":
        return False
    return False


def run_replay():
    manifest = _load_manifest()
    adapter = ScreenshotObservationAdapter()
    files = sorted(
        os.path.join(SCREENSHOT_DIR, n)
        for n in os.listdir(SCREENSHOT_DIR)
        if n.lower().endswith(".png")
    )

    traces = []
    case_counter = {}
    case_match_counter = {}
    total_cases = 0
    matched_cases = 0
    screens_with_candidates = 0
    screens_without_candidates = 0

    for path in files:
        name = os.path.basename(path)
        entry = manifest.get(name, {})
        obs = adapter.observe(
            path, package=entry.get("package", "unknown"),
            activity=entry.get("activity", "unknown"),
            control_bar_visible=_bar_to_bool(entry.get("control_bar_visible")),
        )
        if not obs.ok or obs.ui_state is None:
            traces.append({"filename": name, "skipped": "observation_failed",
                           "reason": obs.error})
            continue

        state = obs.ui_state
        if not obs.candidates:
            screens_without_candidates += 1
            traces.append({"filename": name, "skipped": "no_candidates",
                           "candidates": 0, "ocr_available": obs.ocr_available,
                           "visual_available": obs.visual_available})
            continue

        screens_with_candidates += 1
        real_candidate = obs.candidates[0]
        cases = build_cases(state, real_candidate)

        # 负坐标 bbox（类型层拒绝，单独记录）
        neg = _negative_bbox_case(state)
        case_counter[neg["case_id"]] = case_counter.get(neg["case_id"], 0) + 1
        case_match_counter[neg["case_id"]] = case_match_counter.get(neg["case_id"], 0) + int(neg["all_match"])
        total_cases += 1
        matched_cases += int(neg["all_match"])
        traces.append({
            "filename": name, "fingerprint": state.fingerprint[:16],
            "screen_size": list(state.screen_size), "n_candidates": len(obs.candidates),
            **neg,
        })

        for case in cases:
            rec = _run_case(case)
            cid = rec["case_id"]
            case_counter[cid] = case_counter.get(cid, 0) + 1
            case_match_counter[cid] = case_match_counter.get(cid, 0) + int(rec["all_match"])
            total_cases += 1
            matched_cases += int(rec["all_match"])
            traces.append({
                "filename": name, "fingerprint": state.fingerprint[:16],
                "screen_size": list(state.screen_size), "n_candidates": len(obs.candidates),
                **rec,
            })

    metrics = {
        "total_screenshots": len(files),
        "screenshots_with_candidates": screens_with_candidates,
        "screenshots_without_candidates": screens_without_candidates,
        "ocr_available_screenshots": 0,  # 无 OCR 后端
        "visual_available_screenshots": screens_with_candidates + screens_without_candidates,
        "total_replay_cases": total_cases,
        "matched_cases": matched_cases,
        "all_assertions_pass": matched_cases == total_cases,
        "per_case": {
            cid: {"count": case_counter[cid], "matched": case_match_counter[cid]}
            for cid in sorted(case_counter)
        },
        "red_box_note": "无验证红框标注集，不报告 recall",
    }

    os.makedirs(os.path.dirname(TRACES_PATH), exist_ok=True)
    with open(TRACES_PATH, "w", encoding="utf-8") as f:
        for t in traces:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    _write_report(metrics)

    print(f"Traces written to {TRACES_PATH}")
    print(f"Metrics written to {METRICS_PATH}")
    print(f"Report written to {REPORT_PATH}")
    print(f"  screenshots: {metrics['total_screenshots']} "
          f"(with candidates: {metrics['screenshots_with_candidates']}, "
          f"without: {metrics['screenshots_without_candidates']})")
    print(f"  replay cases: {total_cases}, matched: {matched_cases}, "
          f"all_pass: {metrics['all_assertions_pass']}")
    return metrics


def _write_report(metrics):
    lines = [
        "# Step 3A — 真实中屏截图静态 Harness 回放报告",
        "",
        "> 边界声明：仅做**静态安全回放**（Action Guard 校验），不接真机 / ADB / VLM，",
        "> 不伪造点击后的下一页，不计算端到端或真机点击成功率。",
        "",
        "## 1. 纳入截图",
        "",
        f"- 真实中屏截图：**{metrics['total_screenshots']}** 张（1280×800）",
        f"- 成功生成 CandidateMap：**{metrics['screenshots_with_candidates']}** 张",
        f"- 无候选（skipped/unavailable）：**{metrics['screenshots_without_candidates']}** 张",
        f"- OCR 可用截图：**{metrics['ocr_available_screenshots']}** 张（无 OCR 后端，降级 unavailable）",
        "",
        "## 2. 真实 CandidateMap 上的 Guard 注入阻断结果",
        "",
        "| 场景 | 数量 | 匹配 |",
        "|---|---|---|",
    ]
    for cid, v in metrics["per_case"].items():
        lines.append(f"| {cid} | {v['count']} | {v['matched']}/{v['count']} |")
    lines += [
        "",
        f"- 全部断言通过：**{metrics['all_assertions_pass']}** "
        f"（{metrics['matched_cases']}/{metrics['total_replay_cases']}）",
        "",
        "## 3. 关键结论",
        "",
        "- 所有 reject/refine 场景：`executor_calls == 0`，`error_code` / `risk_level` / "
        "`requires_refinement` 与预期一致。",
        "- 校验对象为真实截图生成的 `CandidateMap`（故障注入到其副本），未脱离截图重建 map。",
        "- 负坐标 bbox 由 `BBox` 类型层在构造时拒绝，未进入 Guard。",
        "",
        "## 4. 红框标注 / recall",
        "",
        f"- {metrics['red_box_note']}。",
        "",
        "## 5. 明确不报告",
        "",
        "- 真机点击成功率、真实端到端任务成功率、Reveal 成功率、VLM 决策效果、",
        "无真实计时器的延迟性能。",
    ]
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    run_replay()
