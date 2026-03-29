# SPDX-License-Identifier: Apache-2.0
"""Java test generation utilities.

This module contains stateless utility functions used for Java test validation,
Maven output parsing, and error categorization.

NOTE: The original LangGraph workflow (run_test_generation_with_agent) has been
removed — it was never reachable from the CLI and duplicated functionality already
covered by the MCP tools + CLI layer. The three Java discovery helpers
(_find_source_files, classify_source_file, find_existing_test) have been moved
to src/lib/java_discovery.py.
"""

import re
import shutil
from pathlib import Path
from typing import Any

from src.lib.logging import get_logger

logger = get_logger(__name__)


class TestGenerationError(Exception):
    """Base exception for test generation errors."""

    def __init__(self, message: str = "Test generation failed", source_file: str | None = None):
        if source_file:
            message = f"{message} for {source_file}"
        super().__init__(message)
        self.source_file = source_file


class CompilationError(TestGenerationError):
    """Raised when generated tests fail to compile."""

    def __init__(
        self,
        message: str = "Generated tests failed to compile",
        test_file: str | None = None,
        errors: list[str] | None = None,
    ):
        if test_file:
            message = f"{message}: {test_file}"
        if errors:
            message = f"{message}. Errors: {'; '.join(errors[:3])}"
        super().__init__(message)
        self.test_file = test_file
        self.errors = errors or []


def _get_maven_executable() -> str:
    """Get the Maven executable name for the current platform.

    On Windows, Maven is a .cmd script, so we need 'mvn.cmd'.
    On Linux/macOS, it's a shell script, so 'mvn' works.
    """
    mvn = shutil.which("mvn")
    if mvn is None:
        mvn = shutil.which("mvn.cmd")
        if mvn is None:
            return "mvn"
    return mvn


def _validate_java_syntax(code: str) -> tuple[bool, str | None]:
    """Validate Java code syntax for common truncation issues.

    Returns:
        Tuple of (is_valid, error_message)
    """
    open_braces = code.count("{")
    close_braces = code.count("}")
    if open_braces != close_braces:
        return False, f"Unbalanced braces: {open_braces} open, {close_braces} close"

    open_parens = code.count("(")
    close_parens = code.count(")")
    if open_parens != close_parens:
        return False, f"Unbalanced parentheses: {open_parens} open, {close_parens} close"

    if "class " in code and not code.rstrip().endswith("}"):
        return False, "Class declaration not properly closed (missing final })"

    last_line = code.strip().split("\n")[-1].strip()
    incomplete_patterns = [
        "assertThrows(",
        "assertEquals(",
        "assertTrue(",
        "assertFalse(",
        "assertNotNull(",
        "verify(",
        "when(",
        "throws ",
        "= ",
    ]
    for pattern in incomplete_patterns:
        if last_line.endswith(pattern) or (pattern in last_line and not last_line.endswith(";")):
            return False, f"Incomplete statement detected at end: '{last_line[:50]}...'"

    method_pattern = r"(@Test|@BeforeEach|@AfterEach|@ParameterizedTest)\s*\n\s*(?:public|private|protected)?\s*\w+\s+\w+\s*\([^)]*\)"
    for match in re.finditer(method_pattern, code):
        snippet = code[match.end():match.end() + 100]
        if "{" not in snippet:
            return False, f"Test method missing opening brace: {match.group()[:50]}"

    return True, None


def _is_valid_test_code(code: str) -> bool:
    """Check if code is valid Java test code."""
    if not ("class " in code and ("@Test" in code or "@ParameterizedTest" in code) and len(code) > 100):
        return False
    is_valid, error = _validate_java_syntax(code)
    if not is_valid:
        logger.warning("invalid_java_syntax", error=error, code_length=len(code))
        return False
    return True


def _extract_test_info(code: str) -> dict[str, Any] | None:
    """Extract test class info (name, package, path) from Java code."""
    if not code:
        return None

    class_name = "GeneratedTest"
    package = ""

    for line in code.split("\n"):
        line = line.strip()
        if line.startswith("package ") and ";" in line:
            package = line.replace("package ", "").replace(";", "").strip()
        if "class " in line and "{" in line:
            parts = line.split("class ")[1].split()
            if parts:
                class_name = parts[0].replace("{", "").strip()
            break

    if package:
        package_path = package.replace(".", "/")
        path = f"src/test/java/{package_path}/{class_name}.java"
    else:
        path = f"src/test/java/{class_name}.java"

    return {"path": path, "content": code, "class_name": class_name, "package": package}


def _extract_code_from_response(content: str) -> str | None:
    """Extract Java code from an LLM response (strips markdown fences)."""
    if "```java" in content:
        code_blocks = content.split("```java")
        if len(code_blocks) > 1:
            return code_blocks[1].split("```")[0].strip()
    return None


def _parse_test_failures(maven_output: str) -> list[dict[str, Any]]:
    """Parse Maven test output to extract failure information.

    Supports both Surefire 2.x and 3.x output formats.
    """
    failures: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    def _add_failure(failure: dict[str, Any]) -> None:
        cls = failure.get("class", "")
        method = failure.get("method", "")
        key = f"{cls}.{method}"
        if key != "." and key in seen_keys:
            if failure.get("stacktrace"):
                for f in failures:
                    if f.get("class", "") == cls and f.get("method") == method:
                        f["stacktrace"] = failure["stacktrace"]
                        break
            return
        if key != ".":
            seen_keys.add(key)
        failures.append(failure)

    # Surefire 3.x summary format
    surefire3_summary_pattern = re.compile(
        r"\[ERROR\]\s+(?:Errors|Failures):\s*\n((?:\[ERROR\]\s+.+\n)+)",
        re.MULTILINE,
    )
    surefire3_line_pattern = re.compile(
        r"\[ERROR\]\s+(\S+)\.(\w+):(\d+)\s+.{1,3}\s+(\w+(?:\.\w+)*)\s+(.*)"
    )

    for section_match in surefire3_summary_pattern.finditer(maven_output):
        for line in section_match.group(1).strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            line_match = surefire3_line_pattern.match(line)
            if line_match:
                _add_failure({
                    "type": "runtime",
                    "class": line_match.group(1),
                    "method": line_match.group(2),
                    "line": int(line_match.group(3)),
                    "error_type": line_match.group(4),
                    "error": line_match.group(5).strip(),
                })

    # Surefire 3.x stack trace blocks
    stacktrace_pattern = re.compile(
        r"\[ERROR\]\s+([\w.]+)\.([\w]+)\s+--\s+Time elapsed:.*?<<<\s+(?:ERROR|FAILURE)!\n"
        r"([\s\S]*?)(?=\n\[ERROR\]\s+\S+\.\S+\s+--|(?:\n\[INFO\])|\n\n)",
        re.MULTILINE,
    )

    for match in stacktrace_pattern.finditer(maven_output):
        class_name = match.group(1)
        method_name = match.group(2)
        stacktrace_block = match.group(3).strip()
        exception_line = stacktrace_block.split("\n")[0] if stacktrace_block else ""
        exc_match = re.match(r"([\w.]+(?:Exception|Error|Throwable)):\s*(.*)", exception_line)
        trace_lines = stacktrace_block.split("\n")
        limited_trace = "\n".join(trace_lines[:10])
        if len(trace_lines) > 10:
            limited_trace += f"\n    ... ({len(trace_lines) - 10} more lines)"

        key = f"{class_name}.{method_name}"
        if key in seen_keys:
            for f in failures:
                if f.get("class") == class_name and f.get("method") == method_name:
                    f["stacktrace"] = limited_trace
                    break
        else:
            _add_failure({
                "type": "runtime",
                "class": class_name,
                "method": method_name,
                "error_type": exc_match.group(1) if exc_match else "Unknown",
                "error": exc_match.group(2).strip() if exc_match else exception_line,
                "stacktrace": limited_trace,
            })

    # Surefire 2.x format
    failure_pattern = re.compile(
        r"(?:Failed tests?|Tests in error):\s*\n((?:\s+.+\n)+)",
        re.MULTILINE,
    )
    for match in failure_pattern.findall(maven_output):
        for line in match.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            test_match = re.match(r"(\w+)\(([^)]+)\):\s*(.+)", line)
            if test_match:
                _add_failure({
                    "type": "runtime",
                    "method": test_match.group(1),
                    "class": test_match.group(2),
                    "error": test_match.group(3),
                })

    # Compilation errors
    compile_error_pattern = re.compile(
        r"\[ERROR\]\s*(.+\.java):\[(\d+),(\d+)\]\s*(.+)",
        re.MULTILINE,
    )
    for match in compile_error_pattern.finditer(maven_output):
        error_msg = match.group(4)
        failure = {
            "type": "compilation",
            "file": match.group(1),
            "line": int(match.group(2)),
            "column": int(match.group(3)),
            "error": error_msg,
        }
        failure["jpa_error"] = _categorize_jpa_error(error_msg)
        failure["type_error"] = _categorize_type_error(error_msg)
        failures.append(failure)

    # Assertion failures
    assertion_pattern = re.compile(
        r"(org\.opentest4j\.\w+|java\.lang\.AssertionError):\s*(.+?)(?=\n\tat|\n\n|$)",
        re.DOTALL,
    )
    for match in assertion_pattern.finditer(maven_output):
        message = match.group(2).strip()
        if message and not any(f.get("error") == message for f in failures):
            failures.append({
                "type": "assertion",
                "error_type": match.group(1),
                "error": message,
            })

    return failures


def _categorize_jpa_error(error_msg: str) -> dict[str, Any] | None:
    """Categorize JPA-specific compilation errors and provide fix suggestions."""
    error_lower = error_msg.lower()

    if "cannot find symbol" in error_lower and "setid" in error_lower:
        return {
            "category": "generated_value_setid",
            "description": "Attempting to call setId() on a JPA entity with @GeneratedValue",
            "fix": 'Use ReflectionTestUtils.setField(entity, "id", value) instead of entity.setId(value)',
            "import_needed": "org.springframework.test.util.ReflectionTestUtils",
        }
    if "incompatible types" in error_lower and ("long" in error_lower or "integer" in error_lower):
        return {
            "category": "id_type_mismatch",
            "description": "Type mismatch between Long and Integer for ID field",
            "fix": "Use 1L for Long IDs, use 1 for Integer IDs. Check the entity's getId() return type.",
        }
    if "cannot find symbol" in error_lower and "optional" in error_lower:
        return {
            "category": "optional_misuse",
            "description": "Calling entity method directly on Optional<Entity> instead of extracted value",
            "fix": "Use optional.get().getProperty() or assertThat(optional).isPresent() then extract",
        }
    if ("incompatible types" in error_lower or "cannot find symbol" in error_lower) and (
        "date" in error_lower or "localdate" in error_lower
    ):
        return {
            "category": "date_type_mismatch",
            "description": "Using wrong date type (java.util.Date vs java.time.LocalDate)",
            "fix": "Check entity field type: use new Date() for java.util.Date, LocalDate.of() for LocalDate",
        }
    if "duplicate class" in error_lower:
        return {
            "category": "duplicate_class",
            "description": "Two test classes with the same name exist",
            "fix": "Delete one of the duplicate test files",
        }
    if "ambiguous" in error_lower and "assertequals" in error_lower:
        return {
            "category": "ambiguous_assertion",
            "description": "Ambiguous assertEquals call with boxed types",
            "fix": "Use AssertJ assertThat(actual).isEqualTo(expected) instead of assertEquals",
        }
    return None


def _categorize_type_error(error_msg: str) -> dict[str, Any] | None:
    """Categorize type-related compilation errors and provide fix suggestions."""
    error_lower = error_msg.lower()

    if "incompatible types" in error_lower and (
        "bigdecimal" in error_lower or "double" in error_lower
    ):
        return {
            "category": "bigdecimal_double_mismatch",
            "description": "Type mismatch between BigDecimal and Double",
            "fix": 'Use new BigDecimal("value") instead of Double. Never use double primitives with BigDecimal fields.',
            "example": 'new BigDecimal("100.00") instead of 100.0',
        }
    if "incompatible types" in error_lower and (
        ("string" in error_lower and "integer" in error_lower)
        or ("string" in error_lower and " int" in error_lower)
    ):
        return {
            "category": "string_integer_mismatch",
            "description": "Type mismatch between String and Integer",
            "fix": "Use Integer.parseInt(string) to convert String to Integer, or use string literals with quotes",
            "example": 'Use 123 (Integer) instead of "123" (String), or vice versa',
        }
    if "method" in error_lower and "cannot be applied to given types" in error_lower:
        return {
            "category": "method_parameter_type_mismatch",
            "description": "Method called with wrong parameter types",
            "fix": "Check the method signature and ensure parameter types match exactly",
        }
    if "cannot find symbol" in error_lower and "builder" in error_lower:
        return {
            "category": "builder_not_found",
            "description": "Builder pattern method not found on class",
            "fix": "Check if class has @Builder annotation (Lombok), or use constructor instead",
            "example": "Use new ClassName() constructor instead of ClassName.builder()",
        }
    if "has private access" in error_lower or "is not visible" in error_lower:
        return {
            "category": "private_field_access",
            "description": "Attempting to access private field directly",
            "fix": "Use getter method or ReflectionTestUtils.setField() for private fields in tests",
            "import_needed": "org.springframework.test.util.ReflectionTestUtils",
        }
    if "cannot find symbol" in error_lower:
        return {
            "category": "symbol_not_found",
            "description": "Variable, method, or class not found",
            "fix": "Check spelling, imports, and ensure the symbol exists in the source code",
        }
    if "incompatible types" in error_lower and ("list" in error_lower or "array" in error_lower):
        return {
            "category": "array_collection_mismatch",
            "description": "Type mismatch between array and collection",
            "fix": "Use Arrays.asList() to convert array to List, or toArray() to convert List to array",
        }
    return None


def _find_source_file_for_test(test_path: str, project_path: str) -> str | None:
    """Find the source file corresponding to a test file."""
    test_file = Path(test_path)
    test_class_name = test_file.stem

    source_class_name = test_class_name[:-4] if test_class_name.endswith("Test") else test_class_name

    source_path = test_path.replace("/test/", "/main/").replace("\\test\\", "\\main\\")
    source_path = source_path.replace(test_class_name + ".java", source_class_name + ".java")

    full_source_path = Path(project_path) / source_path
    if full_source_path.exists():
        return str(full_source_path.relative_to(project_path))
    return None


def _try_fix_truncated_java(code: str) -> str:
    """Attempt to fix Java code truncated by the LLM by adding missing closing braces."""
    missing = code.count("{") - code.count("}")
    if missing > 0:
        logger.info("auto_fixing_truncated_java", missing_braces=missing)
        code = code.rstrip()
        if not code.endswith("\n"):
            code += "\n"
        for _ in range(missing):
            code += "}\n"
    return code


__all__ = [
    "TestGenerationError",
    "CompilationError",
]
