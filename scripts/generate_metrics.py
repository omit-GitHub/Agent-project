# -*- coding: utf-8 -*-
"""Harness B1 Metrics — 运行所有测试，生成 metrics.json + metrics.csv。

指标来自实际运行结果，非手工填写。

用法：
  cd harness-framework
  python scripts/generate_metrics.py

输出：
  metrics.json — 汇总指标
  metrics.csv — 每行一个测试用例
"""
import csv
import io
import json
import os
import re
import subprocess
import sys
import time
import unittest


_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
_SRC_ROOT = os.path.join(_PROJECT_ROOT, "src")

# 确保 Windows 控制台能输出 UTF-8
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 确保路径正确
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ─────────────── 测试收集 ───────────────

TEST_SUITES = [
    "tests.test_smoke",
    "tests.test_action_guard_injection",
    "tests.test_verifier_four_state",
    "tests.test_control_revealer_state_machine",
    "tests.test_guard_declarative_registry",
    "tests.test_reveal_plan_regression",
]


def _iter_tests(suite):
    """递归展开 TestSuite，产出所有 TestCase。"""
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_tests(item)
        else:
            yield item


def run_all_tests():
    """运行所有测试，返回结构化结果。"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    for suite_name in TEST_SUITES:
        try:
            suite.addTests(loader.loadTestsFromName(suite_name))
        except Exception as e:
            print(f"[WARN] 无法加载 {suite_name}: {e}")

    # 使用 TextTestRunner 运行并捕获输出
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)
    start_time = time.time()
    result = runner.run(suite)
    duration_ms = (time.time() - start_time) * 1000

    # 解析每个测试的结果
    test_results = []

    # 收集失败和错误的测试 ID
    failure_ids = {str(test) for test, _ in result.failures}
    error_ids = {str(test) for test, _ in result.errors}

    # 遍历所有测试
    for test_suite_obj in [loader.loadTestsFromName(s) for s in TEST_SUITES]:
        for test in _iter_tests(test_suite_obj):
            test_id = str(test)
            status = "ok"
            tb = ""
            if test_id in failure_ids:
                status = "fail"
                for t, traceback in result.failures:
                    if str(t) == test_id:
                        tb = traceback.strip()
                        break
            elif test_id in error_ids:
                status = "error"
                for t, traceback in result.errors:
                    if str(t) == test_id:
                        tb = traceback.strip()
                        break

            test_results.append({
                "test_id": test_id,
                "suite": _extract_suite(test_id),
                "test_name": _extract_test_name(test_id),
                "status": status,
                "traceback": tb,
            })

    # 成功的测试 = 总数 - 失败 - 错误
    total = result.testsRun
    failed = len(result.failures)
    errors = len(result.errors)
    passed = total - failed - errors

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "duration_ms": round(duration_ms, 2),
        "tests": test_results,
    }


def _extract_suite(test_id: str) -> str:
    """从 test_id 提取 suite 名。"""
    # 格式: "test_name (tests.module.ClassName.method) ... ok"
    match = re.search(r'\((.+?)\)', test_id)
    if match:
        full_path = match.group(1)
        parts = full_path.split(".")
        # 格式: tests.test_xxx.ClassName.method_name
        # parts[1] 是测试模块名 (test_xxx)
        if len(parts) >= 2 and parts[1].startswith("test_"):
            return parts[1]
        return parts[0]
    return "unknown"


def _extract_test_name(test_id: str) -> str:
    """从 test_id 提取测试方法名。"""
    # 格式: "test_name (tests.module.ClassName.method) ... ok"
    # 第一个空格前的就是方法名
    match = re.match(r'(\S+)', test_id)
    if match:
        return match.group(1)
    return test_id


# ─────────────── 安全断言验证 ───────────────

def verify_safety_assertions(test_results):
    """验证关键安全断言。"""
    assertions = {}

    # 1. 所有 guard rejection 测试的 executor_calls == 0
    guard_test = [t for t in test_results
                  if t["test_name"] == "test_60_all_rejections_zero_calls"]
    assertions["guard_rejection_executor_calls_zero"] = (
        len(guard_test) > 0 and guard_test[0]["status"] == "ok"
    )

    # 2. unknown 不得导致 ok=True
    unknown_test = [t for t in test_results
                    if t["test_name"] == "test_17_unknown_in_action_loop_not_ok"]
    assertions["unknown_never_leads_to_success"] = (
        len(unknown_test) > 0 and unknown_test[0]["status"] == "ok"
    )

    # 3. expected_package 无转移 → 不 success
    no_transition_test = [t for t in test_results
                         if t["test_name"] == "test_08_expected_package_no_transition"]
    assertions["expected_package_requires_transition"] = (
        len(no_transition_test) > 0 and no_transition_test[0]["status"] == "ok"
    )

    # 4. reveal 不接受 raw dict
    no_raw_dict_test = [t for t in test_results
                        if t["test_name"] == "test_26_no_reveal_method"]
    assertions["revealer_rejects_raw_dict"] = (
        len(no_raw_dict_test) > 0 and no_raw_dict_test[0]["status"] == "ok"
    )

    # 5. stale 策略产生新版本
    version_test = [t for t in test_results
                    if t["test_name"] == "test_17_new_version_preserves_old_history"]
    assertions["stale_creates_new_version"] = (
        len(version_test) > 0 and version_test[0]["status"] == "ok"
    )

    return assertions


# ─────────────── 按 suite 统计 ───────────────

def compute_by_suite(test_results):
    """按 suite 统计测试结果。"""
    by_suite = {}
    for t in test_results:
        suite = t["suite"]
        if suite not in by_suite:
            by_suite[suite] = {"total": 0, "passed": 0, "failed": 0, "errors": 0}
        by_suite[suite]["total"] += 1
        if t["status"] == "ok":
            by_suite[suite]["passed"] += 1
        elif t["status"] == "fail":
            by_suite[suite]["failed"] += 1
        elif t["status"] == "error":
            by_suite[suite]["errors"] += 1
    return by_suite


# ─────────────── 输出 ───────────────

def write_metrics_json(data, path):
    """写入 metrics.json。"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[OK] 已写入 {path}")


def write_metrics_csv(tests, path):
    """写入 metrics.csv。"""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["suite", "test_name", "test_id", "status"])
        for t in tests:
            writer.writerow([t["suite"], t["test_name"], t["test_id"], t["status"]])
    print(f"[OK] 已写入 {path}")


# ─────────────── 主函数 ───────────────

def main():
    print("=" * 60)
    print("Harness B1 Metrics — 运行所有测试并生成指标")
    print("=" * 60)
    print()

    # 运行测试
    print("[1/4] 运行测试...")
    run_result = run_all_tests()

    print(f"  总计: {run_result['total']}")
    print(f"  通过: {run_result['passed']}")
    print(f"  失败: {run_result['failed']}")
    print(f"  错误: {run_result['errors']}")
    print(f"  耗时: {run_result['duration_ms']:.1f}ms")
    print()

    # 按 suite 统计
    print("[2/4] 按 suite 统计...")
    by_suite = compute_by_suite(run_result["tests"])
    for suite, stats in sorted(by_suite.items()):
        print(f"  {suite}: {stats['passed']}/{stats['total']} 通过")
    print()

    # 安全断言验证
    print("[3/4] 验证安全断言...")
    assertions = verify_safety_assertions(run_result["tests"])
    for name, passed in assertions.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {name}")
    print()

    # 输出文件
    print("[4/4] 生成输出文件...")
    metrics = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_tests": run_result["total"],
        "passed": run_result["passed"],
        "failed": run_result["failed"],
        "errors": run_result["errors"],
        "duration_ms": run_result["duration_ms"],
        "by_suite": by_suite,
        "safety_assertions": assertions,
        "all_safety_assertions_passed": all(assertions.values()),
        "all_tests_passed": run_result["failed"] == 0 and run_result["errors"] == 0,
    }

    json_path = os.path.join(_PROJECT_ROOT, "metrics.json")
    csv_path = os.path.join(_PROJECT_ROOT, "metrics.csv")
    write_metrics_json(metrics, json_path)
    write_metrics_csv(run_result["tests"], csv_path)

    print()
    print("=" * 60)
    if metrics["all_tests_passed"] and metrics["all_safety_assertions_passed"]:
        print("[SUCCESS] 所有测试通过，所有安全断言成立。")
    else:
        if not metrics["all_tests_passed"]:
            print(f"[WARNING] {run_result['failed']} 个测试失败，{run_result['errors']} 个错误。")
        if not metrics["all_safety_assertions_passed"]:
            failed_assertions = [k for k, v in assertions.items() if not v]
            print(f"[WARNING] 安全断言未通过: {failed_assertions}")
    print("=" * 60)

    return 0 if metrics["all_tests_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
