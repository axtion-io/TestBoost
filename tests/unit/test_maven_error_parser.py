"""Unit tests for Maven error parser."""

from pathlib import Path

from src.lib.maven_error_parser import CompilationError, MavenErrorParser


class TestMavenErrorParser:
    """Test suite for MavenErrorParser."""

    def test_parse_incompatible_types_bigdecimal_to_double(self):
        """Test parsing of BigDecimal vs Double type error."""
        maven_output = """
[ERROR] /C:/path/to/BankingServiceImplTest.java:[341,39] incompatible types: java.math.BigDecimal cannot be converted to java.lang.Double
"""
        parser = MavenErrorParser()
        errors = parser.parse(maven_output)

        assert len(errors) == 1
        error = errors[0]
        assert error.error_type == "incompatible_types"
        assert error.line == 341
        assert error.column == 39
        assert error.actual_type == "java.math.BigDecimal"
        assert error.expected_type == "java.lang.Double"
        assert "Double literal" in error.suggestion
        assert "BigDecimal" in error.suggestion

    def test_parse_incompatible_types_string_to_integer(self):
        """Test parsing of String vs Integer type error."""
        maven_output = """
[ERROR] /path/to/Test.java:[100,20] incompatible types: java.lang.String cannot be converted to java.lang.Integer
"""
        parser = MavenErrorParser()
        errors = parser.parse(maven_output)

        assert len(errors) == 1
        error = errors[0]
        assert error.error_type == "incompatible_types"
        assert error.line == 100
        assert error.actual_type == "java.lang.String"
        assert error.expected_type == "java.lang.Integer"
        assert "without quotes" in error.suggestion

    def test_parse_cannot_find_symbol_builder(self):
        """Test parsing of missing builder() method error."""
        maven_output = """
[ERROR] /path/to/Test.java:[528,58] cannot find symbol
  symbol:   method builder()
  location: class com.example.TransferDetails
"""
        parser = MavenErrorParser()
        errors = parser.parse(maven_output)

        assert len(errors) == 1
        error = errors[0]
        assert error.error_type == "cannot_find_symbol"
        assert error.line == 528
        assert error.column == 58
        assert "builder()" in error.symbol
        assert "@Builder" in error.suggestion or "constructor" in error.suggestion

    def test_parse_cannot_find_symbol_method(self):
        """Test parsing of missing method error."""
        maven_output = """
[ERROR] /path/to/Test.java:[200,10] cannot find symbol
  symbol:   method someMethod(int)
  location: class com.example.MyClass
"""
        parser = MavenErrorParser()
        errors = parser.parse(maven_output)

        assert len(errors) == 1
        error = errors[0]
        assert error.error_type == "cannot_find_symbol"
        assert "method" in error.symbol.lower()

    def test_parse_package_does_not_exist(self):
        """Test parsing of package not found error."""
        maven_output = """
[ERROR] /path/to/Test.java:[5,10] package com.example.missing does not exist
"""
        parser = MavenErrorParser()
        errors = parser.parse(maven_output)

        assert len(errors) == 1
        error = errors[0]
        assert error.error_type == "package_does_not_exist"
        assert error.symbol == "com.example.missing"
        assert "dependency" in error.suggestion or "import" in error.suggestion

    def test_parse_multiple_errors(self):
        """Test parsing multiple errors from same output."""
        maven_output = """
[ERROR] /path/to/Test1.java:[100,20] incompatible types: java.math.BigDecimal cannot be converted to java.lang.Double
[ERROR] /path/to/Test1.java:[150,30] incompatible types: java.lang.String cannot be converted to java.lang.Integer
[ERROR] /path/to/Test2.java:[50,10] cannot find symbol
  symbol:   method builder()
  location: class com.example.Foo
"""
        parser = MavenErrorParser()
        errors = parser.parse(maven_output)

        assert len(errors) == 3
        assert errors[0].error_type == "incompatible_types"
        assert errors[1].error_type == "incompatible_types"
        assert errors[2].error_type == "cannot_find_symbol"

    def test_parse_no_errors(self):
        """Test parsing output with no errors."""
        maven_output = """
[INFO] Scanning for projects...
[INFO] BUILD SUCCESS
"""
        parser = MavenErrorParser()
        errors = parser.parse(maven_output)

        assert len(errors) == 0

    def test_format_for_llm_single_error(self):
        """Test LLM-formatted output for single error."""
        errors = [
            CompilationError(
                file_path=Path("BankingServiceImplTest.java"),
                line=341,
                column=39,
                error_type="incompatible_types",
                message="error message",
                actual_type="java.math.BigDecimal",
                expected_type="java.lang.Double",
                suggestion="Use Double literal instead of BigDecimal",
            )
        ]

        parser = MavenErrorParser()
        formatted = parser.format_for_llm(errors)

        assert "Compilation Errors" in formatted
        assert "BankingServiceImplTest.java" in formatted
        assert "Line 341:39" in formatted
        assert "BigDecimal" in formatted
        assert "Double" in formatted
        assert "Use Double literal" in formatted

    def test_format_for_llm_multiple_files(self):
        """Test LLM-formatted output groups by file."""
        errors = [
            CompilationError(
                file_path=Path("Test1.java"),
                line=100,
                column=20,
                error_type="incompatible_types",
                message="error 1",
                actual_type="BigDecimal",
                expected_type="Double",
                suggestion="Fix 1",
            ),
            CompilationError(
                file_path=Path("Test2.java"),
                line=200,
                column=30,
                error_type="cannot_find_symbol",
                message="error 2",
                symbol="builder()",
                suggestion="Fix 2",
            ),
        ]

        parser = MavenErrorParser()
        formatted = parser.format_for_llm(errors)

        assert "Test1.java" in formatted
        assert "Test2.java" in formatted
        assert "Error #1" in formatted

    def test_format_for_llm_no_errors(self):
        """Test LLM-formatted output when no errors."""
        parser = MavenErrorParser()
        formatted = parser.format_for_llm([])

        assert "No compilation errors" in formatted
        assert "successfully" in formatted.lower()

    def test_get_summary(self):
        """Test error summary generation."""
        errors = [
            CompilationError(
                file_path=Path("Test1.java"),
                line=100,
                column=20,
                error_type="incompatible_types",
                message="error 1",
            ),
            CompilationError(
                file_path=Path("Test1.java"),
                line=150,
                column=30,
                error_type="incompatible_types",
                message="error 2",
            ),
            CompilationError(
                file_path=Path("Test2.java"),
                line=200,
                column=10,
                error_type="cannot_find_symbol",
                message="error 3",
            ),
        ]

        parser = MavenErrorParser()
        summary = parser.get_summary(errors)

        assert summary["total_errors"] == 3
        assert summary["errors_by_type"]["incompatible_types"] == 2
        assert summary["errors_by_type"]["cannot_find_symbol"] == 1
        assert summary["errors_by_file"]["Test1.java"] == 2
        assert summary["errors_by_file"]["Test2.java"] == 1

    def test_type_fix_suggestion_bigdecimal_to_double(self):
        """Test specific suggestion for BigDecimal to Double conversion."""
        error = CompilationError(
            file_path=Path("Test.java"),
            line=100,
            column=20,
            error_type="incompatible_types",
            message="error",
            actual_type="java.math.BigDecimal",
            expected_type="java.lang.Double",
        )

        parser = MavenErrorParser()
        suggestion = parser._generate_type_fix_suggestion(error)

        assert "Double literal" in suggestion
        assert "123.45" in suggestion
        assert "BigDecimal" in suggestion

    def test_type_fix_suggestion_string_to_integer(self):
        """Test specific suggestion for String to Integer conversion."""
        error = CompilationError(
            file_path=Path("Test.java"),
            line=100,
            column=20,
            error_type="incompatible_types",
            message="error",
            actual_type="java.lang.String",
            expected_type="java.lang.Integer",
        )

        parser = MavenErrorParser()
        suggestion = parser._generate_type_fix_suggestion(error)

        assert "Integer literal" in suggestion or "without quotes" in suggestion
        assert "123" in suggestion

    def test_symbol_fix_suggestion_builder(self):
        """Test suggestion for missing builder() method."""
        error = CompilationError(
            file_path=Path("Test.java"),
            line=100,
            column=20,
            error_type="cannot_find_symbol",
            message="error",
            symbol="method builder()",
        )

        parser = MavenErrorParser()
        suggestion = parser._generate_symbol_fix_suggestion(error, "class Foo")

        assert "@Builder" in suggestion or "constructor" in suggestion

    def test_real_world_maven_output(self):
        """Test with real-world Maven output from BankApp."""
        maven_output = """
[INFO] Compiling 6 source files with javac [debug target 17] to target\\test-classes
[INFO] -------------------------------------------------------------
[ERROR] COMPILATION ERROR :
[INFO] -------------------------------------------------------------
[ERROR] /C:/Users/jfran/axtion/TestBoost/test-projects/BankApp/src/test/java/com/coding/exercise/bankapp/service/BankingServiceImplTest.java:[336,43] incompatible types: java.math.BigDecimal cannot be converted to java.lang.Double
[ERROR] /C:/Users/jfran/axtion/TestBoost/test-projects/BankApp/src/test/java/com/coding/exercise/bankapp/service/BankingServiceImplTest.java:[341,39] incompatible types: java.math.BigDecimal cannot be converted to java.lang.Double
[ERROR] /C:/Users/jfran/axtion/TestBoost/test-projects/BankApp/src/test/java/com/coding/exercise/bankapp/service/BankingServiceTest.java:[46,46] incompatible types: java.math.BigDecimal cannot be converted to java.lang.Double
[ERROR] /C:/Users/jfran/axtion/TestBoost/test-projects/BankApp/src/test/java/com/coding/exercise/bankapp/service/helper/BankingServiceHelperTest.java:[135,64] incompatible types: java.lang.String cannot be converted to java.lang.Integer
[ERROR] /C:/Users/jfran/axtion/TestBoost/test-projects/BankApp/src/test/java/com/coding/exercise/bankapp/service/helper/BankingServiceHelperTest.java:[528,58] cannot find symbol
  symbol:   method builder()
  location: class com.coding.exercise.bankapp.domain.TransferDetails
[INFO] 5 errors
"""
        parser = MavenErrorParser()
        errors = parser.parse(maven_output)

        assert len(errors) == 5

        # Check first error (BigDecimal to Double)
        assert errors[0].error_type == "incompatible_types"
        assert errors[0].line == 336
        assert errors[0].actual_type == "java.math.BigDecimal"
        assert errors[0].expected_type == "java.lang.Double"

        # Check last error (builder not found)
        assert errors[4].error_type == "cannot_find_symbol"
        assert "builder()" in errors[4].symbol

        # Test summary
        summary = parser.get_summary(errors)
        assert summary["total_errors"] == 5
        assert summary["errors_by_type"]["incompatible_types"] == 4
        assert summary["errors_by_type"]["cannot_find_symbol"] == 1
