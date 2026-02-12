"""Unit tests for test_generation_agent helper functions."""

from src.workflows.test_generation_agent import (
    _categorize_type_error,
    _try_fix_truncated_java,
    _validate_java_syntax,
)


class TestValidateJavaSyntax:
    """Tests for _validate_java_syntax."""

    def test_valid_java_class(self):
        code = """
public class FooTest {
    @Test
    void testFoo() {
        assertEquals(1, 1);
    }
}"""
        is_valid, error = _validate_java_syntax(code)
        assert is_valid
        assert error is None

    def test_unbalanced_braces(self):
        code = """
public class FooTest {
    @Test
    void testFoo() {
        assertEquals(1, 1);
"""
        is_valid, error = _validate_java_syntax(code)
        assert not is_valid
        assert "Unbalanced braces" in error

    def test_unbalanced_parentheses(self):
        code = """
public class FooTest {
    @Test
    void testFoo() {
        assertEquals(1, 1;
    }
}"""
        is_valid, error = _validate_java_syntax(code)
        assert not is_valid
        assert "Unbalanced parentheses" in error

    def test_class_not_closed(self):
        code = """public class FooTest {
    @Test
    void testFoo() {
        assertEquals(1, 1);
    }
// missing final brace"""
        is_valid, error = _validate_java_syntax(code)
        assert not is_valid

    def test_empty_code(self):
        is_valid, _ = _validate_java_syntax("")
        # No class keyword, passes basic checks
        assert is_valid


class TestTryFixTruncatedJava:
    """Tests for _try_fix_truncated_java."""

    def test_adds_missing_closing_braces(self):
        code = "public class Foo {\n    void bar() {\n"
        fixed = _try_fix_truncated_java(code)
        assert fixed.count("{") == fixed.count("}")

    def test_no_change_when_balanced(self):
        code = "public class Foo {\n    void bar() {\n    }\n}\n"
        fixed = _try_fix_truncated_java(code)
        assert fixed.count("{") == fixed.count("}")
        assert fixed.count("}") == 2

    def test_single_missing_brace(self):
        code = "public class Foo {\n}"
        # Already balanced
        fixed = _try_fix_truncated_java(code)
        assert fixed.count("{") == fixed.count("}")

    def test_multiple_missing_braces(self):
        code = "class A { class B { void c() {"
        fixed = _try_fix_truncated_java(code)
        assert fixed.count("{") == fixed.count("}")
        assert fixed.count("}") == 3


class TestCategorizeTypeError:
    """Tests for _categorize_type_error."""

    def test_bigdecimal_double_mismatch(self):
        error = "incompatible types: java.lang.Double cannot be converted to java.math.BigDecimal"
        result = _categorize_type_error(error)
        assert result is not None
        assert result["category"] == "bigdecimal_double_mismatch"

    def test_string_integer_mismatch(self):
        error = "incompatible types: java.lang.String cannot be converted to java.lang.Integer"
        result = _categorize_type_error(error)
        assert result is not None
        assert result["category"] == "string_integer_mismatch"

    def test_method_parameter_mismatch(self):
        error = "method setBalance in class Account cannot be applied to given types"
        result = _categorize_type_error(error)
        assert result is not None
        assert result["category"] == "method_parameter_type_mismatch"

    def test_builder_not_found(self):
        error = "cannot find symbol: method builder()"
        result = _categorize_type_error(error)
        assert result is not None
        assert result["category"] == "builder_not_found"

    def test_private_access(self):
        error = "id has private access in Customer"
        result = _categorize_type_error(error)
        assert result is not None
        assert result["category"] == "private_field_access"

    def test_symbol_not_found(self):
        error = "cannot find symbol: variable fooBar"
        result = _categorize_type_error(error)
        assert result is not None
        assert result["category"] == "symbol_not_found"

    def test_array_collection_mismatch(self):
        error = "incompatible types: java.util.List cannot be converted to array"
        result = _categorize_type_error(error)
        assert result is not None
        assert result["category"] == "array_collection_mismatch"

    def test_unrelated_error_returns_none(self):
        error = "some random error message"
        result = _categorize_type_error(error)
        assert result is None

    def test_not_visible_private_access(self):
        error = "getName() is not visible"
        result = _categorize_type_error(error)
        assert result is not None
        assert result["category"] == "private_field_access"

    def test_string_int_primitive_mismatch(self):
        error = "incompatible types: java.lang.String cannot be converted to int"
        result = _categorize_type_error(error)
        assert result is not None
        assert result["category"] == "string_integer_mismatch"
