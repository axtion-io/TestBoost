# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the GitLab integration shell scripts.

We don't actually hit GitLab — we substitute curl via the TB_CURL_BIN
env var and assert what payloads/URLs the scripts would call.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_POST = REPO_ROOT / "scripts" / "gitlab" / "post_question_to_mr.sh"
SCRIPT_FETCH = REPO_ROOT / "scripts" / "gitlab" / "fetch_answer_from_mr.sh"


def _make_mock_curl(tmp_path: Path, capture_file: Path, response_body: str) -> Path:
    """Create a mock 'curl' shell script that captures its invocation."""
    mock = tmp_path / "mock_curl.sh"
    mock.write_text(
        f"""#!/usr/bin/env bash
# Mock curl: records args + STDIN to {capture_file}, prints fixed response
{{
  echo "ARGS: $@"
  if [ -t 0 ]; then
    echo "STDIN: (empty)"
  fi
}} >> "{capture_file}"
# For requests with --data, the data is in the args; for streaming bodies via stdin
# we'd capture differently. For our purposes args are enough.
printf '{response_body}'
exit 0
"""
    )
    mock.chmod(mock.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return mock


def _make_session_with_question(tmp_path: Path, question: dict) -> Path:
    """Create a fake .testboost/sessions/001-x/ with the given question.json."""
    sdir = tmp_path / ".testboost" / "sessions" / "001-test"
    sdir.mkdir(parents=True)
    (sdir / "question.json").write_text(json.dumps(question))
    return sdir


def _have_jq() -> bool:
    return shutil.which("jq") is not None


# ---------------------------------------------------------------------------
# post_question_to_mr.sh
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _have_jq(), reason="jq is required by the script")
class TestPostQuestion:
    def test_posts_markdown_preview_with_question_id(self, tmp_path):
        capture = tmp_path / "curl.log"
        capture.touch()
        mock_curl = _make_mock_curl(tmp_path, capture, '{"id":42}')

        sdir = _make_session_with_question(tmp_path, {
            "question_id": "abc123",
            "markdown_preview": "### Question\n\nFix the test.",
        })

        env = os.environ.copy()
        env.update({
            "CI_PROJECT_ID": "100",
            "CI_MERGE_REQUEST_IID": "7",
            "CI_API_V4_URL": "https://gitlab.example.com/api/v4",
            "GITLAB_TOKEN": "secret",
            "TB_CURL_BIN": str(mock_curl),
            "TB_SESSION_DIR": str(sdir),
        })
        res = subprocess.run(
            ["bash", str(SCRIPT_POST)],
            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=15,
        )
        assert res.returncode == 0, res.stderr

        log = capture.read_text()
        # URL ends with notes endpoint
        assert "/projects/100/merge_requests/7/notes" in log
        # PRIVATE-TOKEN header passed
        assert "PRIVATE-TOKEN: secret" in log
        # Body includes the preview + question_id marker
        assert "Fix the test." in log
        assert "testboost:question_id=abc123" in log

    def test_fails_when_no_question(self, tmp_path):
        # No session at all
        env = os.environ.copy()
        env.update({
            "CI_PROJECT_ID": "100",
            "CI_MERGE_REQUEST_IID": "7",
            "GITLAB_TOKEN": "secret",
            "TB_SESSION_DIR": str(tmp_path / "nonexistent"),
        })
        res = subprocess.run(
            ["bash", str(SCRIPT_POST)],
            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=15,
        )
        assert res.returncode != 0


# ---------------------------------------------------------------------------
# fetch_answer_from_mr.sh
# ---------------------------------------------------------------------------


def _make_fetch_mock_curl(tmp_path: Path, mr_response: str, notes_response: str) -> Path:
    """A mock curl that returns the MR or notes response depending on the URL."""
    mock = tmp_path / "fetch_mock_curl.sh"
    mock.write_text(
        f"""#!/usr/bin/env bash
url=""
for arg in "$@"; do
  case "$arg" in
    https://*) url="$arg";;
  esac
done
if [[ "$url" == *"/notes"* ]]; then
  cat <<'EOF'
{notes_response}
EOF
else
  cat <<'EOF'
{mr_response}
EOF
fi
exit 0
"""
    )
    mock.chmod(mock.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return mock


class TestFetchAnswer:
    def _signed_question(self, tmp_path: Path) -> dict:
        from src.lib.integrity import sign_question
        # Use tmp_path as the "project" so the .tb_secret lives there
        (tmp_path / ".testboost").mkdir(parents=True, exist_ok=True)
        return sign_question({"step": "generation", "kind": "x"}, str(tmp_path))

    def test_picks_only_author_comment_with_matching_qid(self, tmp_path):
        question = self._signed_question(tmp_path)
        qid = question["question_id"]
        sdir = tmp_path / ".testboost" / "sessions" / "001-test"
        sdir.mkdir(parents=True)
        (sdir / "question.json").write_text(json.dumps(question))

        mr_response = json.dumps({"author": {"username": "alice"}})
        # Two notes: one from a stranger (should be ignored),
        # one from alice with a valid JSON block and our QID
        raw_answer = {"test_requirements": [{"scenario": "x", "expected": "y"}]}
        alice_body = (
            "Here you go:\n\n```json\n"
            + json.dumps(raw_answer)
            + "\n```\n<!-- testboost:question_id=" + qid + " -->"
        )
        notes_response = json.dumps([
            {"id": 2, "system": False, "author": {"username": "alice"},
             "body": alice_body, "created_at": "2026-06-01T10:00:00Z"},
            {"id": 1, "system": False, "author": {"username": "bob"},
             "body": "I'm not the author\n```json\n{\"hack\": 1}\n```\n"
                     "<!-- testboost:question_id=" + qid + " -->",
             "created_at": "2026-06-01T09:00:00Z"},
        ])
        mock = _make_fetch_mock_curl(tmp_path, mr_response, notes_response)

        out_path = tmp_path / "signed.json"
        env = os.environ.copy()
        env.update({
            "CI_PROJECT_ID": "100",
            "CI_MERGE_REQUEST_IID": "7",
            "CI_API_V4_URL": "https://gitlab.example.com/api/v4",
            "CI_PROJECT_DIR": str(tmp_path),
            "GITLAB_TOKEN": "secret",
            "TB_CURL_BIN": str(mock),
            "TB_SESSION_DIR": str(sdir),
            "TB_OUTPUT": str(out_path),
            "POETRY_VIRTUALENVS_IN_PROJECT": "false",
        })
        res = subprocess.run(
            ["bash", str(SCRIPT_FETCH)],
            cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=60,
        )
        assert res.returncode == 0, f"stderr={res.stderr}\nstdout={res.stdout}"
        assert out_path.exists()
        signed = json.loads(out_path.read_text())
        assert signed["question_id"] == qid
        assert "signature" in signed
        # Alice's payload won, not Bob's hack
        assert signed["test_requirements"] == raw_answer["test_requirements"]

    def test_returns_2_when_no_matching_comment(self, tmp_path):
        question = self._signed_question(tmp_path)
        sdir = tmp_path / ".testboost" / "sessions" / "001-test"
        sdir.mkdir(parents=True)
        (sdir / "question.json").write_text(json.dumps(question))

        mr_response = json.dumps({"author": {"username": "alice"}})
        notes_response = json.dumps([
            {"id": 1, "system": False, "author": {"username": "alice"},
             "body": "just chatting", "created_at": "2026-06-01T10:00:00Z"},
        ])
        mock = _make_fetch_mock_curl(tmp_path, mr_response, notes_response)

        env = os.environ.copy()
        env.update({
            "CI_PROJECT_ID": "100",
            "CI_MERGE_REQUEST_IID": "7",
            "CI_PROJECT_DIR": str(tmp_path),
            "GITLAB_TOKEN": "secret",
            "TB_CURL_BIN": str(mock),
            "TB_SESSION_DIR": str(sdir),
        })
        res = subprocess.run(
            ["bash", str(SCRIPT_FETCH)],
            cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=60,
        )
        assert res.returncode == 2
