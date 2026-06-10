# SPDX-License-Identifier: Apache-2.0
"""Helpers shared across CLI command modules."""

import json
import re
import sys
from pathlib import Path
from typing import Any

TESTBOOST_ROOT = Path(__file__).parent.parent.parent.parent


def _warn_maven_config_issue(
    maven_output: str,
    session_dir: str | None,
    project_path: str,
    logger,
) -> None:
    """Log an explicit user hint when Maven fails for non-test-file reasons.

    Called when mvn test-compile exits non-zero but none of the errors reference
    the generated test files — meaning the failure is likely a project config issue
    (missing profile, corporate repo, custom flags).
    """
    lines = [
        "",
        "WARNING: Maven compile failed, but errors don't reference any generated test file.",
        "  This usually means Maven needs additional flags (e.g. a -P profile, -D property,",
        "  or corporate Maven settings).",
        "",
        "  To fix:",
        "  1. Open the analysis.md for this session:",
    ]
    analysis_path = str(Path(session_dir) / "analysis.md") if session_dir else "<session_dir>/analysis.md"
    lines.append(f"       {analysis_path}")
    lines += [
        '  2. Find the JSON block and edit "maven_compile_cmd" / "maven_test_cmd".',
        '     Example: "mvn test-compile -q --no-transfer-progress -P my-profile"',
        "  3. Re-run: testboost generate && testboost validate",
        "",
        "  Maven output (last 30 lines):",
        "\n".join(maven_output.splitlines()[-30:]),
    ]
    for line in lines:
        logger.warn(line)
def _read_step_status(step_file: Path) -> str:
    """Read the status from a step markdown file's YAML frontmatter.

    Returns the status string (e.g. "completed", "failed", "in_progress")
    or "unknown" if the file cannot be parsed.
    """
    try:
        content = step_file.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if match:
            for line in match.group(1).split("\n"):
                if line.startswith("status:"):
                    return line.partition(":")[2].strip()
    except OSError:
        pass
    return "unknown"
def _extract_json_field(markdown_content: str, field_name: str) -> Any:
    """Extract a field from a JSON block in a markdown file.

    Looks for ```json blocks in the markdown and extracts the named field.
    """
    json_blocks = re.findall(r"```json\n(.*?)```", markdown_content, re.DOTALL)
    for block in json_blocks:
        try:
            data = json.loads(block)
            if field_name in data:
                return data[field_name]
        except json.JSONDecodeError:
            continue
    return None


def load_answer_for_step(
    session_dir: str,
    answer_file: str | None,
    project_path: str,
    logger,
) -> tuple[dict | None, int | None]:
    """Verify a HITL answer file for a step command.

    Verification only — the answer is finalized (question cleared, consumed
    marker written) by the caller once the answered work has succeeded, so a
    crashed resume can be retried with the same answer file.

    Returns (payload, None) on success or when no answer file was given,
    (None, exit_code) when the command must abort.
    """
    from src.lib.integrity import ExpiredQuestionError, SignatureError
    from src.lib.session_tracker import load_and_verify_answer

    if not answer_file:
        return None, None
    try:
        payload = load_and_verify_answer(
            session_dir, answer_file, project_path=project_path
        )
        logger.info(f"Loaded and verified answer payload from {answer_file}")
        return payload, None
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Cannot consume answer file: {e}")
        return None, 1
    except SignatureError as e:
        logger.error(f"Answer signature invalid: {e}")
        print(f"\nERROR: answer file rejected — {e}", file=sys.stderr)
        return None, 1
    except ExpiredQuestionError as e:
        logger.error(f"Answer expired: {e}")
        print(f"\nERROR: answer rejected — {e}", file=sys.stderr)
        return None, 1
