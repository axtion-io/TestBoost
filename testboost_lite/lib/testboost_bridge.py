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
    """Analyze a Java project structure and context.

    Wraps src.mcp_servers.test_generator.tools.analyze.analyze_project_context
    """
    from src.mcp_servers.test_generator.tools.analyze import (
        analyze_project_context as _analyze,
    )
    return await _analyze(project_path, **kwargs)


async def detect_test_conventions(project_path: str, **kwargs) -> str:
    """Detect test naming and assertion conventions.

    Wraps src.mcp_servers.test_generator.tools.conventions.detect_test_conventions
    """
    from src.mcp_servers.test_generator.tools.conventions import (
        detect_test_conventions as _detect,
    )
    return await _detect(project_path, **kwargs)


def find_source_files(project_path: str) -> list[str]:
    """Find testable Java source files.

    Wraps src.workflows.test_generation_agent._find_source_files
    """
    from src.workflows.test_generation_agent import (
        _find_source_files,
    )
    return _find_source_files(project_path)


async def generate_adaptive_tests(project_path: str, source_file: str, **kwargs) -> str:
    """Generate tests for a single source file using LLM.

    Wraps src.mcp_servers.test_generator.tools.generate_unit.generate_adaptive_tests

    CRITICAL: If the LLM is not reachable, this function MUST raise an exception.
    It should NEVER silently fallback or return empty results without error.
    """
    from src.mcp_servers.test_generator.tools.generate_unit import (
        generate_adaptive_tests as _generate,
    )
    return await _generate(project_path=project_path, source_file=source_file, **kwargs)


def parse_maven_errors(maven_output: str):
    """Parse Maven compilation errors into structured format.

    Wraps src.lib.maven_error_parser.MavenErrorParser
    """
    from src.lib.maven_error_parser import MavenErrorParser
    parser = MavenErrorParser()
    return parser, parser.parse(maven_output)
