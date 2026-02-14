"""
Test Report Generator Module

Generates professional test reports in multiple formats:
- JSON: Machine-readable format for CI/CD integration
- HTML: Human-readable format with visual styling
- JUnit XML: Standard format for CI/CD tools (Jenkins, GitHub Actions, etc.)
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from xml.etree import ElementTree as ET


@dataclass
class TestCaseResult:
    """Individual test case result."""
    name: str
    status: str  # "PASS", "FAIL", "ERROR", "SKIP"
    expected: Any
    actual: Any
    duration_ms: float = 0.0
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    metadata: Optional[Dict] = None


@dataclass
class TestSuiteResult:
    """Complete test suite result."""
    suite_name: str
    total_tests: int
    passed: int
    failed: int
    errors: int
    skipped: int
    duration_seconds: float
    start_time: str
    end_time: str
    test_cases: List[TestCaseResult]
    hardware_info: Optional[Dict] = None
    infrastructure_info: Optional[Dict] = None
    metadata: Optional[Dict] = None


class TestReportGenerator:
    """
    Enterprise-grade test report generator.

    Supports multiple output formats and integrates with CI/CD pipelines.
    """

    def __init__(self, suite_name: str):
        """
        Initialize the report generator.

        Args:
            suite_name: Name of the test suite
        """
        self.suite_name = suite_name
        self.test_cases: List[TestCaseResult] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.hardware_info: Optional[Dict] = None
        self.infrastructure_info: Optional[Dict] = None
        self.metadata: Dict = {}

    def start_suite(self):
        """Mark the start of test suite execution."""
        self.start_time = datetime.now()

    def end_suite(self):
        """Mark the end of test suite execution."""
        self.end_time = datetime.now()

    def add_test_result(
        self,
        name: str,
        status: str,
        expected: Any,
        actual: Any,
        duration_ms: float = 0.0,
        error_message: Optional[str] = None,
        stack_trace: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """
        Add a test case result.

        Args:
            name: Test case name
            status: Result status (PASS/FAIL/ERROR/SKIP)
            expected: Expected value
            actual: Actual value
            duration_ms: Test duration in milliseconds
            error_message: Error message if failed
            stack_trace: Stack trace if error
            metadata: Additional test metadata
        """
        self.test_cases.append(TestCaseResult(
            name=name,
            status=status.upper(),
            expected=expected,
            actual=actual,
            duration_ms=duration_ms,
            error_message=error_message,
            stack_trace=stack_trace,
            metadata=metadata
        ))

    def set_environment_info(self, hardware_info: Dict, infrastructure_info: Dict):
        """Set hardware and infrastructure information."""
        self.hardware_info = hardware_info
        self.infrastructure_info = infrastructure_info

    def set_metadata(self, **kwargs):
        """Set additional metadata for the report."""
        self.metadata.update(kwargs)

    def get_suite_result(self) -> TestSuiteResult:
        """Generate the complete test suite result."""
        passed = sum(1 for tc in self.test_cases if tc.status == "PASS")
        failed = sum(1 for tc in self.test_cases if tc.status == "FAIL")
        errors = sum(1 for tc in self.test_cases if tc.status == "ERROR")
        skipped = sum(1 for tc in self.test_cases if tc.status == "SKIP")

        start = self.start_time or datetime.now()
        end = self.end_time or datetime.now()
        duration = (end - start).total_seconds()

        return TestSuiteResult(
            suite_name=self.suite_name,
            total_tests=len(self.test_cases),
            passed=passed,
            failed=failed,
            errors=errors,
            skipped=skipped,
            duration_seconds=duration,
            start_time=start.isoformat(),
            end_time=end.isoformat(),
            test_cases=self.test_cases,
            hardware_info=self.hardware_info,
            infrastructure_info=self.infrastructure_info,
            metadata=self.metadata
        )

    def generate_json_report(self, output_path: str) -> str:
        """
        Generate JSON report.

        Args:
            output_path: Path to save the report

        Returns:
            Path to generated report
        """
        result = self.get_suite_result()

        # Convert dataclasses to dicts
        report_data = {
            "suite_name": result.suite_name,
            "summary": {
                "total_tests": result.total_tests,
                "passed": result.passed,
                "failed": result.failed,
                "errors": result.errors,
                "skipped": result.skipped,
                "pass_rate": f"{(result.passed / result.total_tests * 100):.1f}%" if result.total_tests > 0 else "N/A",
                "duration_seconds": round(result.duration_seconds, 3),
            },
            "timing": {
                "start_time": result.start_time,
                "end_time": result.end_time,
                "duration_seconds": round(result.duration_seconds, 3),
            },
            "environment": {
                "hardware": result.hardware_info,
                "infrastructure": result.infrastructure_info,
            },
            "metadata": result.metadata,
            "test_cases": [
                {
                    "name": tc.name,
                    "status": tc.status,
                    "expected": tc.expected,
                    "actual": tc.actual,
                    "duration_ms": tc.duration_ms,
                    "error_message": tc.error_message,
                    "stack_trace": tc.stack_trace,
                    "metadata": tc.metadata,
                }
                for tc in result.test_cases
            ],
            "generated_at": datetime.now().isoformat(),
        }

        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)

        return output_path

    def generate_html_report(self, output_path: str) -> str:
        """
        Generate HTML report with styling.

        Args:
            output_path: Path to save the report

        Returns:
            Path to generated report
        """
        result = self.get_suite_result()
        pass_rate = (result.passed / result.total_tests * 100) if result.total_tests > 0 else 0

        # Generate test case rows
        test_rows = ""
        for tc in result.test_cases:
            status_class = {
                "PASS": "status-pass",
                "FAIL": "status-fail",
                "ERROR": "status-error",
                "SKIP": "status-skip"
            }.get(tc.status, "")

            error_info = ""
            if tc.error_message:
                error_info = f'<div class="error-info">{tc.error_message}</div>'

            test_rows += f"""
            <tr class="{status_class}">
                <td>{tc.name}</td>
                <td class="status">{tc.status}</td>
                <td>{tc.expected}</td>
                <td>{tc.actual}</td>
                <td>{tc.duration_ms:.2f} ms</td>
            </tr>
            {f'<tr><td colspan="5">{error_info}</td></tr>' if error_info else ''}
            """

        # Hardware info
        hw_info = ""
        if result.hardware_info:
            hw = result.hardware_info
            hw_info = f"""
            <div class="info-section">
                <h3>Hardware Information</h3>
                <table class="info-table">
                    <tr><td>OS</td><td>{hw.get('os', {}).get('system', 'N/A')} {hw.get('os', {}).get('release', '')}</td></tr>
                    <tr><td>CPU</td><td>{hw.get('cpu', {}).get('processor', 'N/A')} ({hw.get('cpu', {}).get('cores', 'N/A')} cores)</td></tr>
                    <tr><td>Memory</td><td>{hw.get('memory', {}).get('total_gb', 'N/A')} GB</td></tr>
                    <tr><td>Python</td><td>{hw.get('python', {}).get('version', 'N/A')}</td></tr>
                </table>
            </div>
            """

        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Report - {result.suite_name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px 8px 0 0; }}
        .header h1 {{ font-size: 24px; margin-bottom: 10px; }}
        .header .timestamp {{ opacity: 0.8; font-size: 14px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 20px; padding: 20px; background: #fafafa; }}
        .summary-card {{ background: white; padding: 20px; border-radius: 8px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .summary-card .value {{ font-size: 32px; font-weight: bold; }}
        .summary-card .label {{ color: #666; font-size: 14px; margin-top: 5px; }}
        .summary-card.passed .value {{ color: #22c55e; }}
        .summary-card.failed .value {{ color: #ef4444; }}
        .summary-card.errors .value {{ color: #f59e0b; }}
        .content {{ padding: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; font-weight: 600; color: #333; }}
        .status-pass {{ background: #f0fdf4; }}
        .status-fail {{ background: #fef2f2; }}
        .status-error {{ background: #fffbeb; }}
        .status-skip {{ background: #f5f5f5; }}
        .status {{ font-weight: bold; }}
        .status-pass .status {{ color: #22c55e; }}
        .status-fail .status {{ color: #ef4444; }}
        .status-error .status {{ color: #f59e0b; }}
        .error-info {{ padding: 10px; background: #fef2f2; border-left: 3px solid #ef4444; font-size: 13px; color: #991b1b; }}
        .info-section {{ margin-top: 30px; padding: 20px; background: #f8f9fa; border-radius: 8px; }}
        .info-section h3 {{ margin-bottom: 15px; color: #333; }}
        .info-table {{ width: auto; }}
        .info-table td:first-child {{ font-weight: 600; padding-right: 20px; color: #666; }}
        .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; border-top: 1px solid #eee; }}
        .progress-bar {{ height: 8px; background: #e5e7eb; border-radius: 4px; overflow: hidden; margin-top: 10px; }}
        .progress-fill {{ height: 100%; background: linear-gradient(90deg, #22c55e, #16a34a); transition: width 0.3s; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{result.suite_name}</h1>
            <div class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
        </div>

        <div class="summary">
            <div class="summary-card">
                <div class="value">{result.total_tests}</div>
                <div class="label">Total Tests</div>
            </div>
            <div class="summary-card passed">
                <div class="value">{result.passed}</div>
                <div class="label">Passed</div>
            </div>
            <div class="summary-card failed">
                <div class="value">{result.failed}</div>
                <div class="label">Failed</div>
            </div>
            <div class="summary-card errors">
                <div class="value">{result.errors}</div>
                <div class="label">Errors</div>
            </div>
            <div class="summary-card">
                <div class="value">{pass_rate:.1f}%</div>
                <div class="label">Pass Rate</div>
                <div class="progress-bar"><div class="progress-fill" style="width: {pass_rate}%"></div></div>
            </div>
            <div class="summary-card">
                <div class="value">{result.duration_seconds:.2f}s</div>
                <div class="label">Duration</div>
            </div>
        </div>

        <div class="content">
            <h2>Test Results</h2>
            <table>
                <thead>
                    <tr>
                        <th>Test Name</th>
                        <th>Status</th>
                        <th>Expected</th>
                        <th>Actual</th>
                        <th>Duration</th>
                    </tr>
                </thead>
                <tbody>
                    {test_rows}
                </tbody>
            </table>

            {hw_info}
        </div>

        <div class="footer">
            <p>Singletap Backend Test Report | Duration: {result.duration_seconds:.2f}s | {result.start_time} to {result.end_time}</p>
        </div>
    </div>
</body>
</html>
        """

        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return output_path

    def generate_junit_xml(self, output_path: str) -> str:
        """
        Generate JUnit XML report for CI/CD integration.

        Args:
            output_path: Path to save the report

        Returns:
            Path to generated report
        """
        result = self.get_suite_result()

        # Create root element
        testsuites = ET.Element('testsuites')
        testsuites.set('tests', str(result.total_tests))
        testsuites.set('failures', str(result.failed))
        testsuites.set('errors', str(result.errors))
        testsuites.set('time', str(result.duration_seconds))

        # Create testsuite element
        testsuite = ET.SubElement(testsuites, 'testsuite')
        testsuite.set('name', result.suite_name)
        testsuite.set('tests', str(result.total_tests))
        testsuite.set('failures', str(result.failed))
        testsuite.set('errors', str(result.errors))
        testsuite.set('skipped', str(result.skipped))
        testsuite.set('time', str(result.duration_seconds))
        testsuite.set('timestamp', result.start_time)

        # Add test cases
        for tc in result.test_cases:
            testcase = ET.SubElement(testsuite, 'testcase')
            testcase.set('name', tc.name)
            testcase.set('classname', result.suite_name)
            testcase.set('time', str(tc.duration_ms / 1000))

            if tc.status == "FAIL":
                failure = ET.SubElement(testcase, 'failure')
                failure.set('message', tc.error_message or f"Expected: {tc.expected}, Actual: {tc.actual}")
                failure.set('type', 'AssertionError')
                if tc.stack_trace:
                    failure.text = tc.stack_trace

            elif tc.status == "ERROR":
                error = ET.SubElement(testcase, 'error')
                error.set('message', tc.error_message or "Unknown error")
                error.set('type', 'Error')
                if tc.stack_trace:
                    error.text = tc.stack_trace

            elif tc.status == "SKIP":
                skipped = ET.SubElement(testcase, 'skipped')
                if tc.error_message:
                    skipped.set('message', tc.error_message)

        # Write to file
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        tree = ET.ElementTree(testsuites)
        tree.write(output_path, encoding='utf-8', xml_declaration=True)

        return output_path

    def generate_all_reports(self, output_dir: str, base_name: str = "report") -> Dict[str, str]:
        """
        Generate all report formats.

        Args:
            output_dir: Directory to save reports
            base_name: Base name for report files

        Returns:
            Dictionary mapping format to file path
        """
        os.makedirs(output_dir, exist_ok=True)

        return {
            "json": self.generate_json_report(os.path.join(output_dir, f"{base_name}.json")),
            "html": self.generate_html_report(os.path.join(output_dir, f"{base_name}.html")),
            "junit_xml": self.generate_junit_xml(os.path.join(output_dir, f"{base_name}.xml")),
        }
