"""
Hardware and Infrastructure Detection Module

Captures detailed system information for test documentation:
- CPU specifications
- Memory (RAM)
- Operating System
- Python version
- Infrastructure type (local, Docker, CI/CD)
"""

import platform
import os
import sys
from typing import Dict, Any
from datetime import datetime


def get_hardware_info() -> Dict[str, Any]:
    """
    Capture hardware specifications of the test environment.

    Returns:
        Dictionary containing CPU, memory, and OS details
    """
    info = {
        "cpu": {
            "processor": platform.processor() or "Unknown",
            "architecture": platform.machine(),
            "cores": _get_cpu_cores(),
        },
        "memory": {
            "total_gb": _get_total_memory_gb(),
        },
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "platform": platform.platform(),
        },
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "compiler": platform.python_compiler(),
        },
        "captured_at": datetime.now().isoformat(),
    }
    return info


def _get_cpu_cores() -> int:
    """Get the number of CPU cores."""
    try:
        return os.cpu_count() or 1
    except Exception:
        return 1


def _get_total_memory_gb() -> float:
    """Get total system memory in GB."""
    try:
        # Try psutil first (most accurate)
        import psutil
        return round(psutil.virtual_memory().total / (1024**3), 2)
    except ImportError:
        pass

    # Platform-specific fallbacks
    if platform.system() == "Windows":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            c_ulong = ctypes.c_ulong

            class MEMORYSTATUS(ctypes.Structure):
                _fields_ = [
                    ('dwLength', c_ulong),
                    ('dwMemoryLoad', c_ulong),
                    ('dwTotalPhys', c_ulong),
                    ('dwAvailPhys', c_ulong),
                    ('dwTotalPageFile', c_ulong),
                    ('dwAvailPageFile', c_ulong),
                    ('dwTotalVirtual', c_ulong),
                    ('dwAvailVirtual', c_ulong),
                ]

            memoryStatus = MEMORYSTATUS()
            memoryStatus.dwLength = ctypes.sizeof(MEMORYSTATUS)
            kernel32.GlobalMemoryStatus(ctypes.byref(memoryStatus))
            return round(memoryStatus.dwTotalPhys / (1024**3), 2)
        except Exception:
            pass

    elif platform.system() == "Linux":
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if 'MemTotal' in line:
                        # MemTotal is in kB
                        kb = int(line.split()[1])
                        return round(kb / (1024**2), 2)
        except Exception:
            pass

    return 0.0


def get_infrastructure_info() -> Dict[str, Any]:
    """
    Detect infrastructure environment (local, Docker, CI/CD).

    Returns:
        Dictionary containing infrastructure details
    """
    info = {
        "type": _detect_infrastructure_type(),
        "environment_variables": _get_relevant_env_vars(),
        "working_directory": os.getcwd(),
        "user": _get_current_user(),
    }

    # Add CI/CD specific info
    ci_info = _detect_ci_cd()
    if ci_info:
        info["ci_cd"] = ci_info

    # Add Docker info if applicable
    if _is_docker():
        info["docker"] = True

    return info


def _detect_infrastructure_type() -> str:
    """Detect the type of infrastructure running tests."""
    if _is_docker():
        return "Docker Container"

    ci_cd = _detect_ci_cd()
    if ci_cd:
        return f"CI/CD ({ci_cd.get('provider', 'Unknown')})"

    return "Local Development"


def _is_docker() -> bool:
    """Check if running inside a Docker container."""
    # Check for .dockerenv file
    if os.path.exists('/.dockerenv'):
        return True

    # Check cgroup
    try:
        with open('/proc/1/cgroup', 'rt') as f:
            return 'docker' in f.read()
    except Exception:
        pass

    return False


def _detect_ci_cd() -> Dict[str, str]:
    """Detect CI/CD environment and provider."""
    ci_providers = {
        "GITHUB_ACTIONS": {"provider": "GitHub Actions", "run_id": "GITHUB_RUN_ID"},
        "GITLAB_CI": {"provider": "GitLab CI", "run_id": "CI_PIPELINE_ID"},
        "JENKINS_URL": {"provider": "Jenkins", "run_id": "BUILD_NUMBER"},
        "TRAVIS": {"provider": "Travis CI", "run_id": "TRAVIS_BUILD_ID"},
        "CIRCLECI": {"provider": "CircleCI", "run_id": "CIRCLE_BUILD_NUM"},
        "AZURE_PIPELINES": {"provider": "Azure Pipelines", "run_id": "BUILD_BUILDID"},
        "BITBUCKET_PIPELINE": {"provider": "Bitbucket Pipelines", "run_id": "BITBUCKET_BUILD_NUMBER"},
    }

    for env_var, info in ci_providers.items():
        if os.environ.get(env_var):
            result = {"provider": info["provider"]}
            run_id = os.environ.get(info["run_id"])
            if run_id:
                result["run_id"] = run_id
            return result

    # Generic CI detection
    if os.environ.get("CI"):
        return {"provider": "Unknown CI", "ci_env": "true"}

    return {}


def _get_relevant_env_vars() -> Dict[str, str]:
    """Get relevant environment variables for testing."""
    relevant_vars = [
        "USE_NEW_PIPELINE",
        "USE_HYBRID_SCORER",
        "BABELNET_API_KEY",
        "RAPIDAPI_KEY",
        "WIKIDATA_CACHE_ENABLED",
    ]

    result = {}
    for var in relevant_vars:
        value = os.environ.get(var)
        if value:
            # Mask API keys
            if "KEY" in var or "SECRET" in var:
                result[var] = "***SET***"
            else:
                result[var] = value

    return result


def _get_current_user() -> str:
    """Get the current system user."""
    try:
        return os.getlogin()
    except Exception:
        return os.environ.get("USER", os.environ.get("USERNAME", "unknown"))


def get_test_environment_summary() -> str:
    """
    Get a human-readable summary of the test environment.

    Returns:
        Formatted string with environment details
    """
    hw = get_hardware_info()
    infra = get_infrastructure_info()

    summary = f"""
Test Environment Summary
========================
Infrastructure: {infra['type']}
OS: {hw['os']['system']} {hw['os']['release']}
CPU: {hw['cpu']['processor']} ({hw['cpu']['cores']} cores)
Memory: {hw['memory']['total_gb']} GB
Python: {hw['python']['version']} ({hw['python']['implementation']})
Working Directory: {infra['working_directory']}
Captured: {hw['captured_at']}
"""
    return summary.strip()
