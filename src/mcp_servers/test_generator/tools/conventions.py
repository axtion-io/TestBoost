"""
Detect test conventions tool for test generation.

Analyzes existing tests to detect naming conventions, assertion styles,
mock patterns, and other testing conventions used in the project.
"""

import json
import re
from collections import Counter
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

    test_dir = project_dir / "src" / "test" / "java"
    if not test_dir.exists():
        return json.dumps({"success": False, "error": "Test directory not found"})

    # Find test files
    test_files = list(test_dir.rglob("*Test.java"))
    test_files.extend(test_dir.rglob("*Tests.java"))
    test_files.extend(test_dir.rglob("Test*.java"))
    test_files = list(set(test_files))[:sample_size]

    if not test_files:
        return json.dumps({"success": False, "error": "No test files found"})

    conventions = {
        "success": True,
        "sample_size": len(test_files),
        "naming": await _analyze_naming_conventions(test_files),
        "assertions": await _analyze_assertion_styles(test_files),
        "mocking": await _analyze_mock_patterns(test_files),
        "setup": await _analyze_setup_patterns(test_files),
        "organization": await _analyze_test_organization(test_files),
        "annotations": await _analyze_annotation_usage(test_files),
        "documentation": await _analyze_documentation_patterns(test_files),
    }

    return json.dumps(conventions, indent=2)


async def _analyze_naming_conventions(test_files: list[Path]) -> dict[str, Any]:
    """Analyze test method naming conventions."""
    naming_patterns = {
        "should_when": 0,
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

    # Determine dominant pattern
    total = sum(naming_patterns.values())
    dominant_pattern = max(naming_patterns, key=naming_patterns.get) if total > 0 else "unknown"

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
        max(assertion_styles, key=assertion_styles.get)
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


async def _analyze_test_organization(test_files: list[Path]) -> dict[str, Any]:
    """Analyze how tests are organized."""
    organization = {
        "avg_tests_per_file": 0,
        "uses_display_name": 0,
        "uses_tags": 0,
        "groups_by_method": 0,
        "groups_by_scenario": 0,
    }

    total_tests = 0

    for test_file in test_files:
        try:
            content = test_file.read_text(encoding="utf-8", errors="replace")

            # Count tests per file
            test_count = content.count("@Test")
            total_tests += test_count

            if "@DisplayName" in content:
                organization["uses_display_name"] += 1
            if "@Tag" in content:
                organization["uses_tags"] += 1

        except Exception:
            pass

    if test_files:
        organization["avg_tests_per_file"] = round(total_tests / len(test_files), 1)

    return organization


async def _analyze_annotation_usage(test_files: list[Path]) -> dict[str, Any]:
    """Analyze common test annotations used."""
    annotations = Counter()

    for test_file in test_files:
        try:
            content = test_file.read_text(encoding="utf-8", errors="replace")

            # Find all annotations
            found_annotations = re.findall(r"@(\w+)", content)
            annotations.update(found_annotations)

        except Exception:
            pass

    # Get most common test-related annotations
    test_annotations = [
        "Test",
        "BeforeEach",
        "AfterEach",
        "BeforeAll",
        "AfterAll",
        "Mock",
        "InjectMocks",
        "MockBean",
        "Spy",
        "Captor",
        "ParameterizedTest",
        "ValueSource",
        "CsvSource",
        "MethodSource",
        "DisplayName",
        "Nested",
        "Tag",
        "Disabled",
        "SpringBootTest",
        "WebMvcTest",
        "DataJpaTest",
        "ExtendWith",
    ]

    relevant = {k: annotations[k] for k in test_annotations if k in annotations}

    return {"common_annotations": dict(annotations.most_common(15)), "test_specific": relevant}


async def _analyze_documentation_patterns(test_files: list[Path]) -> dict[str, Any]:
    """Analyze test documentation patterns."""
    documentation = {
        "has_javadoc": 0,
        "has_comments": 0,
        "uses_display_name": 0,
        "avg_display_name_length": 0,
    }

    display_name_lengths = []

    for test_file in test_files:
        try:
            content = test_file.read_text(encoding="utf-8", errors="replace")

            if "/**" in content:
                documentation["has_javadoc"] += 1
            if "//" in content:
                documentation["has_comments"] += 1

            # Extract display names
            display_names = re.findall(r'@DisplayName\s*\(\s*"([^"]+)"\s*\)', content)
            if display_names:
                documentation["uses_display_name"] += 1
                display_name_lengths.extend(len(dn) for dn in display_names)

        except Exception:
            pass

    if display_name_lengths:
        documentation["avg_display_name_length"] = round(
            sum(display_name_lengths) / len(display_name_lengths), 1
        )

    return documentation
