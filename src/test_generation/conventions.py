"""
Detect test conventions tool for test generation.

Analyzes existing tests to detect naming conventions, assertion styles,
mock patterns, and other testing conventions used in the project.
"""

import json
import re
from pathlib import Path
from typing import Any


async def detect_test_conventions(project_path: str, sample_size: int = 20) -> str:
    """
    Detect test conventions used in the project.

    Args:
        project_path: Path to the Java project root directory
        sample_size: Number of test files to sample for analysis

    Returns:
        JSON string with detected conventions
    """
    project_dir = Path(project_path)

    if not project_dir.exists():
        return json.dumps(
            {"success": False, "error": f"Project path does not exist: {project_path}"}
        )

    # Discover test files using plugin-provided patterns
    from src.lib.plugins import get_registry
    detected_plugin = get_registry().detect(project_dir)
    patterns = detected_plugin.test_file_pattern() if detected_plugin else ["**/*Test.java", "**/*Tests.java", "**/Test*.java"]

    test_files: list[Path] = []
    for pattern in patterns:
        # Strip leading **/ prefix if present — rglob already searches recursively
        glob_pattern = pattern.removeprefix("**/")
        test_files.extend(project_dir.rglob(glob_pattern))
    test_files = sorted(set(test_files))[:sample_size]  # deterministic sample

    if not test_files:
        return json.dumps({"success": False, "error": "No test files found"})

    conventions = {
        "success": True,
        "sample_size": len(test_files),
        "naming": await _analyze_naming_conventions(test_files),
        "assertions": await _analyze_assertion_styles(test_files),
        "mocking": await _analyze_mock_patterns(test_files),
        "setup_patterns": await _analyze_setup_patterns(test_files),
    }

    return json.dumps(conventions, indent=2)


async def _analyze_naming_conventions(test_files: list[Path]) -> dict[str, Any]:
    """Analyze test method naming conventions."""
    naming_patterns = {
        "should_when": 0,
        "should": 0,
        "given_when_then": 0,
        "test_description": 0,
        "method_state_result": 0,
        "camelCase": 0,
        "snake_case": 0,
    }

    method_names = []

    for test_file in test_files:
        try:
            content = test_file.read_text(encoding="utf-8", errors="replace")

            # Find test method names
            test_methods = re.findall(r"@Test\s+(?:public\s+)?void\s+(\w+)", content)
            method_names.extend(test_methods)

            for method in test_methods:
                if "should" in method.lower() and "when" in method.lower():
                    naming_patterns["should_when"] += 1
                elif method.startswith("should"):
                    naming_patterns["should"] += 1
                elif "given" in method.lower() and "then" in method.lower():
                    naming_patterns["given_when_then"] += 1
                elif method.startswith("test"):
                    naming_patterns["test_description"] += 1

                # Check case style
                if "_" in method:
                    naming_patterns["snake_case"] += 1
                else:
                    naming_patterns["camelCase"] += 1

        except Exception:
            pass

    # Dominant NAMING pattern: the case-style counters are tallied for every
    # method and must not compete with it (camelCase always won).
    styles = ("should_when", "should", "given_when_then", "test_description", "method_state_result")
    dominant_pattern = max(styles, key=lambda k: naming_patterns[k])
    if naming_patterns[dominant_pattern] == 0:
        dominant_pattern = "unknown"

    return {
        "dominant_pattern": dominant_pattern,
        "patterns": naming_patterns,
        "sample_methods": method_names[:10],
        "uses_snake_case": naming_patterns["snake_case"] > naming_patterns["camelCase"],
    }


async def _analyze_assertion_styles(test_files: list[Path]) -> dict[str, Any]:
    """Analyze assertion library and style preferences."""
    assertion_styles = {"junit_assertions": 0, "assertj": 0, "hamcrest": 0, "truth": 0}

    assertion_examples = []

    for test_file in test_files:
        try:
            content = test_file.read_text(encoding="utf-8", errors="replace")

            if "assertThat(" in content and "org.assertj" in content:
                assertion_styles["assertj"] += content.count("assertThat(")
            if "assertThat(" in content and "org.hamcrest" in content:
                assertion_styles["hamcrest"] += content.count("assertThat(")
            if "assertEquals(" in content or "assertTrue(" in content:
                assertion_styles["junit_assertions"] += (
                    content.count("assertEquals(")
                    + content.count("assertTrue(")
                    + content.count("assertFalse(")
                    + content.count("assertNotNull(")
                )
            if "com.google.common.truth" in content:
                assertion_styles["truth"] += content.count("assertThat(")

            # Extract sample assertions
            assertions = re.findall(r"(assert\w+\([^;]+\);)", content)
            assertion_examples.extend(assertions[:3])

        except Exception:
            pass

    dominant_style = (
        max(assertion_styles, key=lambda k: assertion_styles[k])
        if sum(assertion_styles.values()) > 0
        else "junit_assertions"
    )

    return {
        "dominant_style": dominant_style,
        "styles": assertion_styles,
        "examples": assertion_examples[:5],
    }


async def _analyze_mock_patterns(test_files: list[Path]) -> dict[str, Any]:
    """Analyze mocking patterns and frameworks."""
    mock_patterns = {
        "mockito_annotations": 0,
        "mockito_inline": 0,
        "mock_bean": 0,
        "spy": 0,
        "argument_captor": 0,
        "verify": 0,
    }

    for test_file in test_files:
        try:
            content = test_file.read_text(encoding="utf-8", errors="replace")

            if "@Mock" in content or "@InjectMocks" in content:
                mock_patterns["mockito_annotations"] += 1
            if "Mockito.mock(" in content or "mock(" in content:
                mock_patterns["mockito_inline"] += 1
            if "@MockBean" in content:
                mock_patterns["mock_bean"] += 1
            if "@Spy" in content or "Mockito.spy(" in content:
                mock_patterns["spy"] += 1
            if "ArgumentCaptor" in content:
                mock_patterns["argument_captor"] += 1
            if "verify(" in content:
                mock_patterns["verify"] += 1

        except Exception:
            pass

    uses_mockito = mock_patterns["mockito_annotations"] > 0 or mock_patterns["mockito_inline"] > 0
    uses_spring_mock = mock_patterns["mock_bean"] > 0

    return {
        "uses_mockito": uses_mockito,
        "uses_spring_mock_bean": uses_spring_mock,
        "patterns": mock_patterns,
        "prefers_annotations": mock_patterns["mockito_annotations"]
        > mock_patterns["mockito_inline"],
    }


async def _analyze_setup_patterns(test_files: list[Path]) -> dict[str, Any]:
    """Analyze test setup and teardown patterns."""
    setup_patterns = {
        "before_each": 0,
        "before_all": 0,
        "after_each": 0,
        "after_all": 0,
        "nested_classes": 0,
        "parameterized": 0,
    }

    for test_file in test_files:
        try:
            content = test_file.read_text(encoding="utf-8", errors="replace")

            if "@BeforeEach" in content or "@Before" in content:
                setup_patterns["before_each"] += 1
            if "@BeforeAll" in content or "@BeforeClass" in content:
                setup_patterns["before_all"] += 1
            if "@AfterEach" in content or "@After" in content:
                setup_patterns["after_each"] += 1
            if "@AfterAll" in content or "@AfterClass" in content:
                setup_patterns["after_all"] += 1
            if "@Nested" in content:
                setup_patterns["nested_classes"] += 1
            if "@ParameterizedTest" in content:
                setup_patterns["parameterized"] += 1

        except Exception:
            pass

    return {
        "patterns": setup_patterns,
        "uses_setup": setup_patterns["before_each"] > 0,
        "uses_nested": setup_patterns["nested_classes"] > 0,
        "uses_parameterized": setup_patterns["parameterized"] > 0,
    }
