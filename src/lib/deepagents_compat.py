r"""
DeepAgents compatibility patches for Windows.

DeepAgents' FilesystemMiddleware rejects Windows absolute paths (C:\...)
but we need to support them for MCP tools on Windows. This module
patches the path validation to allow Windows paths.

IMPORTANT: This module must be imported early in the application startup,
before any other module imports DeepAgents.
"""

import os
import re
import sys

# Only apply patch on Windows
if sys.platform == "win32":
    try:
        from deepagents.middleware import filesystem

        # Save original function for reference
        _original_validate_path = filesystem._validate_path

        def _patched_validate_path(path: str, *, allowed_prefixes=None) -> str:
            """Patched version that allows Windows absolute paths."""
            # Reject path traversal for security
            if ".." in path:
                msg = f"Path traversal not allowed: {path}"
                raise ValueError(msg)

            # Normalize the path
            normalized = os.path.normpath(path)
            normalized = normalized.replace("\\", "/")

            # Add leading slash for relative paths (DeepAgents expects Unix-style)
            if not normalized.startswith("/") and not re.match(r"^[a-zA-Z]:", normalized):
                normalized = f"/{normalized}"

            # Check allowed prefixes if specified
            if allowed_prefixes is not None:
                prefix_match = any(normalized.startswith(prefix) for prefix in allowed_prefixes)
                # Allow Windows absolute paths (C:, D:, etc.) even if not in allowed_prefixes
                windows_path = re.match(r"^[a-zA-Z]:", path)

                if not prefix_match and not windows_path:
                    msg = f"Path must start with one of {allowed_prefixes}: {path}"
                    raise ValueError(msg)

            return normalized

        # Apply patch
        filesystem._validate_path = _patched_validate_path
        _patched = True

    except ImportError:
        # DeepAgents not installed
        _patched = False
    except Exception as e:
        # Patch failed - log but don't crash
        print(f"[deepagents_compat] Warning: Patch failed: {e}")
        _patched = False
else:
    _patched = False


def is_patched() -> bool:
    """Check if DeepAgents has been patched for Windows compatibility."""
    return _patched


__all__ = ["is_patched"]
