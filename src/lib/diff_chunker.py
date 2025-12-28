"""Diff chunking logic (T009).

Splits large diffs into manageable chunks per FR-011.
Default chunk size is 500 lines.
"""

import re
from dataclasses import dataclass
from typing import Callable

from src.models.impact import DiffChunk


# Pattern to match file headers in unified diff
FILE_HEADER_PATTERN = re.compile(r"^diff --git a/(.+) b/(.+)$", re.MULTILINE)


def split_by_file(diff_content: str) -> list[tuple[str, str]]:
    """
    Split a unified diff into per-file sections.

    Args:
        diff_content: Full unified diff content

    Returns:
        List of (file_path, file_diff) tuples
    """
    if not diff_content.strip():
        return []

    # Find all file headers
    matches = list(FILE_HEADER_PATTERN.finditer(diff_content))

    if not matches:
        return []

    file_diffs: list[tuple[str, str]] = []

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(diff_content)
        file_path = match.group(2)  # Use the 'b/' path (new file name)
        file_diff = diff_content[start:end]
        file_diffs.append((file_path, file_diff))

    return file_diffs


def count_lines(diff_content: str) -> int:
    """
    Count the number of lines in a diff section.

    Args:
        diff_content: Diff content to count

    Returns:
        Number of lines
    """
    if not diff_content:
        return 0
    return len(diff_content.splitlines())


def chunk_diff(
    diff_content: str,
    max_lines: int = 500,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[DiffChunk]:
    """
    Split a large diff into chunks for processing.

    Per FR-011, chunks diffs exceeding max_lines into batches,
    respecting file boundaries where possible.

    Args:
        diff_content: Full unified diff content
        max_lines: Maximum lines per chunk (default: 500)
        progress_callback: Optional callback(chunk_index, total_chunks)

    Returns:
        List of DiffChunk objects
    """
    if not diff_content.strip():
        return []

    file_diffs = split_by_file(diff_content)

    if not file_diffs:
        # Single chunk for non-standard diff format
        return [
            DiffChunk(
                index=0,
                total_chunks=1,
                files=[],
                content=diff_content,
                line_count=count_lines(diff_content),
            )
        ]

    # Build chunks respecting file boundaries
    chunks: list[DiffChunk] = []
    current_files: list[str] = []
    current_content: list[str] = []
    current_lines = 0

    for file_path, file_diff in file_diffs:
        file_lines = count_lines(file_diff)

        # If adding this file exceeds limit and we have content, start new chunk
        if current_lines + file_lines > max_lines and current_content:
            chunks.append(
                DiffChunk(
                    index=len(chunks),
                    total_chunks=0,  # Will be updated after
                    files=current_files.copy(),
                    content="".join(current_content),
                    line_count=current_lines,
                )
            )
            current_files = []
            current_content = []
            current_lines = 0

        current_files.append(file_path)
        current_content.append(file_diff)
        current_lines += file_lines

    # Add final chunk
    if current_content:
        chunks.append(
            DiffChunk(
                index=len(chunks),
                total_chunks=0,
                files=current_files.copy(),
                content="".join(current_content),
                line_count=current_lines,
            )
        )

    # Update total_chunks in all chunks
    total = len(chunks)
    for chunk in chunks:
        # Create new chunk with correct total
        chunk_index = chunks.index(chunk)
        chunks[chunk_index] = DiffChunk(
            index=chunk.index,
            total_chunks=total,
            files=chunk.files,
            content=chunk.content,
            line_count=chunk.line_count,
        )

    # Call progress callback for each chunk
    if progress_callback:
        for chunk in chunks:
            progress_callback(chunk.index, total)

    return chunks


def is_large_diff(diff_content: str, threshold: int = 500) -> bool:
    """
    Check if a diff exceeds the chunking threshold.

    Args:
        diff_content: Diff content to check
        threshold: Line count threshold (default: 500)

    Returns:
        True if diff exceeds threshold
    """
    return count_lines(diff_content) > threshold
