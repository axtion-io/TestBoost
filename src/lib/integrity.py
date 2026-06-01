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
import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SECRET_FILE = ".tb_secret"
TOKEN_PREFIX = "[TESTBOOST_INTEGRITY:"
TOKEN_SUFFIX = "]"

QUESTION_TTL_HOURS_DEFAULT = 24


class SignatureError(Exception):
    """Raised when a question or answer signature is invalid."""


class ExpiredQuestionError(Exception):
    """Raised when an answer arrives after the question's TTL has elapsed."""


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


def _canonical_json(payload: dict[str, Any]) -> str:
    """Stable JSON encoding for HMAC signing.

    Sort keys and strip whitespace so the same logical payload always
    produces the same byte string.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _hmac_hex(secret: str, message: str) -> str:
    return hmac.new(
        secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def sign_question(payload: dict[str, Any], project_path: str) -> dict[str, Any]:
    """Sign a question payload.

    Adds `question_id` (16-byte hex nonce) and `created_at` if missing,
    then appends a `signature` field. The signature covers every field
    except `signature` itself. Returns a new dict; the input is not mutated.
    """
    enriched = dict(payload)
    enriched.setdefault("question_id", secrets.token_hex(16))
    enriched.setdefault(
        "created_at", datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    content = {k: v for k, v in enriched.items() if k != "signature"}
    secret = get_or_create_secret(project_path)
    enriched["signature"] = _hmac_hex(secret, _canonical_json(content))
    return enriched


def verify_question(payload: dict[str, Any], project_path: str) -> bool:
    """Return True iff `payload` carries a valid HMAC signature."""
    if "signature" not in payload:
        return False
    content = {k: v for k, v in payload.items() if k != "signature"}
    secret = get_or_create_secret(project_path)
    expected = _hmac_hex(secret, _canonical_json(content))
    return hmac.compare_digest(payload["signature"], expected)


def sign_answer(
    payload: dict[str, Any], question: dict[str, Any], project_path: str
) -> dict[str, Any]:
    """Bind an answer to a question and sign it.

    The answer payload is augmented with the question's `question_id`,
    then signed under the same HMAC secret. Returns a new dict.
    """
    if "question_id" not in question:
        raise SignatureError("question has no question_id; cannot bind an answer")
    enriched = dict(payload)
    enriched["question_id"] = question["question_id"]
    content = {k: v for k, v in enriched.items() if k != "signature"}
    secret = get_or_create_secret(project_path)
    enriched["signature"] = _hmac_hex(secret, _canonical_json(content))
    return enriched


def verify_answer(
    answer: dict[str, Any],
    question: dict[str, Any],
    project_path: str,
    ttl_hours: int = QUESTION_TTL_HOURS_DEFAULT,
) -> None:
    """Verify an answer against the question it claims to respond to.

    Raises SignatureError if any of these conditions fail:
      - question payload is tampered (signature mismatch)
      - answer.question_id != question.question_id
      - answer.signature is missing or doesn't match the answer content
    Raises ExpiredQuestionError if the question is older than ttl_hours.
    """
    if not verify_question(question, project_path):
        raise SignatureError("question signature is invalid (payload was tampered)")
    if answer.get("question_id") != question.get("question_id"):
        raise SignatureError(
            "answer.question_id does not match question.question_id"
        )
    if "signature" not in answer:
        raise SignatureError("answer is missing a signature")

    content = {k: v for k, v in answer.items() if k != "signature"}
    secret = get_or_create_secret(project_path)
    expected = _hmac_hex(secret, _canonical_json(content))
    if not hmac.compare_digest(answer["signature"], expected):
        raise SignatureError("answer signature does not match its content")

    created = question.get("created_at")
    if not created:
        return
    try:
        ts = datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as e:
        raise SignatureError(f"question created_at is malformed: {created}") from e
    if datetime.now(UTC) - ts > timedelta(hours=ttl_hours):
        raise ExpiredQuestionError(
            f"question expired (created {created}, TTL {ttl_hours}h)"
        )


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
