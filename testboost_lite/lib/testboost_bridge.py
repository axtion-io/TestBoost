# SPDX-License-Identifier: Apache-2.0
"""Bridge module to TestBoost core functions.

Centralizes all imports from the TestBoost codebase (src/) so they can
be easily mocked in tests. This also provides a clear boundary between
testboost_lite and the existing TestBoost code.

In tests: mock `testboost_lite.lib.testboost_bridge.<function>`
In production: these just re-export the real functions.
"""

import sys
from pathlib import Path

# Add TestBoost root to path
TESTBOOST_ROOT = Path(__file__).parent.parent.parent
if str(TESTBOOST_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTBOOST_ROOT))


async def analyze_project_context(project_path: str, **kwargs) -> str:
    """Analyze a Java project structure and context."""
    from src.mcp_servers.test_generator.tools.analyze import (
        analyze_project_context as _analyze,
    )
    return await _analyze(project_path, **kwargs)


async def detect_test_conventions(project_path: str, **kwargs) -> str:
    """Detect test naming and assertion conventions."""
    from src.mcp_servers.test_generator.tools.conventions import (
        detect_test_conventions as _detect,
    )
    return await _detect(project_path, **kwargs)


def find_source_files(project_path: str) -> list[str]:
    """Find testable Java source files."""
    from src.workflows.test_generation_agent import _find_source_files
    return _find_source_files(project_path)


def classify_file(source_file: str) -> str:
    """Classify a Java source file by its role (Service, Controller, Repository, etc.)."""
    name = Path(source_file).stem.lower()
    if "controller" in name or "resource" in name:
        return "Controller"
    if "service" in name:
        return "Service"
    if "repository" in name or "dao" in name or "mapper" in name:
        return "Repository"
    if "entity" in name or "model" in name or "domain" in name:
        return "Model"
    if "config" in name or "configuration" in name:
        return "Config"
    if "util" in name or "helper" in name or "utils" in name:
        return "Utility"
    if "exception" in name or "error" in name:
        return "Exception"
    return "Other"


def find_test_for_source(project_path: str, source_file: str) -> str | None:
    """Find the test file corresponding to a Java source file."""
    class_name = Path(source_file).stem
    test_root = Path(project_path) / "src" / "test" / "java"
    if not test_root.exists():
        return None
    for candidate in [f"{class_name}Test.java", f"{class_name}Tests.java"]:
        matches = list(test_root.rglob(candidate))
        if matches:
            return str(matches[0])
    return None


async def generate_adaptive_tests(project_path: str, source_file: str, **kwargs) -> str:
    """Generate tests for a single source file using LLM."""
    from src.mcp_servers.test_generator.tools.generate_unit import (
        generate_adaptive_tests as _generate,
    )
    return await _generate(project_path=project_path, source_file=source_file, **kwargs)


def parse_maven_errors(maven_output: str):
    """Parse Maven compilation errors into structured format."""
    from src.lib.maven_error_parser import MavenErrorParser
    parser = MavenErrorParser()
    return parser, parser.parse(maven_output)
