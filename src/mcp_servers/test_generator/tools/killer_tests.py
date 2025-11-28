"""
Generate killer tests tool.

Generates tests specifically designed to kill surviving mutants
based on mutation testing analysis.
"""

import json
import re
from pathlib import Path


async def generate_killer_tests(
    project_path: str,
    surviving_mutants: list[dict],
    source_file: str | None = None,
    max_tests: int = 10,
) -> str:
    """
    Generate tests to kill surviving mutants.

    Args:
        project_path: Path to the Java project root directory
        surviving_mutants: List of surviving mutants to target
        source_file: Path to the source file with surviving mutants
        max_tests: Maximum number of killer tests to generate

    Returns:
        JSON string with generated killer test code
    """
    project_dir = Path(project_path)

    if not project_dir.exists():
        return json.dumps(
            {"success": False, "error": f"Project path does not exist: {project_path}"}
        )

    if not surviving_mutants:
        return json.dumps({"success": False, "error": "No surviving mutants provided"})

    # Group mutants by class
    by_class = {}
    for mutant in surviving_mutants[:max_tests]:
        class_name = mutant.get("class", "")
        if class_name not in by_class:
            by_class[class_name] = []
        by_class[class_name].append(mutant)

    # Generate killer tests for each class
    generated_tests = []

    for class_name, mutants in by_class.items():
        # Find source file if not provided
        if source_file:
            src_path = Path(source_file)
        else:
            src_path = _find_source_file(project_dir, class_name)

        if src_path and src_path.exists():
            source_code = src_path.read_text(encoding="utf-8", errors="replace")
        else:
            source_code = None

        # Generate test code
        test_code = _generate_killer_test_class(class_name, mutants, source_code)

        test_file_path = _get_killer_test_path(project_dir, class_name)

        generated_tests.append(
            {
                "class": class_name,
                "test_file": str(test_file_path),
                "test_code": test_code,
                "mutants_targeted": len(mutants),
            }
        )

    results = {
        "success": True,
        "generated_tests": generated_tests,
        "total_tests": sum(t["mutants_targeted"] for t in generated_tests),
        "total_mutants_targeted": len(surviving_mutants[:max_tests]),
    }

    return json.dumps(results, indent=2)


def _find_source_file(project_dir: Path, class_name: str) -> Path | None:
    """Find source file for a class."""
    # Convert class name to file path
    class_path = class_name.replace(".", "/") + ".java"

    # Search in common source directories
    search_paths = [
        project_dir / "src" / "main" / "java" / class_path,
        project_dir / "src" / class_path,
    ]

    for path in search_paths:
        if path.exists():
            return path

    return None


def _get_killer_test_path(project_dir: Path, class_name: str) -> Path:
    """Generate killer test file path."""
    # Convert class name to path
    parts = class_name.split(".")
    parts[-1] = f"{parts[-1]}KillerTest.java"

    return project_dir / "src" / "test" / "java" / Path(*parts)


def _generate_killer_test_class(
    class_name: str, mutants: list[dict], source_code: str | None
) -> str:
    """Generate killer test class for surviving mutants."""
    # Extract package and simple class name
    parts = class_name.rsplit(".", 1)
    package = parts[0] if len(parts) > 1 else ""
    simple_name = parts[-1]

    # Build imports
    imports = []
    if package:
        imports.append(f"package {package};")
        imports.append("")

    imports.extend(
        [
            "import org.junit.jupiter.api.Test;",
            "import org.junit.jupiter.api.DisplayName;",
            "import org.junit.jupiter.api.BeforeEach;",
            "import static org.assertj.core.api.Assertions.*;",
            "import static org.mockito.Mockito.*;",
            "",
        ]
    )

    # Build test class
    test_class_name = f"{simple_name}KillerTest"

    class_body = [
        f'@DisplayName("Killer Tests for {simple_name}")',
        f"class {test_class_name} {{",
        "",
        f"    private {simple_name} {_to_camel_case(simple_name)};",
        "",
        "    @BeforeEach",
        "    void setUp() {",
        f"        {_to_camel_case(simple_name)} = new {simple_name}();",
        "    }",
        "",
    ]

    # Generate a test for each mutant
    for i, mutant in enumerate(mutants):
        test_methods = _generate_killer_test_method(mutant, simple_name, i + 1, source_code)
        class_body.extend(test_methods)

    class_body.append("}")

    return "\n".join(imports + class_body)


def _generate_killer_test_method(
    mutant: dict, class_name: str, index: int, source_code: str | None
) -> list[str]:
    """Generate a killer test for a specific mutant."""
    method = mutant.get("method", "unknownMethod")
    line = mutant.get("line", 0)
    mutator = mutant.get("mutator", "").split(".")[-1]
    description = mutant.get("description", "")
    instance = _to_camel_case(class_name)

    # Determine test strategy based on mutator type
    test_strategy = _get_kill_strategy(mutator, description)

    test_name = f"shouldKillMutant{index}_{_sanitize_method_name(method)}_line{line}"
    display_name = f"Kill mutant: {method} line {line} ({mutator})"

    test_code = [
        "    @Test",
        f'    @DisplayName("{display_name}")',
        f"    void {test_name}() {{",
        f"        // Target: {description}",
        f"        // Strategy: {test_strategy['strategy']}",
        "",
        "        // Arrange",
        f"        {test_strategy['arrange']}",
        "",
        "        // Act",
        f"        var result = {instance}.{method}({test_strategy['params']});",
        "",
        "        // Assert - specifically targets the mutation",
        f"        {test_strategy['assert']}",
        "    }",
        "",
    ]

    return test_code


def _get_kill_strategy(mutator: str, description: str) -> dict[str, str]:
    """Get test strategy to kill a specific mutator type."""
    strategies = {
        "ConditionalsBoundaryMutator": {
            "strategy": "Test boundary conditions",
            "arrange": "// Set up boundary value test case",
            "params": "/* boundary value */",
            "assert": "// Verify exact boundary behavior\n        assertThat(result).isEqualTo(/* expected boundary result */);",
        },
        "NegateConditionalsMutator": {
            "strategy": "Test both branches of conditional",
            "arrange": "// Set up to trigger specific branch",
            "params": "/* value that triggers specific branch */",
            "assert": "// Verify correct branch was taken\n        assertThat(result).isEqualTo(/* expected for this branch */);",
        },
        "MathMutator": {
            "strategy": "Verify exact mathematical result",
            "arrange": "// Set up values where math operations differ",
            "params": "/* values where +1 vs -1 matters */",
            "assert": "// Verify exact calculation result\n        assertThat(result).isEqualTo(/* exact expected value */);",
        },
        "IncrementsMutator": {
            "strategy": "Verify increment/decrement operations",
            "arrange": "// Set up counter/index test",
            "params": "",
            "assert": "// Verify exact count/index value\n        assertThat(result).isEqualTo(/* expected after increment */);",
        },
        "ReturnValuesMutator": {
            "strategy": "Verify actual return value not just type",
            "arrange": "// Set up specific return value scenario",
            "params": "",
            "assert": "// Verify actual value, not just non-null\n        assertThat(result).isEqualTo(/* specific expected value */);",
        },
        "VoidMethodCallMutator": {
            "strategy": "Verify side effects of void method",
            "arrange": "// Set up to detect side effects",
            "params": "",
            "assert": "// Verify side effects occurred\n        // Check state changes, mock interactions, etc.",
        },
        "EmptyReturnValuesMutator": {
            "strategy": "Verify non-empty return value",
            "arrange": "// Set up non-empty return scenario",
            "params": "",
            "assert": "// Verify return is not empty\n        assertThat(result).isNotEmpty();",
        },
        "NullReturnValuesMutator": {
            "strategy": "Verify non-null return value",
            "arrange": "// Set up non-null return scenario",
            "params": "",
            "assert": "// Verify return is not null\n        assertThat(result).isNotNull();",
        },
        "BooleanTrueReturnValsMutator": {
            "strategy": "Verify false return scenario",
            "arrange": "// Set up false return scenario",
            "params": "/* input that should return false */",
            "assert": "// Verify returns false\n        assertThat(result).isFalse();",
        },
        "BooleanFalseReturnValsMutator": {
            "strategy": "Verify true return scenario",
            "arrange": "// Set up true return scenario",
            "params": "/* input that should return true */",
            "assert": "// Verify returns true\n        assertThat(result).isTrue();",
        },
    }

    # Default strategy if mutator not found
    default = {
        "strategy": f"Target {mutator}",
        "arrange": "// Set up test data",
        "params": "",
        "assert": f"// Verify behavior affected by {mutator}\n        assertThat(result).isNotNull();",
    }

    return strategies.get(mutator, default)


def _to_camel_case(name: str) -> str:
    """Convert PascalCase to camelCase."""
    if not name:
        return name
    return name[0].lower() + name[1:]


def _sanitize_method_name(name: str) -> str:
    """Sanitize method name for use in test method name."""
    # Remove special characters and ensure valid Java identifier
    sanitized = re.sub(r"[^a-zA-Z0-9]", "", name)
    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized
    return sanitized or "method"
