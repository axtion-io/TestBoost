# SPDX-License-Identifier: Apache-2.0
"""Integrity token system for TestBoost CLI output.

Generates and verifies HMAC-SHA256 tokens that prove output was produced
by the TestBoost CLI and not fabricated by an LLM acting on its own.

Each TestBoost installation has a unique secret stored in
`.testboost/.tb_secret`. The CLI emits a token at the end of every
successful command, and the slash-command markdown files instruct the
calling LLM to verify the token's presence before proceeding.

Token format printed to stdout:
    [TESTBOOST_INTEGRITY:sha256=<hex_digest>:<step>:<session_id>:<timestamp>]

The LLM cannot forge this because it doesn't know the secret.
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from pathlib import Path

SECRET_FILE = ".tb_secret"
TOKEN_PREFIX = "[TESTBOOST_INTEGRITY:"
TOKEN_SUFFIX = "]"


def get_or_create_secret(project_path: str) -> str:
    """Get the installation secret, creating it if it doesn't exist.

    The secret is stored in `.testboost/.tb_secret` and is generated once
    per project initialization. It is git-ignored.

    Args:
        project_path: Path to the Java project with `.testboost/` directory.

    Returns:
        The hex-encoded secret string.
    """
    tb_dir = Path(project_path) / ".testboost"
    secret_path = tb_dir / SECRET_FILE

    if secret_path.exists():
        return secret_path.read_text(encoding="utf-8").strip()

    # Generate a new secret
    secret = secrets.token_hex(32)
    tb_dir.mkdir(parents=True, exist_ok=True)
    secret_path.write_text(secret, encoding="utf-8")

    # Ensure .tb_secret is in .gitignore
    _ensure_gitignored(tb_dir, SECRET_FILE)

    return secret


def generate_token(project_path: str, step: str, session_id: str) -> str:
    """Generate an integrity token for a successful CLI step.

    Args:
        project_path: Path to the Java project.
        step: Step name (init, analysis, coverage-gaps, generation, validation).
        session_id: The current session ID (e.g., "001-test-generation").

    Returns:
        The full token string including brackets.
    """
    secret = get_or_create_secret(project_path)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    payload = f"{step}:{session_id}:{timestamp}"
    digest = hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"{TOKEN_PREFIX}sha256={digest}:{payload}{TOKEN_SUFFIX}"


def verify_token(project_path: str, token_line: str) -> bool:
    """Verify an integrity token.

    Args:
        project_path: Path to the Java project.
        token_line: The full token string to verify.

    Returns:
        True if the token is valid, False otherwise.
    """
    if not token_line.startswith(TOKEN_PREFIX) or not token_line.endswith(TOKEN_SUFFIX):
        return False

    inner = token_line[len(TOKEN_PREFIX):-len(TOKEN_SUFFIX)]

    # Expected format: sha256=<digest>:<step>:<session_id>:<timestamp>
    if not inner.startswith("sha256="):
        return False

    parts = inner[len("sha256="):].split(":", 3)
    if len(parts) != 4:
        return False

    claimed_digest, step, session_id, timestamp = parts
    payload = f"{step}:{session_id}:{timestamp}"

    secret = get_or_create_secret(project_path)
    expected_digest = hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(claimed_digest, expected_digest)


def emit_token(project_path: str, step: str, session_id: str) -> str:
    """Generate and print the integrity token to stdout.

    This should be called at the very end of a successful CLI command.

    Args:
        project_path: Path to the Java project.
        step: Step name.
        session_id: Session ID.

    Returns:
        The generated token string.
    """
    token = generate_token(project_path, step, session_id)
    print(f"\n{token}")
    return token


def _ensure_gitignored(tb_dir: Path, filename: str) -> None:
    """Make sure the file is in .testboost/.gitignore."""
    gitignore = tb_dir / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        if filename not in content:
            with open(gitignore, "a", encoding="utf-8") as f:
                f.write(f"\n# TestBoost installation secret (never commit)\n{filename}\n")
    else:
        gitignore.write_text(
            f"# TestBoost installation secret (never commit)\n{filename}\n",
            encoding="utf-8",
        )
