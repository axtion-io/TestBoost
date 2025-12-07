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
