# SPDX-License-Identifier: Apache-2.0
"""Bridge module to TestBoost core functions.

Centralizes all imports from the TestBoost codebase (src/) so they can
be easily mocked in tests. This also provides a clear boundary between
testboost and the existing TestBoost code.

In tests: mock `src.lib.bridge.<function>`
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
    from src.test_generation.analyze import (
        analyze_project_context as _analyze,
    )
    return await _analyze(project_path, **kwargs)


async def detect_test_conventions(project_path: str, **kwargs) -> str:
    """Detect test naming and assertion conventions."""
    from src.test_generation.conventions import (
        detect_test_conventions as _detect,
    )
    return await _detect(project_path, **kwargs)


def get_plugin_for_session(project_path: str):
    """Return the plugin for the project's current session.

    Reads the technology identifier from session metadata and looks up
    the corresponding plugin in the registry.

    Falls back to 'java-spring' if no session or no technology field exists
    (backward compatibility for sessions created before the plugin system).

    Args:
        project_path: Path to the project root.

    Returns:
        TechnologyPlugin instance for this session's technology.
    """
    from pathlib import Path as _Path

    from src.lib.plugins import get_registry
    from src.lib.session_tracker import get_current_session, get_session_technology

    session = get_current_session(project_path)
    if session:
        technology = get_session_technology(_Path(session["session_dir"]))
    else:
        technology = "java-spring"

    return get_registry().get(technology)


def find_source_files(project_path: str) -> list[str]:
    """Find testable source files for the current session's technology."""
    from pathlib import Path as _Path
    plugin = get_plugin_for_session(project_path)
    return plugin.find_source_files(_Path(project_path))


def classify_file(relative_path: str, project_path: str = "") -> str:
    """Classify a source file by category using the current session's plugin."""
    if project_path:
        plugin = get_plugin_for_session(project_path)
    else:
        # Fallback: use Java plugin for backward compatibility
        from src.java.discovery import classify_source_file
        return classify_source_file(relative_path)
    return plugin.classify_source_file(relative_path)


def find_test_for_source(project_path: str, source_relative_path: str) -> str | None:
    """Find existing test file for a source file, if any."""
    from src.java.discovery import find_existing_test
    return find_existing_test(project_path, source_relative_path)


async def generate_adaptive_tests(project_path: str, source_file: str, **kwargs) -> str:
    """Generate tests for a single source file using LLM.

    CRITICAL: If the LLM is not reachable, this function MUST raise an exception.
    It should NEVER silently fallback or return empty results without error.
    """
    from src.test_generation.generate_unit import (
        generate_adaptive_tests as _generate,
    )
    return await _generate(project_path=project_path, source_file=source_file, **kwargs)


async def fix_compilation_errors(test_code: str, compile_errors: str, class_name: str) -> str:
    """Fix compilation errors in generated test code using LLM."""
    from src.test_generation.generate_unit import (
        fix_compilation_errors as _fix,
    )
    return await _fix(test_code, compile_errors, class_name)


def build_class_index(project_path: str, source_files: list[str]) -> dict[str, dict]:
    """Build the full class index for all source files.

    Delegates to the Java class analyzer for backward compatibility.
    For the Python plugin, use plugin.build_generation_context() directly.
    """
    from src.java.class_analyzer import build_class_index as _build
    return _build(project_path, source_files)


def extract_test_examples(
    project_path: str, max_examples: int = 3, max_lines: int = 150
) -> list[dict]:
    """Extract representative test file examples from the project."""
    from src.java.class_analyzer import extract_test_examples as _extract
    return _extract(project_path, max_examples=max_examples, max_lines=max_lines)


async def analyze_edge_cases(source_code: str, class_name: str, class_type: str) -> list[dict]:
    """Analyze a Java class for edge case test scenarios using LLM."""
    from src.test_generation.generate_unit import (
        analyze_edge_cases as _analyze,
    )
    return await _analyze(source_code, class_name, class_type)


async def run_mutation_testing(project_path: str, **kwargs) -> str:
    """Run PIT mutation testing on a Java project."""
    from src.test_generation.mutation import (
        run_mutation_testing as _run,
    )
    return await _run(project_path, **kwargs)


async def analyze_mutants(project_path: str, **kwargs) -> str:
    """Analyze mutation testing results for insights and recommendations."""
    from src.test_generation.analyze_mutants import (
        analyze_mutants as _analyze,
    )
    return await _analyze(project_path, **kwargs)


async def generate_killer_tests(project_path: str, surviving_mutants: list[dict], **kwargs) -> str:
    """Generate tests to kill surviving mutants."""
    from src.test_generation.killer_tests import (
        generate_killer_tests as _generate,
    )
    return await _generate(project_path, surviving_mutants, **kwargs)


def parse_maven_errors(maven_output: str):
    """Parse Maven compilation errors into structured format."""
    from src.lib.maven_error_parser import MavenErrorParser
    parser = MavenErrorParser()
    return parser, parser.parse(maven_output)
