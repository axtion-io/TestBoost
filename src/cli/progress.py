"""Cross-platform progress indicators for CLI.

Provides ASCII-safe progress indicators for Windows compatibility.
"""

import sys

from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn


def create_progress(console: Console | None = None) -> Progress:
    """Create a cross-platform Progress instance.

    Uses simple ASCII characters instead of Unicode spinners to avoid
    encoding issues on Windows terminals.

    Args:
        console: Optional Console instance. If None, creates a new one.

    Returns:
        Progress instance configured for the current platform.
    """
    if console is None:
        console = Console()

    # Use simple text-based progress without Unicode spinners
    return Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
        transient=False,  # Keep progress visible
    )


def is_windows() -> bool:
    """Check if running on Windows.

    Returns:
        True if on Windows platform.
    """
    return sys.platform.startswith("win")


# Unicode to ASCII replacements for Windows console compatibility
UNICODE_REPLACEMENTS = {
    "\u2192": "->",  # → rightwards arrow
    "\u2190": "<-",  # ← leftwards arrow
    "\u2194": "<->",  # ↔ left right arrow
    "\u2713": "[x]",  # ✓ check mark
    "\u2717": "[ ]",  # ✗ ballot x
    "\u2714": "[x]",  # ✔ heavy check mark
    "\u2716": "[X]",  # ✖ heavy multiplication x
    "\u2022": "*",  # • bullet
    "\u2023": ">",  # ‣ triangular bullet
    "\u2043": "-",  # ⁃ hyphen bullet
    "\u25cf": "*",  # ● black circle
    "\u25cb": "o",  # ○ white circle
    "\u25a0": "#",  # ■ black square
    "\u25a1": "[]",  # □ white square
    "\u2605": "*",  # ★ black star
    "\u2606": "*",  # ☆ white star
    "\u2026": "...",  # … horizontal ellipsis
    "\u2014": "--",  # — em dash
    "\u2013": "-",  # – en dash
    "\u201c": '"',  # " left double quotation mark
    "\u201d": '"',  # " right double quotation mark
    "\u2018": "'",  # ' left single quotation mark
    "\u2019": "'",  # ' right single quotation mark
}


def sanitize_for_console(text: str) -> str:
    """Sanitize text for console output, replacing problematic Unicode characters.

    On Windows, the default cp1252 encoding doesn't support many Unicode characters.
    This function replaces common Unicode characters with ASCII equivalents.

    Args:
        text: Text that may contain Unicode characters

    Returns:
        Text with problematic characters replaced by ASCII equivalents
    """
    if not is_windows():
        return text

    result = text
    for unicode_char, ascii_replacement in UNICODE_REPLACEMENTS.items():
        result = result.replace(unicode_char, ascii_replacement)

    # For any remaining non-ASCII characters, replace with '?'
    # This is a safety net for characters we haven't mapped
    try:
        result.encode("cp1252")
    except UnicodeEncodeError:
        # Replace remaining problematic characters
        result = result.encode("cp1252", errors="replace").decode("cp1252")

    return result
