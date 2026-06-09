# SPDX-License-Identifier: Apache-2.0
"""GitLab MR helpers: post a pending question as an MR note, fetch the answer.

Replaces the former scripts/gitlab/*.sh so consumer repos only need
`pip install testboost` — `include:`-ing the CI template does not ship
shell scripts.

Environment (provided by GitLab CI):
    CI_PROJECT_ID            — numeric project id
    CI_MERGE_REQUEST_IID     — MR iid (merge_request_event pipelines), or
    TESTBOOST_MR_IID         — fallback sent by the resume webhook (branch
                               pipelines triggered via the API have no
                               CI_MERGE_REQUEST_IID)
    GITLAB_TOKEN             — Project Access Token, scope: api
    CI_API_V4_URL            — defaults to https://gitlab.com/api/v4
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import httpx

QUESTION_MARKER_TEMPLATE = "<!-- testboost:question_id={qid} -->"
ANSWER_JSON_BLOCK = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)


class GitLabConfigError(RuntimeError):
    """Missing/invalid environment for the GitLab API calls."""


class NoAnswerFoundError(RuntimeError):
    """No MR note matched the pending question (author + question_id)."""


def _require_env() -> dict[str, str]:
    project_id = os.environ.get("CI_PROJECT_ID")
    mr_iid = os.environ.get("CI_MERGE_REQUEST_IID") or os.environ.get("TESTBOOST_MR_IID")
    token = os.environ.get("GITLAB_TOKEN")
    api = os.environ.get("CI_API_V4_URL", "https://gitlab.com/api/v4")

    missing = []
    if not project_id:
        missing.append("CI_PROJECT_ID")
    if not mr_iid:
        missing.append("CI_MERGE_REQUEST_IID (or TESTBOOST_MR_IID)")
    if not token:
        missing.append("GITLAB_TOKEN")
    if missing:
        raise GitLabConfigError(f"missing required env: {', '.join(missing)}")

    return {"project_id": project_id, "mr_iid": mr_iid, "token": token, "api": api}


def _pending_question(project_path: str) -> tuple[Path, dict[str, Any]]:
    """Locate the current session's question.json."""
    from src.lib.session_tracker import QUESTION_FILENAME, get_current_session

    session = get_current_session(project_path)
    if not session:
        raise GitLabConfigError(f"no TestBoost session found in {project_path}")
    qpath = Path(session["session_dir"]) / QUESTION_FILENAME
    if not qpath.exists():
        raise GitLabConfigError(f"no pending question.json in {session['session_dir']}")
    question = json.loads(qpath.read_text(encoding="utf-8"))
    if "question_id" not in question:
        raise GitLabConfigError("pending question has no question_id")
    return qpath, question


def post_question(project_path: str, client: httpx.Client | None = None) -> dict[str, Any]:
    """POST the pending question's markdown_preview as an MR note.

    The note body ends with a machine-readable marker
    `<!-- testboost:question_id=… -->` that the resume webhook and
    fetch_answer() grep for.

    Returns {"question_id": …, "note_id": …}.
    """
    env = _require_env()
    _qpath, question = _pending_question(project_path)
    qid = question["question_id"]
    preview = question.get("markdown_preview") or json.dumps(question, indent=2)
    body = f"{preview}\n\n{QUESTION_MARKER_TEMPLATE.format(qid=qid)}"

    url = (
        f"{env['api']}/projects/{env['project_id']}"
        f"/merge_requests/{env['mr_iid']}/notes"
    )
    own_client = client is None
    client = client or httpx.Client(timeout=15)
    try:
        resp = client.post(
            url,
            json={"body": body},
            headers={"PRIVATE-TOKEN": env["token"]},
        )
        resp.raise_for_status()
        note = resp.json()
    finally:
        if own_client:
            client.close()

    return {"question_id": qid, "note_id": note.get("id")}


def fetch_answer(
    project_path: str,
    output: str | Path = "./answer.json",
    client: httpx.Client | None = None,
) -> Path:
    """Find the developer's answer note on the MR and write a signed answer file.

    Algorithm:
      1. Fetch the MR to learn its author.
      2. Fetch the notes (newest first).
      3. Keep the first non-system note authored by the MR author whose body
         references the pending question_id and contains a fenced JSON block.
      4. Sign the raw JSON against the pending question (integrity.sign_answer)
         and write it to `output`.

    Raises NoAnswerFoundError when no note matches.
    """
    from src.lib.integrity import sign_answer

    env = _require_env()
    qpath, question = _pending_question(project_path)
    qid = question["question_id"]
    marker = QUESTION_MARKER_TEMPLATE.format(qid=qid)

    base = f"{env['api']}/projects/{env['project_id']}/merge_requests/{env['mr_iid']}"
    headers = {"PRIVATE-TOKEN": env["token"]}

    own_client = client is None
    client = client or httpx.Client(timeout=15)
    try:
        mr_resp = client.get(base, headers=headers)
        mr_resp.raise_for_status()
        author = ((mr_resp.json().get("author") or {}).get("username")) or ""

        notes_resp = client.get(
            f"{base}/notes",
            params={"per_page": 100, "order_by": "created_at", "sort": "desc"},
            headers=headers,
        )
        notes_resp.raise_for_status()
        notes = notes_resp.json()
    finally:
        if own_client:
            client.close()

    raw_answer = _extract_answer(notes, author, marker)
    if raw_answer is None:
        raise NoAnswerFoundError(
            f"no matching answer note found (author={author!r}, question_id={qid})"
        )

    signed = sign_answer(raw_answer, question, project_path)
    out_path = Path(output)
    out_path.write_text(json.dumps(signed, indent=2), encoding="utf-8")
    return out_path


def _extract_answer(
    notes: list[dict[str, Any]], author: str, marker: str
) -> dict[str, Any] | None:
    """First valid JSON answer from the MR author referencing the marker."""
    for note in notes:
        if note.get("system"):
            continue
        if ((note.get("author") or {}).get("username")) != author:
            continue
        body = note.get("body") or ""
        if marker not in body:
            continue
        # The bot's own question note carries the marker AND fenced JSON
        # (the answer_schema) — never mistake it for an answer, even when
        # the MR author is the bot identity.
        if body.lstrip().startswith("### 🤖 TestBoost needs input"):
            continue
        match = ANSWER_JSON_BLOCK.search(body)
        if not match:
            continue
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None
