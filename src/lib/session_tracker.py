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
STATUS_AWAITING_INPUT = "awaiting_input"

# Exit code used when a step pauses waiting for human input (sysexits-style).
# 78 maps to EX_CONFIG; we reuse it to signal "human action required" so a CI
# job can treat it as neutral rather than a hard failure.
EXIT_AWAITING_INPUT = 78

QUESTION_FILENAME = "question.json"
ANSWER_FILENAME = "answer.json"
ANSWER_CONSUMED_FILENAME = "answer.json.consumed"
GENERATION_CURSOR_FILENAME = "generation_cursor.json"


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
            "# TestBoost Configuration\n"
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


# ---------------------------------------------------------------------------
# Human-in-the-loop interruption (spike)
# ---------------------------------------------------------------------------


class AwaitingInputError(Exception):
    """Raised by a step when it needs human input to continue.

    The caller catches this and returns EXIT_AWAITING_INPUT so a CI runner
    can treat the job as neutral and post `question.json` to the MR.
    """

    def __init__(self, question_path: Path, step_name: str):
        self.question_path = question_path
        self.step_name = step_name
        super().__init__(f"{step_name} awaiting input — see {question_path}")


def emit_question(
    session_dir: str,
    step_name: str,
    payload: dict[str, Any],
    project_path: str | None = None,
    session_id: str | None = None,
) -> Path:
    """Write a structured, signed question.json and flip status to awaiting_input.

    The payload is a free-form dict but the caller SHOULD include:
      - "kind": short tag (e.g. "missing_business_context")
      - "subject": what the question is about (file, class, error)
      - "question": human-readable question text
      - "answer_schema": hint about the shape expected back in answer.json

    If project_path is supplied, the payload is HMAC-signed via
    integrity.sign_question() so a matching answer can be verified.
    Backwards-compatible: callers that don't pass project_path skip signing.
    """
    from src.lib.integrity import sign_question

    session_path = Path(session_dir)
    question_path = session_path / QUESTION_FILENAME

    enriched = dict(payload)
    enriched.setdefault("step", step_name)
    if session_id:
        enriched.setdefault("session_id", session_id)
    enriched.setdefault("created_at", _now_iso())

    # markdown_preview must be added BEFORE signing so it is included in
    # the HMAC and survives round-trip verification
    enriched["markdown_preview"] = _render_question_markdown(enriched)

    if project_path:
        enriched = sign_question(enriched, project_path)

    question_path.write_text(
        json.dumps(enriched, indent=2, default=str), encoding="utf-8"
    )

    update_step_file(
        session_dir,
        step_name,
        STATUS_AWAITING_INPUT,
        f"# {step_name} — awaiting input\n\n"
        f"**Question**: {enriched.get('question', '(no question text)')}\n\n"
        f"Resume with: `python -m testboost resume <project> "
        f"--answer-file <signed_answer.json>`\n",
        data={"question": enriched},
    )

    return question_path


def consume_answer(
    session_dir: str,
    answer_file: str | Path,
    project_path: str | None = None,
    ttl_hours: int | None = None,
) -> dict[str, Any]:
    """Load an answer payload, verify its signature against the pending question, mark it consumed.

    Reads answer_file, parses JSON, then:
      - if project_path is supplied, loads the session's question.json and
        verifies that the answer is correctly signed and not expired
      - writes the answer into the session as answer.json.consumed
      - deletes question.json so the session is no longer awaiting

    Returns the parsed payload (with question_id/signature fields preserved).

    Raises:
      - FileNotFoundError: answer_file does not exist
      - ValueError: malformed JSON or non-object payload
      - integrity.SignatureError: signature missing/invalid/tampered
      - integrity.ExpiredQuestionError: question is older than ttl_hours
    """
    from src.lib.integrity import QUESTION_TTL_HOURS_DEFAULT, verify_answer

    src_path = Path(answer_file)
    if not src_path.exists():
        raise FileNotFoundError(f"answer file not found: {src_path}")

    raw = src_path.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"answer file is not valid JSON: {e}") from e

    if not isinstance(payload, dict):
        raise ValueError("answer payload must be a JSON object at the top level")

    session_path = Path(session_dir)
    question_path = session_path / QUESTION_FILENAME

    if project_path:
        if not question_path.exists():
            raise ValueError(
                "no pending question in this session; cannot verify the answer"
            )
        question_payload = json.loads(question_path.read_text(encoding="utf-8"))
        verify_answer(
            payload,
            question_payload,
            project_path,
            ttl_hours=ttl_hours if ttl_hours is not None else QUESTION_TTL_HOURS_DEFAULT,
        )

    consumed_path = session_path / ANSWER_CONSUMED_FILENAME
    consumed_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    if question_path.exists():
        question_path.unlink()

    return payload


def _render_question_markdown(payload: dict[str, Any]) -> str:
    """Render an MR-comment-ready markdown preview of a question payload."""
    kind = payload.get("kind", "question")
    subject = payload.get("subject", {})
    question = payload.get("question", "(no question text)")
    answer_schema = payload.get("answer_schema", {})

    lines = [
        f"### 🤖 TestBoost needs input ({kind})",
        "",
        f"**Question**: {question}",
        "",
    ]
    if subject:
        lines.append("**Subject**:")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(subject, indent=2, default=str))
        lines.append("```")
        lines.append("")
    if answer_schema:
        lines.append("**Reply with this shape** (sign with `testboost sign-answer`):")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(answer_schema, indent=2, default=str))
        lines.append("```")
        lines.append("")
    qid = payload.get("question_id")
    if qid:
        lines.append(f"_Question ID: `{qid}`_")
    return "\n".join(lines)


# --- generation cursor helpers (per-file resumability) ---


def save_generation_cursor(
    session_dir: str,
    *,
    target_files: list[str],
    current_index: int,
    completed_files: list[str],
) -> Path:
    """Persist progress through the generate per-file loop."""
    path = Path(session_dir) / GENERATION_CURSOR_FILENAME
    path.write_text(
        json.dumps(
            {
                "target_files": target_files,
                "current_index": current_index,
                "completed_files": completed_files,
                "updated_at": _now_iso(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def load_generation_cursor(session_dir: str) -> dict[str, Any] | None:
    """Read the cursor, or None if no resume state exists."""
    path = Path(session_dir) / GENERATION_CURSOR_FILENAME
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def clear_generation_cursor(session_dir: str) -> None:
    """Drop the cursor file once generate has run to completion."""
    path = Path(session_dir) / GENERATION_CURSOR_FILENAME
    if path.exists():
        path.unlink()


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


def get_session_technology(session_dir: Path) -> str:
    """Read the technology field from session spec.md frontmatter.

    Args:
        session_dir: Path to the session directory.

    Returns:
        Technology identifier string. Returns 'java-spring' when the field
        is absent (backward compatibility for existing sessions).
    """
    spec_path = Path(session_dir) / "spec.md"
    if not spec_path.exists():
        return "java-spring"
    frontmatter = _parse_frontmatter(spec_path.read_text(encoding="utf-8"))
    return frontmatter.get("technology", "java-spring")


def set_session_technology(session_dir: Path, technology: str) -> None:
    """Write the technology field to session spec.md frontmatter.

    Args:
        session_dir: Path to the session directory.
        technology: Technology identifier to write (e.g. 'java-spring').
    """
    spec_path = Path(session_dir) / "spec.md"
    if not spec_path.exists():
        return
    content = spec_path.read_text(encoding="utf-8")
    if re.search(r"^technology:", content, re.MULTILINE):
        content = re.sub(r"(?m)^technology:.*$", f"technology: {technology}", content)
    else:
        # Insert before the closing --- of the frontmatter block
        content = re.sub(r"\n---\n\n", f"\ntechnology: {technology}\n---\n\n", content, count=1)
    spec_path.write_text(content, encoding="utf-8")


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
