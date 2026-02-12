"""Parser for Maven compilation errors with structured output.

This module extracts compilation errors from Maven output and provides
structured, actionable feedback for LLM-based error correction.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class CompilationError:
    """Structured representation of a Maven compilation error.

    Attributes:
        file_path: Path to the file with the error
        line: Line number of the error
        column: Column number of the error
        error_type: Type of error (incompatible_types, cannot_find_symbol, etc.)
        message: Full error message from Maven
        expected_type: Expected type (for type errors)
        actual_type: Actual type provided (for type errors)
        symbol: Symbol that couldn't be found (for symbol errors)
        suggestion: Human-readable fix suggestion
    """

    file_path: Path
    line: int
    column: int
    error_type: str
    message: str
    expected_type: str | None = None
    actual_type: str | None = None
    symbol: str | None = None
    suggestion: str | None = None


class MavenErrorParser:
    """Parse Maven compiler output to extract structured error information.

    This parser identifies common compilation errors and provides
    actionable suggestions for fixing them.

    Example:
        >>> parser = MavenErrorParser()
        >>> errors = parser.parse(maven_output)
        >>> for error in errors:
        ...     print(f"{error.file_path}:{error.line} - {error.suggestion}")
    """

    # Regex patterns for different error types
    PATTERNS = {
        "incompatible_types": re.compile(
            r"\[ERROR\]\s+(.+\.java):\[(\d+),(\d+)\]\s+incompatible types:\s+(.+?)\s+cannot be converted to\s+(.+?)(?:\n|$)",
            re.MULTILINE,
        ),
        "cannot_find_symbol": re.compile(
            r"\[ERROR\]\s+(/[^\[]+\.java|[A-Za-z]:\\[^\[]+\.java):\[(\d+),(\d+)\]\s+cannot find symbol\n\s+symbol:\s+(.+)\n\s+location:\s+(.+)",
            re.MULTILINE,
        ),
        "package_does_not_exist": re.compile(
            r"\[ERROR\]\s+(.+\.java):\[(\d+),(\d+)\]\s+package\s+(.+?)\s+does not exist",
            re.MULTILINE,
        ),
        "private_access": re.compile(
            r"\[ERROR\]\s+(.+\.java):\[(\d+),(\d+)\]\s+(\S+)\s+has private access in\s+(.+?)(?:\n|$)",
            re.MULTILINE,
        ),
        "cannot_find_symbol_simple": re.compile(
            r"\[ERROR\]\s+(.+\.java):\[(\d+),(\d+)\]\s+cannot find symbol(?:\n|$)",
            re.MULTILINE,
        ),
        "class_not_public": re.compile(
            r"\[ERROR\]\s+(.+\.java):\[(\d+),(\d+)\]\s+(.+?)\s+is not public",
            re.MULTILINE,
        ),
        "generic_error": re.compile(
            r"\[ERROR\]\s+(.+\.java):\[(\d+),(\d+)\]\s+(.+?)(?:\n|$)",
            re.MULTILINE,
        ),
    }

    def parse(self, maven_output: str) -> list[CompilationError]:
        """Parse Maven output to extract compilation errors.

        Args:
            maven_output: Raw output from mvn test-compile

        Returns:
            List of structured CompilationError objects (deduplicated)

        Example:
            >>> parser = MavenErrorParser()
            >>> output = "[ERROR] Test.java:[10,5] incompatible types: ..."
            >>> errors = parser.parse(output)
            >>> len(errors)
            1
        """
        errors = []
        seen = set()  # Track (file, line, column) to deduplicate

        logger.debug("parsing_maven_output", output_length=len(maven_output))

        # Parse incompatible types errors
        for match in self.PATTERNS["incompatible_types"].finditer(maven_output):
            key = (match.group(1), match.group(2), match.group(3))
            if key in seen:
                continue
            seen.add(key)
            error = CompilationError(
                file_path=Path(match.group(1)),
                line=int(match.group(2)),
                column=int(match.group(3)),
                error_type="incompatible_types",
                message=match.group(0).strip(),
                actual_type=match.group(4).strip(),
                expected_type=match.group(5).strip(),
            )
            error.suggestion = self._generate_type_fix_suggestion(error)
            errors.append(error)

        # Parse cannot find symbol errors (with symbol + location)
        for match in self.PATTERNS["cannot_find_symbol"].finditer(maven_output):
            key = (match.group(1), match.group(2), match.group(3))
            if key in seen:
                continue
            seen.add(key)
            symbol_info = match.group(4).strip()
            location_info = match.group(5).strip()

            error = CompilationError(
                file_path=Path(match.group(1)),
                line=int(match.group(2)),
                column=int(match.group(3)),
                error_type="cannot_find_symbol",
                message=match.group(0).strip(),
                symbol=symbol_info,
            )
            error.suggestion = self._generate_symbol_fix_suggestion(error, location_info)
            errors.append(error)

        # Parse cannot find symbol errors (simple - no symbol/location on same line)
        for match in self.PATTERNS["cannot_find_symbol_simple"].finditer(maven_output):
            key = (match.group(1), match.group(2), match.group(3))
            if key in seen:
                continue
            seen.add(key)
            error = CompilationError(
                file_path=Path(match.group(1)),
                line=int(match.group(2)),
                column=int(match.group(3)),
                error_type="cannot_find_symbol",
                message=match.group(0).strip(),
                symbol="unknown",
            )
            error.suggestion = "Check that the referenced class/method/variable exists and is imported correctly"
            errors.append(error)

        # Parse private access errors
        for match in self.PATTERNS["private_access"].finditer(maven_output):
            key = (match.group(1), match.group(2), match.group(3))
            if key in seen:
                continue
            seen.add(key)
            field_name = match.group(4).strip()
            class_name = match.group(5).strip()
            error = CompilationError(
                file_path=Path(match.group(1)),
                line=int(match.group(2)),
                column=int(match.group(3)),
                error_type="private_access",
                message=match.group(0).strip(),
                symbol=field_name,
            )
            error.suggestion = (
                f"Field `{field_name}` is private in `{class_name}`. "
                f"Use @InjectMocks or ReflectionTestUtils.setField() instead of direct field access. "
                f"Or use the getter/setter methods if available."
            )
            errors.append(error)

        # Parse package errors
        for match in self.PATTERNS["package_does_not_exist"].finditer(maven_output):
            key = (match.group(1), match.group(2), match.group(3))
            if key in seen:
                continue
            seen.add(key)
            error = CompilationError(
                file_path=Path(match.group(1)),
                line=int(match.group(2)),
                column=int(match.group(3)),
                error_type="package_does_not_exist",
                message=match.group(0).strip(),
                symbol=match.group(4).strip(),
            )
            error.suggestion = f"Add dependency for package {match.group(4)} or fix import statement"
            errors.append(error)

        # Parse any remaining generic errors not caught above
        for match in self.PATTERNS["generic_error"].finditer(maven_output):
            key = (match.group(1), match.group(2), match.group(3))
            if key in seen:
                continue
            seen.add(key)
            error_msg = match.group(4).strip()
            error = CompilationError(
                file_path=Path(match.group(1)),
                line=int(match.group(2)),
                column=int(match.group(3)),
                error_type="other",
                message=error_msg,
            )
            error.suggestion = f"Fix the compilation error: {error_msg}"
            errors.append(error)

        logger.info(
            "maven_errors_parsed",
            total_errors=len(errors),
            error_types=[e.error_type for e in errors],
        )

        return errors

    def _generate_type_fix_suggestion(self, error: CompilationError) -> str:
        """Generate a fix suggestion for type incompatibility.

        Args:
            error: CompilationError with type information

        Returns:
            Human-readable suggestion for fixing the error
        """
        # Common type conversion fixes
        suggestions = {
            ("java.math.BigDecimal", "java.lang.Double"): (
                "Use Double literal instead of BigDecimal. "
                "Replace `new BigDecimal(\"123.45\")` with `123.45`"
            ),
            ("java.math.BigDecimal", "java.lang.Integer"): (
                "Use Integer literal instead of BigDecimal. "
                "Replace `new BigDecimal(\"123\")` with `123`"
            ),
            ("java.math.BigDecimal", "java.lang.Long"): (
                "Use Long literal instead of BigDecimal. "
                "Replace `new BigDecimal(\"123\")` with `123L`"
            ),
            ("java.lang.String", "java.lang.Integer"): (
                "Use Integer literal without quotes. "
                "Replace `\"123\"` with `123`"
            ),
            ("java.lang.String", "java.lang.Long"): (
                "Use Long literal without quotes. "
                "Replace `\"123\"` with `123L`"
            ),
            ("java.lang.Integer", "java.lang.Long"): (
                "Use Long literal. "
                "Replace `123` with `123L`"
            ),
        }

        key = (error.actual_type, error.expected_type)
        if key in suggestions:
            return suggestions[key]

        # Generic suggestion
        return (
            f"Convert {error.actual_type} to {error.expected_type}. "
            f"Check the method signature to see what type is expected."
        )

    def _generate_symbol_fix_suggestion(
        self, error: CompilationError, location: str
    ) -> str:
        """Generate a fix suggestion for missing symbols.

        Args:
            error: CompilationError with symbol information
            location: Location information from Maven error

        Returns:
            Human-readable suggestion for fixing the error
        """
        symbol = error.symbol.lower()

        if "method builder()" in symbol:
            return (
                "This class does not have a @Builder annotation. "
                "Use the constructor or setter methods instead of .builder()"
            )

        if "method" in symbol:
            method_name = symbol.split("method")[-1].strip()
            return (
                f"Method {method_name} does not exist. "
                f"Check the class API or use an existing method."
            )

        if "variable" in symbol or "class" in location.lower():
            return (
                f"Symbol '{error.symbol}' not found. "
                f"Check imports and ensure the class/variable is defined."
            )

        return f"Verify that '{error.symbol}' exists and is accessible in this context"

    def format_for_llm(self, errors: list[CompilationError]) -> str:
        """Format errors as structured prompt for LLM.

        Args:
            errors: List of CompilationError objects

        Returns:
            Markdown-formatted error list with suggestions for LLM consumption

        Example:
            >>> parser = MavenErrorParser()
            >>> formatted = parser.format_for_llm(errors)
            >>> print(formatted)
            # Compilation Errors to Fix
            ...
        """
        if not errors:
            return "No compilation errors found. All tests compile successfully."

        prompt = "# Compilation Errors Detected\n\n"
        prompt += f"**Total errors**: {len(errors)}\n\n"
        prompt += "The following compilation errors must be fixed:\n\n"

        # Group by file for better organization
        errors_by_file = {}
        for error in errors:
            file_key = str(error.file_path.name)
            if file_key not in errors_by_file:
                errors_by_file[file_key] = []
            errors_by_file[file_key].append(error)

        for file_name, file_errors in sorted(errors_by_file.items()):
            prompt += f"## File: {file_name}\n\n"

            for i, error in enumerate(file_errors, 1):
                prompt += f"### Error #{i} - Line {error.line}:{error.column}\n\n"

                if error.error_type == "incompatible_types":
                    prompt += "**Issue**: Type mismatch\n\n"
                    prompt += f"- **You used**: `{error.actual_type}`\n"
                    prompt += f"- **Expected**: `{error.expected_type}`\n\n"
                    prompt += f"**How to fix**: {error.suggestion}\n\n"

                elif error.error_type == "cannot_find_symbol":
                    prompt += "**Issue**: Symbol not found\n\n"
                    prompt += f"- **Symbol**: `{error.symbol}`\n\n"
                    prompt += f"**How to fix**: {error.suggestion}\n\n"

                elif error.error_type == "package_does_not_exist":
                    prompt += "**Issue**: Package not found\n\n"
                    prompt += f"- **Package**: `{error.symbol}`\n\n"
                    prompt += f"**How to fix**: {error.suggestion}\n\n"

                elif error.error_type == "private_access":
                    prompt += "**Issue**: Private field access\n\n"
                    prompt += f"- **Field**: `{error.symbol}`\n\n"
                    prompt += f"**How to fix**: {error.suggestion}\n\n"

                else:
                    prompt += f"**Issue**: {error.message}\n\n"
                    prompt += f"**How to fix**: {error.suggestion}\n\n"

                prompt += "---\n\n"

        prompt += "\n## CRITICAL Instructions\n\n"
        prompt += "1. Fix **ALL** errors listed above\n"
        prompt += "2. Use the **EXACT** types specified (not approximations)\n"
        prompt += "3. Apply the suggested fixes precisely\n"
        prompt += "4. Return the **COMPLETE** corrected file(s)\n"
        prompt += "5. Do NOT introduce new errors while fixing these\n\n"

        return prompt

    def get_summary(self, errors: list[CompilationError]) -> dict:
        """Get a summary of errors for logging/metrics.

        Args:
            errors: List of CompilationError objects

        Returns:
            Dictionary with error statistics

        Example:
            >>> summary = parser.get_summary(errors)
            >>> summary["total_errors"]
            26
        """
        summary = {
            "total_errors": len(errors),
            "errors_by_type": {},
            "errors_by_file": {},
        }

        for error in errors:
            # Count by type
            error_type = error.error_type
            summary["errors_by_type"][error_type] = (
                summary["errors_by_type"].get(error_type, 0) + 1
            )

            # Count by file
            file_name = str(error.file_path.name)
            summary["errors_by_file"][file_name] = (
                summary["errors_by_file"].get(file_name, 0) + 1
            )

        return summary


__all__ = ["MavenErrorParser", "CompilationError"]
