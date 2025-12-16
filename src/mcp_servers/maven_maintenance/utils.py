"""
Shared utilities for Maven maintenance MCP tools.
"""

import shutil
import sys


def get_mvn_command() -> str:
    """
    Get the Maven command for the current platform.

    On Windows, Maven is typically installed as mvn.cmd, which asyncio
    subprocess cannot find without the .cmd extension.

    Returns:
        Path to Maven executable
    """
    if sys.platform == "win32":
        # On Windows, try mvn.cmd first, then mvn
        mvn_cmd = shutil.which("mvn.cmd") or shutil.which("mvn")
        if mvn_cmd:
            return mvn_cmd
        return "mvn.cmd"  # Fallback
    return "mvn"


__all__ = ["get_mvn_command"]
