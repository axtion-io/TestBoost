"""Unified diff generation utility for file modifications tracking.

This module provides functions to generate unified diffs and detect binary content.
Used by the file_modification artifact type (Feature 006).
"""

import difflib
from typing import Literal

# Binary detection: check for null bytes or high proportion of non-text bytes
BINARY_CHECK_SIZE = 8192
NON_TEXT_THRESHOLD = 0.3


def generate_unified_diff(
    original: str | None,
    modified: str | None,
    file_path: str,
    context_lines: int = 3,
) -> str:
    """Generate unified diff format from original and modified content.

    Args:
        original: Original file content (None for new files)
        modified: Modified file content (None for deleted files)
        file_path: Path to the file (used in diff headers)
        context_lines: Number of context lines around changes (default: 3)

    Returns:
        Unified diff string in standard format
    """
    original_lines = (original or "").splitlines(keepends=True)
    modified_lines = (modified or "").splitlines(keepends=True)

    # Ensure last line has newline for proper diff format
    if original_lines and not original_lines[-1].endswith("\n"):
        original_lines[-1] += "\n"
    if modified_lines and not modified_lines[-1].endswith("\n"):
        modified_lines[-1] += "\n"

    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        n=context_lines,
    )
    return "".join(diff)


def is_binary_content(content: str | bytes | None) -> bool:
    """Check if content appears to be binary (non-text).

    Binary detection uses two heuristics:
    1. Presence of null bytes
    2. High proportion of non-printable characters

    Args:
        content: Content to check (string or bytes)

    Returns:
        True if content appears to be binary
    """
    if content is None:
        return False

    # Convert to bytes if string
    if isinstance(content, str):
        try:
            data = content.encode("utf-8")
        except UnicodeEncodeError:
            return True
    else:
        data = content

    # Check only first chunk for performance
    sample = data[:BINARY_CHECK_SIZE]

    if not sample:
        return False

    # Null bytes indicate binary
    if b"\x00" in sample:
        return True

    # Count non-text bytes
    non_text_count = sum(
        1
        for byte in sample
        if byte < 32 and byte not in (9, 10, 13)  # tab, newline, carriage return
    )

    return (non_text_count / len(sample)) > NON_TEXT_THRESHOLD


def get_operation_type(
    original: str | None,
    modified: str | None,
) -> Literal["create", "modify", "delete"]:
    """Determine the operation type based on content.

    Args:
        original: Original content (None if file didn't exist)
        modified: Modified content (None if file was deleted)

    Returns:
        Operation type: 'create', 'modify', or 'delete'
    """
    if original is None and modified is not None:
        return "create"
    elif original is not None and modified is None:
        return "delete"
    else:
        return "modify"


__all__ = [
    "generate_unified_diff",
    "is_binary_content",
    "get_operation_type",
]
