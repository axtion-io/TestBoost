"""Unit tests for unified diff generation utility.

Tests cover the generate_unified_diff() and is_binary_content() functions.
Feature: 006-file-modifications-api
"""

from src.lib.diff import generate_unified_diff, get_operation_type, is_binary_content


class TestGenerateUnifiedDiff:
    """Tests for generate_unified_diff() function."""

    def test_basic_modification(self):
        """T019: Should generate valid unified diff for file modification."""
        original = "line1\nline2\nline3\n"
        modified = "line1\nmodified line2\nline3\n"

        diff = generate_unified_diff(original, modified, "test.txt")

        # Should have diff header
        assert "--- a/test.txt" in diff
        assert "+++ b/test.txt" in diff
        # Should show the change
        assert "-line2" in diff
        assert "+modified line2" in diff

    def test_file_creation(self):
        """T020: Should generate diff with all additions for new file."""
        original = None
        modified = "new line 1\nnew line 2\nnew line 3\n"

        diff = generate_unified_diff(original, modified, "newfile.txt")

        # Should have diff header
        assert "--- a/newfile.txt" in diff
        assert "+++ b/newfile.txt" in diff
        # All lines should be additions
        assert "+new line 1" in diff
        assert "+new line 2" in diff
        assert "+new line 3" in diff
        # No deletions
        assert "-new line" not in diff

    def test_file_deletion(self):
        """T021: Should generate diff with all deletions for deleted file."""
        original = "deleted line 1\ndeleted line 2\ndeleted line 3\n"
        modified = None

        diff = generate_unified_diff(original, modified, "deleted.txt")

        # Should have diff header
        assert "--- a/deleted.txt" in diff
        assert "+++ b/deleted.txt" in diff
        # All lines should be deletions
        assert "-deleted line 1" in diff
        assert "-deleted line 2" in diff
        assert "-deleted line 3" in diff

    def test_file_modification_multiline(self):
        """T022: Should generate diff for complex file modification."""
        original = """package com.example;

public class Hello {
    public void sayHello() {
        System.out.println("Hello");
    }
}
"""
        modified = """package com.example;

public class Hello {
    public void sayHello() {
        System.out.println("Hello, World!");
    }

    public void sayGoodbye() {
        System.out.println("Goodbye");
    }
}
"""

        diff = generate_unified_diff(original, modified, "Hello.java")

        # Should have diff header
        assert "--- a/Hello.java" in diff
        assert "+++ b/Hello.java" in diff
        # Should show the modification (lines start with - or +)
        assert '-        System.out.println("Hello")' in diff
        assert '+        System.out.println("Hello, World!")' in diff
        # Should show new method added
        assert "+    public void sayGoodbye()" in diff

    def test_empty_to_empty(self):
        """Should handle empty files correctly."""
        diff = generate_unified_diff("", "", "empty.txt")
        # Empty diff for no changes
        assert diff == ""

    def test_identical_content(self):
        """Should return empty diff for identical content."""
        content = "same content\n"
        diff = generate_unified_diff(content, content, "same.txt")
        assert diff == ""

    def test_custom_context_lines(self):
        """Should respect context_lines parameter."""
        original = "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n"
        modified = "1\n2\n3\n4\nMODIFIED\n6\n7\n8\n9\n10\n"

        diff = generate_unified_diff(original, modified, "numbers.txt", context_lines=1)

        # With 1 line of context, should have fewer surrounding lines
        assert "--- a/numbers.txt" in diff
        assert "-5" in diff
        assert "+MODIFIED" in diff

    def test_handles_no_trailing_newline(self):
        """Should handle files without trailing newlines."""
        original = "line without newline"
        modified = "modified line"

        diff = generate_unified_diff(original, modified, "no_newline.txt")

        assert "--- a/no_newline.txt" in diff
        assert "+++ b/no_newline.txt" in diff


class TestIsBinaryContent:
    """Tests for is_binary_content() function."""

    def test_text_content_returns_false(self):
        """Should return False for plain text content."""
        text = "This is plain text content.\nWith multiple lines.\n"
        assert is_binary_content(text) is False

    def test_binary_with_null_bytes_returns_true(self):
        """Should return True for content with null bytes."""
        binary = "Some content\x00with null bytes"
        assert is_binary_content(binary) is True

    def test_empty_content_returns_false(self):
        """Should return False for empty content."""
        assert is_binary_content("") is False
        assert is_binary_content(None) is False

    def test_bytes_input(self):
        """Should handle bytes input correctly."""
        text_bytes = b"Plain text as bytes"
        assert is_binary_content(text_bytes) is False

        binary_bytes = b"Binary\x00content"
        assert is_binary_content(binary_bytes) is True

    def test_high_non_text_ratio(self):
        """Should detect content with high proportion of control characters."""
        # Create content with lots of control characters
        binary_like = "\x01\x02\x03\x04\x05normal text"
        # Depending on ratio, this might be detected as binary
        # The threshold is 0.3 (30%)
        result = is_binary_content(binary_like)
        # With 5 control chars out of ~16 chars, it's ~31% which exceeds threshold
        assert result is True

    def test_valid_whitespace_not_binary(self):
        """Should not flag content with tabs and newlines as binary."""
        text_with_whitespace = "Line 1\n\tIndented\r\nWindows line\t\ttabs"
        assert is_binary_content(text_with_whitespace) is False


class TestGetOperationType:
    """Tests for get_operation_type() function."""

    def test_create_operation(self):
        """Should return 'create' when original is None."""
        assert get_operation_type(None, "new content") == "create"

    def test_delete_operation(self):
        """Should return 'delete' when modified is None."""
        assert get_operation_type("old content", None) == "delete"

    def test_modify_operation(self):
        """Should return 'modify' when both have content."""
        assert get_operation_type("old", "new") == "modify"

    def test_both_none_returns_modify(self):
        """Should return 'modify' when both are None (edge case)."""
        assert get_operation_type(None, None) == "modify"
