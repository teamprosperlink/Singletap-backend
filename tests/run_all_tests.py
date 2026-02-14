"""
Master Test Runner

Runs all test suites and generates comprehensive reports:
- Unit tests
- Integration tests
- E2E tests
- Regression tests

Usage:
    python tests/run_all_tests.py [--quick] [--report-only]

Options:
    --quick       Run only quick tests (skip slow ones)
    --report-only Generate reports from cached results
"""

import sys
import os
import json
import time
from datetime import datetime
from typing import Dict, List, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.utils.hardware_detector import get_hardware_info, get_infrastructure_info


def run_test_suite(suite_path: str, suite_name: str) -> Dict[str, Any]:
    """
    Run a single test suite and return results.

    Args:
        suite_path: Path to the test module
        suite_name: Human-readable name

    Returns:
        Dictionary with results
    """
    print(f"\n{'='*80}")
    print(f"RUNNING: {suite_name}")
    print(f"Path: {suite_path}")
    print(f"{'='*80}")

    start_time = time.time()

    try:
        # Import and run the test module
        import importlib.util
        spec = importlib.util.spec_from_file_location("test_module", suite_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if hasattr(module, 'main'):
            passed, failed, errors = module.main()
            duration = time.time() - start_time

            return {
                "suite_name": suite_name,
                "path": suite_path,
                "status": "completed",
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "total": passed + failed + errors,
                "duration_seconds": round(duration, 2),
            }
        else:
            return {
                "suite_name": suite_name,
                "path": suite_path,
                "status": "error",
                "error": "No main() function found",
                "duration_seconds": 0,
            }

    except Exception as e:
        import traceback
        duration = time.time() - start_time

        return {
            "suite_name": suite_name,
            "path": suite_path,
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "duration_seconds": round(duration, 2),
        }


def generate_master_report(results: List[Dict], output_dir: str) -> str:
    """
    Generate a comprehensive master report.

    Args:
        results: List of test suite results
        output_dir: Directory to save reports

    Returns:
        Path to generated report
    """
    os.makedirs(output_dir, exist_ok=True)

    # Calculate totals
    total_passed = sum(r.get("passed", 0) for r in results)
    total_failed = sum(r.get("failed", 0) for r in results)
    total_errors = sum(r.get("errors", 0) for r in results)
    total_tests = sum(r.get("total", 0) for r in results)
    total_duration = sum(r.get("duration_seconds", 0) for r in results)

    completed_suites = [r for r in results if r.get("status") == "completed"]
    error_suites = [r for r in results if r.get("status") == "error"]

    pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

    # Get environment info
    hardware_info = get_hardware_info()
    infrastructure_info = get_infrastructure_info()

    report = {
        "report_type": "Master Test Report",
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_suites": len(results),
            "completed_suites": len(completed_suites),
            "error_suites": len(error_suites),
            "total_tests": total_tests,
            "passed": total_passed,
            "failed": total_failed,
            "errors": total_errors,
            "pass_rate": f"{pass_rate:.1f}%",
            "total_duration_seconds": round(total_duration, 2),
        },
        "environment": {
            "hardware": hardware_info,
            "infrastructure": infrastructure_info,
        },
        "suites": results,
    }

    # Save JSON report
    json_path = os.path.join(output_dir, "master_report.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, default=str)

    # Generate HTML report
    html_path = os.path.join(output_dir, "master_report.html")
    generate_html_master_report(report, html_path)

    return json_path


def generate_html_master_report(report: Dict, output_path: str):
    """Generate HTML master report."""
    summary = report["summary"]
    suites = report["suites"]
    pass_rate = float(summary["pass_rate"].replace("%", ""))

    # Generate suite rows
    suite_rows = ""
    for suite in suites:
        if suite["status"] == "completed":
            status_class = "status-pass" if suite["failed"] == 0 and suite["errors"] == 0 else "status-fail"
            status_text = "PASS" if suite["failed"] == 0 and suite["errors"] == 0 else "FAIL"
            suite_rows += f"""
            <tr class="{status_class}">
                <td>{suite['suite_name']}</td>
                <td class="status">{status_text}</td>
                <td>{suite['passed']}</td>
                <td>{suite['failed']}</td>
                <td>{suite['errors']}</td>
                <td>{suite['total']}</td>
                <td>{suite['duration_seconds']}s</td>
            </tr>
            """
        else:
            suite_rows += f"""
            <tr class="status-error">
                <td>{suite['suite_name']}</td>
                <td class="status">ERROR</td>
                <td colspan="5">{suite.get('error', 'Unknown error')}</td>
            </tr>
            """

    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Master Test Report - Singletap Backend</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #1e3a5f 0%, #2c5282 100%); color: white; padding: 40px; border-radius: 8px 8px 0 0; }}
        .header h1 {{ font-size: 28px; margin-bottom: 10px; }}
        .header .subtitle {{ opacity: 0.8; font-size: 16px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 20px; padding: 30px; background: white; }}
        .summary-card {{ background: #f8f9fa; padding: 25px; border-radius: 8px; text-align: center; }}
        .summary-card .value {{ font-size: 36px; font-weight: bold; }}
        .summary-card .label {{ color: #666; font-size: 14px; margin-top: 8px; }}
        .summary-card.passed .value {{ color: #22c55e; }}
        .summary-card.failed .value {{ color: #ef4444; }}
        .summary-card.errors .value {{ color: #f59e0b; }}
        .content {{ padding: 30px; background: white; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 15px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
        .status-pass {{ background: #f0fdf4; }}
        .status-fail {{ background: #fef2f2; }}
        .status-error {{ background: #fffbeb; }}
        .status {{ font-weight: bold; }}
        .status-pass .status {{ color: #22c55e; }}
        .status-fail .status {{ color: #ef4444; }}
        .status-error .status {{ color: #f59e0b; }}
        .progress-bar {{ height: 10px; background: #e5e7eb; border-radius: 5px; overflow: hidden; margin-top: 10px; }}
        .progress-fill {{ height: 100%; background: linear-gradient(90deg, #22c55e, #16a34a); }}
        .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; background: white; border-radius: 0 0 8px 8px; border-top: 1px solid #eee; }}
        h2 {{ margin-bottom: 20px; color: #1e3a5f; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Singletap Backend - Master Test Report</h1>
            <div class="subtitle">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
        </div>

        <div class="summary">
            <div class="summary-card">
                <div class="value">{summary['total_suites']}</div>
                <div class="label">Test Suites</div>
            </div>
            <div class="summary-card">
                <div class="value">{summary['total_tests']}</div>
                <div class="label">Total Tests</div>
            </div>
            <div class="summary-card passed">
                <div class="value">{summary['passed']}</div>
                <div class="label">Passed</div>
            </div>
            <div class="summary-card failed">
                <div class="value">{summary['failed']}</div>
                <div class="label">Failed</div>
            </div>
            <div class="summary-card errors">
                <div class="value">{summary['errors']}</div>
                <div class="label">Errors</div>
            </div>
            <div class="summary-card">
                <div class="value">{summary['pass_rate']}</div>
                <div class="label">Pass Rate</div>
                <div class="progress-bar"><div class="progress-fill" style="width: {pass_rate}%"></div></div>
            </div>
            <div class="summary-card">
                <div class="value">{summary['total_duration_seconds']}s</div>
                <div class="label">Total Duration</div>
            </div>
        </div>

        <div class="content">
            <h2>Test Suite Results</h2>
            <table>
                <thead>
                    <tr>
                        <th>Suite Name</th>
                        <th>Status</th>
                        <th>Passed</th>
                        <th>Failed</th>
                        <th>Errors</th>
                        <th>Total</th>
                        <th>Duration</th>
                    </tr>
                </thead>
                <tbody>
                    {suite_rows}
                </tbody>
            </table>
        </div>

        <div class="footer">
            <p>Singletap Backend Test Framework | Total Duration: {summary['total_duration_seconds']}s</p>
        </div>
    </div>
</body>
</html>
    """

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)


def main():
    """Run all test suites."""
    print("\n" + "="*80)
    print("SINGLETAP BACKEND - MASTER TEST RUNNER")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Define test suites
    test_root = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(test_root)

    test_suites = [
        {
            "name": "Unit Tests - Preprocessor",
            "path": os.path.join(test_root, "unit", "preprocessor", "test_preprocessor.py"),
        },
        {
            "name": "Integration Tests - Semantic Implies",
            "path": os.path.join(test_root, "integration", "semantic_implies", "test_semantic_implies.py"),
        },
        {
            "name": "E2E Tests - Canonicalization",
            "path": os.path.join(test_root, "e2e", "canonicalization", "test_e2e_canonicalization.py"),
        },
        {
            "name": "Regression Tests - Matching Robustness",
            "path": os.path.join(test_root, "regression", "matching_robustness", "test_matching_robustness.py"),
        },
        {
            "name": "Regression Tests - Reverse Hierarchy",
            "path": os.path.join(test_root, "regression", "reverse_hierarchy", "test_reverse_hierarchy.py"),
        },
    ]

    # Run all suites
    results = []
    total_start = time.time()

    for suite in test_suites:
        if os.path.exists(suite["path"]):
            result = run_test_suite(suite["path"], suite["name"])
            results.append(result)
        else:
            print(f"\nWARNING: Suite not found: {suite['path']}")
            results.append({
                "suite_name": suite["name"],
                "path": suite["path"],
                "status": "error",
                "error": "Test file not found",
            })

    total_duration = time.time() - total_start

    # Generate master report
    report_dir = os.path.join(test_root, "reports")
    report_path = generate_master_report(results, report_dir)

    # Print summary
    print("\n" + "="*80)
    print("MASTER TEST SUMMARY")
    print("="*80)

    total_passed = sum(r.get("passed", 0) for r in results)
    total_failed = sum(r.get("failed", 0) for r in results)
    total_errors = sum(r.get("errors", 0) for r in results)
    total_tests = sum(r.get("total", 0) for r in results)

    print(f"\n  Suites Run:    {len(results)}")
    print(f"  Total Tests:   {total_tests}")
    print(f"  Passed:        {total_passed}")
    print(f"  Failed:        {total_failed}")
    print(f"  Errors:        {total_errors}")
    print(f"  Duration:      {total_duration:.2f}s")

    if total_tests > 0:
        pass_rate = total_passed / total_tests * 100
        print(f"  Pass Rate:     {pass_rate:.1f}%")

    print(f"\n  Reports saved to: {report_dir}/")
    print(f"    - master_report.json")
    print(f"    - master_report.html")

    print("\n" + "="*80)
    if total_failed == 0 and total_errors == 0:
        print("ALL TESTS PASSED!")
    else:
        print(f"TESTS COMPLETED WITH {total_failed} FAILURES AND {total_errors} ERRORS")
    print("="*80)

    # Return exit code
    return 0 if (total_failed == 0 and total_errors == 0) else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
