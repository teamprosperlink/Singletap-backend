"""
Testing Utilities Package

This package provides enterprise-grade testing utilities including:
- Hardware/Infrastructure detection
- Documentation generation
- Report generation (JSON, HTML, JUnit XML)
- Test runner with metrics collection
"""

from tests.utils.hardware_detector import get_hardware_info, get_infrastructure_info
from tests.utils.report_generator import TestReportGenerator
from tests.utils.doc_generator import TestDocumentationGenerator

__all__ = [
    'get_hardware_info',
    'get_infrastructure_info',
    'TestReportGenerator',
    'TestDocumentationGenerator'
]
