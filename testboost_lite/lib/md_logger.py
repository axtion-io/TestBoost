# SPDX-License-Identifier: Apache-2.0
"""Markdown-based logger that writes both to stdout and to log files.

This replaces the structlog-based logging system with something
that produces human-readable output for both the LLM CLI and
the markdown log files.

Design decisions:
- stdout gets a concise summary (what the LLM sees)
- The .md log file gets full details (what the user can review)
- Structured data is preserved as JSON blocks in the log
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from testboost_lite.lib.session_tracker import write_log


class MdLogger:
    """Logger that writes to both stdout and markdown files.

    Provides a dual-output logging system:
    - Concise stdout messages for the LLM CLI to consume
    - Detailed markdown log entries for user review

    Args:
        session_dir: Path to the session directory (for log files)
        step_name: Current workflow step name
        verbose: If True, also print detailed info to stdout
    """

    def __init__(self, session_dir: str, step_name: str, verbose: bool = False):
        self.session_dir = session_dir
        self.step_name = step_name
        self.verbose = verbose
        self._entries: list[dict[str, Any]] = []

    def info(self, message: str, **kwargs: Any) -> None:
        """Log an info message."""
        self._log("INFO", message, **kwargs)

    def warn(self, message: str, **kwargs: Any) -> None:
        """Log a warning message."""
        self._log("WARN", message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log an error message."""
        self._log("ERROR", message, **kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log a debug message (only to file, not stdout)."""
        write_log(self.session_dir, self.step_name, "DEBUG", message, **kwargs)
        self._entries.append({"level": "DEBUG", "message": message, **kwargs})

    def result(self, title: str, content: str) -> None:
        """Log a result block - always shown on stdout.

        Use this for key outputs the LLM should see and act on.
        """
        print(f"\n## {title}\n", file=sys.stdout)
        print(content, file=sys.stdout)
        print("", file=sys.stdout)
        write_log(self.session_dir, self.step_name, "INFO", f"[RESULT] {title}")

    def data(self, label: str, data: dict[str, Any] | list[Any]) -> None:
        """Log structured data - written to file, summary to stdout."""
        write_log(self.session_dir, self.step_name, "INFO", f"[DATA] {label}", entries=len(data) if isinstance(data, list) else "object")

        if self.verbose:
            print(f"\n### {label}\n", file=sys.stdout)
            print(f"```json\n{json.dumps(data, indent=2, default=str)}\n```\n", file=sys.stdout)
        else:
            if isinstance(data, list):
                print(f"  {label}: {len(data)} entries", file=sys.stdout)
            elif isinstance(data, dict):
                print(f"  {label}: {len(data)} fields", file=sys.stdout)

    def summary(self) -> str:
        """Get a concise summary of all logged entries.

        Returns a markdown string suitable for the LLM to read.
        """
        errors = [e for e in self._entries if e["level"] == "ERROR"]
        warns = [e for e in self._entries if e["level"] == "WARN"]
        infos = [e for e in self._entries if e["level"] == "INFO"]

        parts = []
        parts.append(f"**Step**: {self.step_name}")
        parts.append(f"**Messages**: {len(infos)} info, {len(warns)} warnings, {len(errors)} errors")

        if errors:
            parts.append("\n**Errors**:")
            for e in errors:
                parts.append(f"- {e['message']}")

        if warns:
            parts.append("\n**Warnings**:")
            for w in warns:
                parts.append(f"- {w['message']}")

        return "\n".join(parts)

    def _log(self, level: str, message: str, **kwargs: Any) -> None:
        """Internal log method."""
        self._entries.append({"level": level, "message": message, **kwargs})

        # Write to markdown log file
        write_log(self.session_dir, self.step_name, level, message, **kwargs)

        # Print to stdout (concise format)
        prefix = {"INFO": " ", "WARN": "!", "ERROR": "X"}
        marker = prefix.get(level, "?")

        if level == "ERROR":
            print(f"[{marker}] {message}", file=sys.stderr)
        elif level == "WARN" or self.verbose:
            print(f"[{marker}] {message}", file=sys.stdout)
        elif level == "INFO":
            print(f"[{marker}] {message}", file=sys.stdout)


def get_log_path(session_dir: str) -> Path:
    """Get the path to today's log file."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return Path(session_dir) / "logs" / f"{today}.md"
