# SPDX-License-Identifier: Apache-2.0
"""Markdown-based session tracking.

Replaces the PostgreSQL/SQLAlchemy session management with simple
markdown files organized in a .testboost/ directory.

A session = a directory under .testboost/sessions/ containing:
  - spec.md          : What to test and why (user intent)
  - analysis.md      : Project analysis results
  - coverage-gaps.md : Identified test coverage gaps
  - generation.md    : Test generation results
  - validation.md    : Compilation + test run results
  - logs/            : Detailed logs per step
"""

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TESTBOOST_DIR = ".testboost"
SESSIONS_DIR = "sessions"

# Step names in order
STEPS = ["analysis", "coverage-gaps", "generation", "validation", "mutation", "killer-tests"]

# Frontmatter status values
STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


def get_testboost_dir(project_path: str) -> Path:
    """Get the .testboost directory for a project."""
    return Path(project_path) / TESTBOOST_DIR


def get_sessions_dir(project_path: str) -> Path:
    """Get the sessions directory."""
    return get_testboost_dir(project_path) / SESSIONS_DIR


def init_project(project_path: str) -> dict[str, Any]:
    """Initialize .testboost/ in a project.

    Creates the directory structure and config file.

    Returns:
        Dict with initialization results.
    """
    tb_dir = get_testboost_dir(project_path)
    sessions_dir = get_sessions_dir(project_path)

    tb_dir.mkdir(parents=True, exist_ok=True)
    sessions_dir.mkdir(parents=True, exist_ok=True)

    # Create config.yaml if it doesn't exist
    config_path = tb_dir / "config.yaml"
    if not config_path.exists():
        config_path.write_text(
            "# TestBoost Lite Configuration\n"
            "# Override these values as needed\n"
            "\n"
            "coverage_target: 80\n"
            "max_complexity: 20\n"
            "mock_framework: mockito\n"
            "assertion_library: assertj\n"
            "max_correction_retries: 3\n"
            "test_timeout_seconds: 300\n",
            encoding="utf-8",
        )

    # Create .gitignore for logs
    gitignore_path = tb_dir / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text(
            "# Ignore detailed logs (they can be large)\n"
            "sessions/*/logs/*.md\n",
            encoding="utf-8",
        )

    return {
        "success": True,
        "testboost_dir": str(tb_dir),
        "message": f"Initialized .testboost/ in {project_path}",
    }


def create_session(project_path: str, name: str | None = None, description: str = "") -> dict[str, Any]:
    """Create a new test generation session.

    A session is a numbered directory under .testboost/sessions/
    with a spec.md file describing the intent.

    Args:
        project_path: Path to the Java project
        name: Short name for the session (auto-generated if None)
        description: Description of what to test and why

    Returns:
        Dict with session info including the session_id and path.
    """
    sessions_dir = get_sessions_dir(project_path)
    sessions_dir.mkdir(parents=True, exist_ok=True)

    # Determine next session number
    existing = sorted(sessions_dir.iterdir()) if sessions_dir.exists() else []
    existing_nums = []
    for d in existing:
        if d.is_dir():
            match = re.match(r"^(\d+)-", d.name)
            if match:
                existing_nums.append(int(match.group(1)))

    next_num = max(existing_nums, default=0) + 1

    # Build session directory name
    if not name:
        name = "test-generation"
    safe_name = re.sub(r"[^a-z0-9-]", "-", name.lower().strip())
    safe_name = re.sub(r"-+", "-", safe_name).strip("-")
    session_id = f"{next_num:03d}-{safe_name}"

    session_dir = sessions_dir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "logs").mkdir(exist_ok=True)

    # Write spec.md
    now = _now_iso()
    spec_content = _make_frontmatter(
        status=STATUS_IN_PROGRESS,
        started_at=now,
        step="init",
    )
    spec_content += f"# Test Generation Session: {session_id}\n\n"
    spec_content += f"**Project**: `{os.path.abspath(project_path)}`\n"
    spec_content += f"**Created**: {now}\n\n"
    spec_content += "## Intent\n\n"
    spec_content += description if description else "_Generate tests for this Java project._\n"
    spec_content += "\n\n## Progress\n\n"
    spec_content += "| Step | Status | Started | Completed |\n"
    spec_content += "|------|--------|---------|-----------|\n"
    for step in STEPS:
        spec_content += f"| {step} | {STATUS_PENDING} | - | - |\n"
    spec_content += "\n"

    (session_dir / "spec.md").write_text(spec_content, encoding="utf-8")

    return {
        "success": True,
        "session_id": session_id,
        "session_dir": str(session_dir),
        "message": f"Created session {session_id}",
    }


def get_current_session(project_path: str) -> dict[str, Any] | None:
    """Get the most recent (or only active) session.

    Returns:
        Dict with session info, or None if no sessions exist.
    """
    sessions_dir = get_sessions_dir(project_path)
    if not sessions_dir.exists():
        return None

    existing = sorted(
        [d for d in sessions_dir.iterdir() if d.is_dir()],
        key=lambda d: d.name,
        reverse=True,
    )

    if not existing:
        return None

    session_dir = existing[0]
    session_id = session_dir.name

    # Read spec.md frontmatter
    spec_path = session_dir / "spec.md"
    if not spec_path.exists():
        return None

    frontmatter = _parse_frontmatter(spec_path.read_text(encoding="utf-8"))

    return {
        "session_id": session_id,
        "session_dir": str(session_dir),
        "status": frontmatter.get("status", STATUS_PENDING),
        "step": frontmatter.get("step", "init"),
        "started_at": frontmatter.get("started_at", ""),
    }


def update_step_file(
    session_dir: str,
    step_name: str,
    status: str,
    content: str,
    data: dict[str, Any] | None = None,
) -> Path:
    """Write or update a step's markdown file.

    Args:
        session_dir: Path to the session directory
        step_name: Step name (analysis, coverage-gaps, generation, validation)
        status: Step status
        content: Markdown content for the step
        data: Optional structured data to include as JSON block

    Returns:
        Path to the written file.
    """
    session_path = Path(session_dir)
    now = _now_iso()

    md = _make_frontmatter(
        status=status,
        step=step_name,
        updated_at=now,
        started_at=now if status == STATUS_IN_PROGRESS else None,
        completed_at=now if status in (STATUS_COMPLETED, STATUS_FAILED) else None,
    )
    md += content

    if data:
        md += "\n\n## Raw Data\n\n"
        md += "```json\n"
        md += json.dumps(data, indent=2, default=str)
        md += "\n```\n"

    file_path = session_path / f"{step_name}.md"
    file_path.write_text(md, encoding="utf-8")

    # Update the progress table in spec.md
    _update_spec_progress(session_path, step_name, status, now)

    return file_path


def write_log(session_dir: str, step_name: str, level: str, message: str, **kwargs: Any) -> None:
    """Append a log entry to the session's log file.

    Logs are written to .testboost/sessions/<id>/logs/<date>.md
    in a structured, readable format.

    Args:
        session_dir: Path to the session directory
        step_name: Current step name
        level: Log level (INFO, WARN, ERROR, DEBUG)
        message: Log message
        **kwargs: Additional structured data
    """
    logs_dir = Path(session_dir) / "logs"
    logs_dir.mkdir(exist_ok=True)

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    log_file = logs_dir / f"{today}.md"

    now = datetime.now(UTC).strftime("%H:%M:%S")
    entry = f"| {now} | {level:<5} | {step_name:<15} | {message}"

    if kwargs:
        details = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        entry += f" | {details}"
    entry += " |\n"

    # Create header if file is new
    if not log_file.exists():
        header = f"# Logs - {today}\n\n"
        header += "| Time | Level | Step | Message | Details |\n"
        header += "|------|-------|------|---------|---------|\n"
        log_file.write_text(header, encoding="utf-8")

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry)


def get_session_status(project_path: str) -> str:
    """Get a human-readable summary of the current session status.

    Returns a markdown-formatted string suitable for display.
    """
    session = get_current_session(project_path)
    if not session:
        return "No active session found. Run `/testboost.init` first."

    session_dir = Path(session["session_dir"])
    spec_path = session_dir / "spec.md"

    if not spec_path.exists():
        return f"Session {session['session_id']} exists but has no spec.md."

    lines = []
    lines.append(f"## Session: {session['session_id']}")
    lines.append(f"**Status**: {session['status']}")
    lines.append(f"**Started**: {session.get('started_at', 'unknown')}")
    lines.append("")

    # Check each step file
    lines.append("### Steps")
    lines.append("")
    lines.append("| Step | Status | File |")
    lines.append("|------|--------|------|")

    for step in STEPS:
        step_file = session_dir / f"{step}.md"
        if step_file.exists():
            fm = _parse_frontmatter(step_file.read_text(encoding="utf-8"))
            status = fm.get("status", "unknown")
            lines.append(f"| {step} | {status} | {step}.md |")
        else:
            lines.append(f"| {step} | pending | - |")

    lines.append("")

    # Show recent logs
    logs_dir = session_dir / "logs"
    if logs_dir.exists():
        log_files = sorted(logs_dir.glob("*.md"), reverse=True)
        if log_files:
            latest_log = log_files[0]
            log_content = latest_log.read_text(encoding="utf-8")
            # Get last 10 log lines
            log_lines = [ln for ln in log_content.split("\n") if ln.startswith("|") and not ln.startswith("| Time") and not ln.startswith("|---")]
            if log_lines:
                lines.append("### Recent Logs")
                lines.append("")
                lines.append("| Time | Level | Step | Message | Details |")
                lines.append("|------|-------|------|---------|---------| ")
                for log_line in log_lines[-10:]:
                    lines.append(log_line)
                lines.append("")

    return "\n".join(lines)


# --- Private helpers ---

def _now_iso() -> str:
    """Get current time as ISO string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_frontmatter(**kwargs: Any) -> str:
    """Create YAML frontmatter block."""
    lines = ["---"]
    for key, value in kwargs.items():
        if value is not None:
            lines.append(f"{key}: {value}")
    lines.append("---\n\n")
    return "\n".join(lines)


def _parse_frontmatter(content: str) -> dict[str, str]:
    """Parse YAML frontmatter from markdown content."""
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}

    fm = {}
    for line in match.group(1).split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()
    return fm


def _update_spec_progress(session_dir: Path, step_name: str, status: str, timestamp: str) -> None:
    """Update the progress table in spec.md."""
    spec_path = session_dir / "spec.md"
    if not spec_path.exists():
        return

    content = spec_path.read_text(encoding="utf-8")

    # Update the step row in the progress table
    # Match: | step_name | old_status | old_started | old_completed |
    pattern = rf"\| {re.escape(step_name)} \| \S+ \| [^|]+ \| [^|]+ \|"

    if status == STATUS_IN_PROGRESS:
        replacement = f"| {step_name} | {status} | {timestamp} | - |"
    elif status in (STATUS_COMPLETED, STATUS_FAILED):
        replacement = f"| {step_name} | {status} | - | {timestamp} |"
    else:
        replacement = f"| {step_name} | {status} | - | - |"

    new_content = re.sub(pattern, replacement, content)

    # Also update the frontmatter step
    new_content = re.sub(r"(?<=step: )\S+", step_name, new_content)

    if status in (STATUS_COMPLETED, STATUS_FAILED) and step_name == "validation":
        new_content = re.sub(r"(?<=status: )\S+", status, new_content)

    spec_path.write_text(new_content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Project-level analysis (shared across sessions)
# ---------------------------------------------------------------------------

_PROJECT_ANALYSIS_FILE = "analysis.md"


def get_project_analysis_path(project_path: str) -> Path:
    """Return the path to the project-level analysis.md file.

    This file lives at .testboost/analysis.md (NOT under sessions/).
    It is built by `cmd_analyze` and shared across all sessions.
    """
    return get_testboost_dir(project_path) / _PROJECT_ANALYSIS_FILE


def write_project_analysis(project_path: str, content: str, data: dict[str, Any]) -> Path:
    """Write the project-level analysis.md file.

    Analogous to update_step_file() but writes to .testboost/analysis.md
    (not under a session directory).

    Args:
        project_path: Path to the Java project root.
        content: Markdown body content (without frontmatter or JSON block).
        data: Structured data dict (class_index, conventions, etc.).

    Returns:
        Path to the written file.
    """
    analysis_path = get_project_analysis_path(project_path)
    now = _now_iso()

    md = _make_frontmatter(status=STATUS_COMPLETED, updated_at=now)
    md += content
    md += "\n\n## Raw Data\n\n"
    md += "```json\n"
    md += json.dumps(data, indent=2, default=str)
    md += "\n```\n"

    analysis_path.write_text(md, encoding="utf-8")
    return analysis_path


def read_project_analysis_data(project_path: str) -> dict[str, Any] | None:
    """Read the structured data from the project-level analysis.md.

    Returns:
        The parsed JSON data dict, or None if the file doesn't exist
        or contains no valid JSON block (backward-compat: old sessions
        without a project-level analysis will get None and fall back to
        the session-level analysis.md).
    """
    analysis_path = get_project_analysis_path(project_path)
    if not analysis_path.exists():
        return None
    content = analysis_path.read_text(encoding="utf-8")
    blocks = re.findall(r"```json\n(.*?)```", content, re.DOTALL)
    for block in blocks:
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            continue
    return None
