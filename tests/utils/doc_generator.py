"""
Test Documentation Generator Module

Generates standardized documentation for each test suite:
- Test methodology and approach
- Libraries and dependencies used
- Hardware specifications
- Infrastructure details
- Execution timing
"""

import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from tests.utils.hardware_detector import get_hardware_info, get_infrastructure_info


class TestDocumentationGenerator:
    """
    Enterprise-grade test documentation generator.

    Creates comprehensive documentation for test suites following
    industry standards and best practices.
    """

    def __init__(self, suite_name: str):
        """
        Initialize the documentation generator.

        Args:
            suite_name: Name of the test suite
        """
        self.suite_name = suite_name
        self.test_purpose: str = ""
        self.test_methodology: str = ""
        self.test_cases: List[Dict[str, str]] = []
        self.libraries: List[Dict[str, str]] = []
        self.prerequisites: List[str] = []
        self.setup_steps: List[str] = []
        self.execution_notes: List[str] = []
        self.known_limitations: List[str] = []
        self.related_documents: List[str] = []
        self.author: str = ""
        self.version: str = "1.0.0"
        self.hardware_info: Optional[Dict] = None
        self.infrastructure_info: Optional[Dict] = None
        self.execution_time_seconds: float = 0.0

    def set_purpose(self, purpose: str):
        """Set the test suite purpose."""
        self.test_purpose = purpose

    def set_methodology(self, methodology: str):
        """Set the test methodology description."""
        self.test_methodology = methodology

    def add_test_case(self, name: str, description: str, input_data: str = "", expected_output: str = ""):
        """Add a test case description."""
        self.test_cases.append({
            "name": name,
            "description": description,
            "input_data": input_data,
            "expected_output": expected_output
        })

    def add_library(self, name: str, version: str, purpose: str):
        """Add a library/dependency used."""
        self.libraries.append({
            "name": name,
            "version": version,
            "purpose": purpose
        })

    def add_prerequisite(self, prerequisite: str):
        """Add a prerequisite."""
        self.prerequisites.append(prerequisite)

    def add_setup_step(self, step: str):
        """Add a setup step."""
        self.setup_steps.append(step)

    def add_execution_note(self, note: str):
        """Add an execution note."""
        self.execution_notes.append(note)

    def add_limitation(self, limitation: str):
        """Add a known limitation."""
        self.known_limitations.append(limitation)

    def add_related_document(self, doc: str):
        """Add a related document reference."""
        self.related_documents.append(doc)

    def set_author(self, author: str):
        """Set the author name."""
        self.author = author

    def set_version(self, version: str):
        """Set the document version."""
        self.version = version

    def set_execution_time(self, seconds: float):
        """Set the execution time."""
        self.execution_time_seconds = seconds

    def capture_environment(self):
        """Capture current hardware and infrastructure info."""
        self.hardware_info = get_hardware_info()
        self.infrastructure_info = get_infrastructure_info()

    def generate_markdown(self, output_path: str) -> str:
        """
        Generate markdown documentation.

        Args:
            output_path: Path to save the documentation

        Returns:
            Path to generated documentation
        """
        # Capture environment if not already done
        if not self.hardware_info:
            self.capture_environment()

        doc_content = self._build_markdown_content()

        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(doc_content)

        return output_path

    def _build_markdown_content(self) -> str:
        """Build the complete markdown documentation content."""
        sections = []

        # Header
        sections.append(self._build_header())

        # Table of Contents
        sections.append(self._build_toc())

        # Overview
        sections.append(self._build_overview())

        # Test Methodology
        sections.append(self._build_methodology_section())

        # Test Cases
        if self.test_cases:
            sections.append(self._build_test_cases_section())

        # Libraries
        if self.libraries:
            sections.append(self._build_libraries_section())

        # Hardware & Infrastructure
        sections.append(self._build_environment_section())

        # Execution
        sections.append(self._build_execution_section())

        # Prerequisites
        if self.prerequisites:
            sections.append(self._build_prerequisites_section())

        # Known Limitations
        if self.known_limitations:
            sections.append(self._build_limitations_section())

        # Related Documents
        if self.related_documents:
            sections.append(self._build_related_docs_section())

        # Footer
        sections.append(self._build_footer())

        return "\n\n".join(sections)

    def _build_header(self) -> str:
        return f"""# Test Documentation: {self.suite_name}

| Property | Value |
|----------|-------|
| **Version** | {self.version} |
| **Author** | {self.author or 'Singletap Backend Team'} |
| **Created** | {datetime.now().strftime('%Y-%m-%d')} |
| **Last Updated** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |"""

    def _build_toc(self) -> str:
        return """## Table of Contents

1. [Overview](#overview)
2. [Test Methodology](#test-methodology)
3. [Test Cases](#test-cases)
4. [Libraries & Dependencies](#libraries--dependencies)
5. [Hardware & Infrastructure](#hardware--infrastructure)
6. [Execution Details](#execution-details)
7. [Prerequisites](#prerequisites)
8. [Known Limitations](#known-limitations)
9. [Related Documents](#related-documents)"""

    def _build_overview(self) -> str:
        return f"""## Overview

### Purpose

{self.test_purpose or 'This test suite validates the functionality and correctness of the component under test.'}

### Scope

This documentation covers:
- Test methodology and approach
- Complete list of test cases
- Required libraries and dependencies
- Hardware and infrastructure specifications
- Execution timing and metrics"""

    def _build_methodology_section(self) -> str:
        methodology = self.test_methodology or """The tests follow a structured approach:

1. **Setup Phase**: Initialize test fixtures and mock dependencies
2. **Execution Phase**: Run test cases with controlled inputs
3. **Verification Phase**: Compare actual outputs against expected results
4. **Cleanup Phase**: Release resources and restore system state

Tests are designed to be:
- **Deterministic**: Same inputs produce same outputs
- **Isolated**: Tests don't depend on each other
- **Repeatable**: Can be run multiple times reliably"""

        return f"""## Test Methodology

{methodology}"""

    def _build_test_cases_section(self) -> str:
        cases_table = "| # | Test Case | Description | Expected Outcome |\n"
        cases_table += "|---|-----------|-------------|------------------|\n"

        for i, tc in enumerate(self.test_cases, 1):
            cases_table += f"| {i} | {tc['name']} | {tc['description']} | {tc['expected_output'] or 'Pass'} |\n"

        return f"""## Test Cases

### Summary

Total Test Cases: **{len(self.test_cases)}**

### Test Case Details

{cases_table}"""

    def _build_libraries_section(self) -> str:
        libs_table = "| Library | Version | Purpose |\n"
        libs_table += "|---------|---------|----------|\n"

        for lib in self.libraries:
            libs_table += f"| {lib['name']} | {lib['version']} | {lib['purpose']} |\n"

        return f"""## Libraries & Dependencies

### Runtime Dependencies

{libs_table}

### Installation

```bash
pip install -r requirements.txt
```"""

    def _build_environment_section(self) -> str:
        hw = self.hardware_info or {}
        infra = self.infrastructure_info or {}

        os_info = hw.get('os', {})
        cpu_info = hw.get('cpu', {})
        mem_info = hw.get('memory', {})
        py_info = hw.get('python', {})

        return f"""## Hardware & Infrastructure

### Hardware Specifications

| Component | Specification |
|-----------|---------------|
| **Operating System** | {os_info.get('system', 'N/A')} {os_info.get('release', '')} |
| **Platform** | {os_info.get('platform', 'N/A')} |
| **CPU** | {cpu_info.get('processor', 'N/A')} |
| **CPU Cores** | {cpu_info.get('cores', 'N/A')} |
| **Architecture** | {cpu_info.get('architecture', 'N/A')} |
| **Total Memory** | {mem_info.get('total_gb', 'N/A')} GB |

### Software Environment

| Component | Version |
|-----------|---------|
| **Python Version** | {py_info.get('version', 'N/A')} |
| **Python Implementation** | {py_info.get('implementation', 'N/A')} |
| **Compiler** | {py_info.get('compiler', 'N/A')} |

### Infrastructure

| Property | Value |
|----------|-------|
| **Environment Type** | {infra.get('type', 'N/A')} |
| **Working Directory** | `{infra.get('working_directory', 'N/A')}` |
| **User** | {infra.get('user', 'N/A')} |

### Environment Variables

| Variable | Status |
|----------|--------|
{self._format_env_vars(infra.get('environment_variables', {}))}"""

    def _format_env_vars(self, env_vars: Dict[str, str]) -> str:
        if not env_vars:
            return "| None configured | - |"

        lines = []
        for key, value in env_vars.items():
            lines.append(f"| `{key}` | {value} |")
        return "\n".join(lines)

    def _build_execution_section(self) -> str:
        exec_time = self.execution_time_seconds
        time_str = f"{exec_time:.2f} seconds" if exec_time > 0 else "Not recorded"

        notes_list = ""
        for note in self.execution_notes:
            notes_list += f"- {note}\n"

        return f"""## Execution Details

### Timing

| Metric | Value |
|--------|-------|
| **Total Execution Time** | {time_str} |
| **Timestamp** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |

### How to Run

```bash
# Run from project root
python -m pytest tests/path/to/test.py -v

# Or run directly
python tests/path/to/test.py
```

### Execution Notes

{notes_list if notes_list else '- No special notes'}"""

    def _build_prerequisites_section(self) -> str:
        prereq_list = ""
        for prereq in self.prerequisites:
            prereq_list += f"- {prereq}\n"

        return f"""## Prerequisites

Before running these tests, ensure:

{prereq_list}"""

    def _build_limitations_section(self) -> str:
        limits_list = ""
        for limit in self.known_limitations:
            limits_list += f"- {limit}\n"

        return f"""## Known Limitations

{limits_list}"""

    def _build_related_docs_section(self) -> str:
        docs_list = ""
        for doc in self.related_documents:
            docs_list += f"- {doc}\n"

        return f"""## Related Documents

{docs_list}"""

    def _build_footer(self) -> str:
        return f"""---

*This documentation was auto-generated by the Singletap Backend Test Framework.*

*Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"""


def create_standard_documentation(
    suite_name: str,
    purpose: str,
    methodology: str,
    test_cases: List[Dict[str, str]],
    libraries: List[Dict[str, str]],
    output_path: str,
    execution_time: float = 0.0,
    **kwargs
) -> str:
    """
    Helper function to create standard documentation.

    Args:
        suite_name: Name of the test suite
        purpose: Test suite purpose
        methodology: Test methodology description
        test_cases: List of test case dictionaries
        libraries: List of library dictionaries
        output_path: Path to save documentation
        execution_time: Total execution time in seconds
        **kwargs: Additional options (prerequisites, limitations, etc.)

    Returns:
        Path to generated documentation
    """
    doc = TestDocumentationGenerator(suite_name)
    doc.set_purpose(purpose)
    doc.set_methodology(methodology)
    doc.set_execution_time(execution_time)

    for tc in test_cases:
        doc.add_test_case(
            name=tc.get("name", ""),
            description=tc.get("description", ""),
            input_data=tc.get("input_data", ""),
            expected_output=tc.get("expected_output", "")
        )

    for lib in libraries:
        doc.add_library(
            name=lib.get("name", ""),
            version=lib.get("version", ""),
            purpose=lib.get("purpose", "")
        )

    for prereq in kwargs.get("prerequisites", []):
        doc.add_prerequisite(prereq)

    for limit in kwargs.get("limitations", []):
        doc.add_limitation(limit)

    for note in kwargs.get("execution_notes", []):
        doc.add_execution_note(note)

    for doc_ref in kwargs.get("related_documents", []):
        doc.add_related_document(doc_ref)

    if kwargs.get("author"):
        doc.set_author(kwargs["author"])

    if kwargs.get("version"):
        doc.set_version(kwargs["version"])

    doc.capture_environment()
    return doc.generate_markdown(output_path)
