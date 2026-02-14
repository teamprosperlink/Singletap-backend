"""
Standard Test Runner Module

Provides a consistent interface for running tests with:
- Automatic documentation generation
- Report generation (JSON, HTML, JUnit XML)
- Hardware/infrastructure capture
- Timing metrics
"""

import os
import sys
import time
import traceback
from datetime import datetime
from typing import List, Dict, Any, Callable, Optional
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tests.utils.report_generator import TestReportGenerator
from tests.utils.doc_generator import TestDocumentationGenerator
from tests.utils.hardware_detector import get_hardware_info, get_infrastructure_info


@dataclass
class TestCase:
    """Definition of a single test case."""
    name: str
    description: str
    test_fn: Callable
    expected: Any
    input_data: Optional[Dict] = None
    tags: Optional[List[str]] = None


class StandardTestRunner:
    """
    Standard test runner with documentation and reporting.

    Usage:
        runner = StandardTestRunner(
            suite_name="My Test Suite",
            suite_purpose="Tests for feature X",
            output_dir="tests/regression/my_test"
        )

        runner.add_test(TestCase(
            name="Test 1",
            description="Tests basic functionality",
            test_fn=lambda: True,
            expected=True
        ))

        results = runner.run_all()
    """

    def __init__(
        self,
        suite_name: str,
        suite_purpose: str,
        output_dir: str,
        methodology: Optional[str] = None
    ):
        """
        Initialize the test runner.

        Args:
            suite_name: Name of the test suite
            suite_purpose: Description of what the suite tests
            output_dir: Directory for output files (docs, reports)
            methodology: Optional test methodology description
        """
        self.suite_name = suite_name
        self.suite_purpose = suite_purpose
        self.output_dir = output_dir
        self.methodology = methodology or self._default_methodology()
        self.test_cases: List[TestCase] = []
        self.libraries: List[Dict[str, str]] = []
        self.prerequisites: List[str] = []
        self.limitations: List[str] = []
        self.execution_notes: List[str] = []

        # Reporters
        self.report_generator = TestReportGenerator(suite_name)
        self.doc_generator = TestDocumentationGenerator(suite_name)

    def _default_methodology(self) -> str:
        return """The tests follow a data-driven approach:

1. **Test Data Definition**: Each test case is defined with:
   - Input data (listings, queries, parameters)
   - Expected output (match/no-match, canonical forms)

2. **Pipeline Execution**: Tests run through the full pipeline:
   - Canonicalization (preprocessing, disambiguation, normalization)
   - Matching (semantic implies, hierarchy checking)

3. **Assertion Verification**: Results are compared against expected outcomes:
   - Exact match comparison for deterministic outputs
   - Semantic equivalence for normalized forms

4. **Error Handling**: Failures are captured with:
   - Full stack traces for debugging
   - Intermediate state dumps for analysis"""

    def add_test(self, test_case: TestCase):
        """Add a test case to the suite."""
        self.test_cases.append(test_case)

    def add_tests(self, test_cases: List[TestCase]):
        """Add multiple test cases."""
        self.test_cases.extend(test_cases)

    def add_library(self, name: str, version: str, purpose: str):
        """Add a library dependency."""
        self.libraries.append({
            "name": name,
            "version": version,
            "purpose": purpose
        })

    def add_prerequisite(self, prereq: str):
        """Add a prerequisite."""
        self.prerequisites.append(prereq)

    def add_limitation(self, limitation: str):
        """Add a known limitation."""
        self.limitations.append(limitation)

    def add_execution_note(self, note: str):
        """Add an execution note."""
        self.execution_notes.append(note)

    def run_all(self, generate_docs: bool = True, generate_reports: bool = True) -> Dict[str, Any]:
        """
        Run all test cases and generate outputs.

        Args:
            generate_docs: Whether to generate documentation
            generate_reports: Whether to generate reports

        Returns:
            Dictionary with results summary and file paths
        """
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

        # Capture environment
        hardware_info = get_hardware_info()
        infrastructure_info = get_infrastructure_info()

        # Start timing
        self.report_generator.start_suite()
        self.report_generator.set_environment_info(hardware_info, infrastructure_info)

        results = []
        pass_count = 0
        fail_count = 0
        error_count = 0

        print(f"\n{'='*80}")
        print(f"RUNNING: {self.suite_name}")
        print(f"{'='*80}\n")

        for test_case in self.test_cases:
            print(f"  Running: {test_case.name}...", end=" ")

            start_time = time.time()
            try:
                actual = test_case.test_fn()
                duration_ms = (time.time() - start_time) * 1000

                if actual == test_case.expected:
                    status = "PASS"
                    pass_count += 1
                    print(f"PASS ({duration_ms:.1f}ms)")
                else:
                    status = "FAIL"
                    fail_count += 1
                    print(f"FAIL (expected {test_case.expected}, got {actual})")

                self.report_generator.add_test_result(
                    name=test_case.name,
                    status=status,
                    expected=test_case.expected,
                    actual=actual,
                    duration_ms=duration_ms,
                    metadata={"description": test_case.description}
                )

                results.append({
                    "name": test_case.name,
                    "status": status,
                    "expected": test_case.expected,
                    "actual": actual,
                    "duration_ms": duration_ms
                })

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                error_count += 1
                tb = traceback.format_exc()
                print(f"ERROR ({str(e)})")

                self.report_generator.add_test_result(
                    name=test_case.name,
                    status="ERROR",
                    expected=test_case.expected,
                    actual=None,
                    duration_ms=duration_ms,
                    error_message=str(e),
                    stack_trace=tb
                )

                results.append({
                    "name": test_case.name,
                    "status": "ERROR",
                    "error": str(e),
                    "traceback": tb
                })

        # End timing
        self.report_generator.end_suite()

        # Get total duration
        suite_result = self.report_generator.get_suite_result()
        total_duration = suite_result.duration_seconds

        # Print summary
        print(f"\n{'='*80}")
        print(f"SUMMARY: {self.suite_name}")
        print(f"{'='*80}")
        print(f"  Total:   {len(self.test_cases)}")
        print(f"  Passed:  {pass_count}")
        print(f"  Failed:  {fail_count}")
        print(f"  Errors:  {error_count}")
        print(f"  Duration: {total_duration:.2f}s")

        output_files = {}

        # Generate reports
        if generate_reports:
            report_files = self.report_generator.generate_all_reports(
                output_dir=self.output_dir,
                base_name="REPORT"
            )
            output_files["reports"] = report_files
            print(f"\n  Reports generated in: {self.output_dir}/")

        # Generate documentation
        if generate_docs:
            self._setup_doc_generator(total_duration)
            doc_path = self.doc_generator.generate_markdown(
                os.path.join(self.output_dir, "DOCUMENTATION.md")
            )
            output_files["documentation"] = doc_path
            print(f"  Documentation generated: DOCUMENTATION.md")

        return {
            "suite_name": self.suite_name,
            "total_tests": len(self.test_cases),
            "passed": pass_count,
            "failed": fail_count,
            "errors": error_count,
            "duration_seconds": total_duration,
            "results": results,
            "output_files": output_files
        }

    def _setup_doc_generator(self, duration: float):
        """Configure the documentation generator with all collected info."""
        self.doc_generator.set_purpose(self.suite_purpose)
        self.doc_generator.set_methodology(self.methodology)
        self.doc_generator.set_execution_time(duration)

        for tc in self.test_cases:
            self.doc_generator.add_test_case(
                name=tc.name,
                description=tc.description,
                input_data=str(tc.input_data) if tc.input_data else "",
                expected_output=str(tc.expected)
            )

        for lib in self.libraries:
            self.doc_generator.add_library(**lib)

        for prereq in self.prerequisites:
            self.doc_generator.add_prerequisite(prereq)

        for limit in self.limitations:
            self.doc_generator.add_limitation(limit)

        for note in self.execution_notes:
            self.doc_generator.add_execution_note(note)

        self.doc_generator.capture_environment()


def run_test_with_reports(
    suite_name: str,
    suite_purpose: str,
    test_cases: List[Dict],
    test_fn: Callable,
    output_dir: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Convenience function to run tests with full reporting.

    Args:
        suite_name: Name of the test suite
        suite_purpose: Purpose description
        test_cases: List of test case dictionaries with 'name', 'expected', etc.
        test_fn: Function that takes a test case and returns actual result
        output_dir: Output directory for docs/reports
        **kwargs: Additional options (libraries, prerequisites, etc.)

    Returns:
        Results dictionary
    """
    runner = StandardTestRunner(
        suite_name=suite_name,
        suite_purpose=suite_purpose,
        output_dir=output_dir,
        methodology=kwargs.get("methodology")
    )

    # Convert test case dicts to TestCase objects
    for tc in test_cases:
        runner.add_test(TestCase(
            name=tc["name"],
            description=tc.get("description", ""),
            test_fn=lambda t=tc: test_fn(t),
            expected=tc["expected"],
            input_data=tc.get("input_data")
        ))

    # Add metadata
    for lib in kwargs.get("libraries", []):
        runner.add_library(**lib)

    for prereq in kwargs.get("prerequisites", []):
        runner.add_prerequisite(prereq)

    for limit in kwargs.get("limitations", []):
        runner.add_limitation(limit)

    return runner.run_all()
