# SPDX-License-Identifier: Apache-2.0
"""GitLab Note Hook → trigger TestBoost resume pipeline.

Standalone tool, deployed separately from TestBoost itself. Receives
GitLab webhook events, validates the source comment (author check),
and triggers a new pipeline with the `TESTBOOST_RESUME=true` variable
so the CI fetches the answer and resumes the paused session.

Run with:
    pip install -r requirements.txt
    uvicorn webhook:app --host 0.0.0.0 --port 8080

Required env:
    GITLAB_WEBHOOK_TOKEN  — secret to validate X-Gitlab-Token header
    GITLAB_TOKEN          — token used to call the GitLab API
    GITLAB_API_URL        — e.g. https://gitlab.com/api/v4
"""

from __future__ import annotations

import hmac
import logging
import os
import re

import httpx
from fastapi import FastAPI, Header, HTTPException, Request

app = FastAPI(title="TestBoost GitLab Webhook")
log = logging.getLogger("testboost.webhook")
logging.basicConfig(level=logging.INFO)

QUESTION_MARKER = re.compile(r"testboost:question_id=([0-9a-f]{32})")


def _expected_token() -> str:
    tok = os.environ.get("GITLAB_WEBHOOK_TOKEN")
    if not tok:
        raise RuntimeError("GITLAB_WEBHOOK_TOKEN env var is required")
    return tok


async def _trigger_pipeline(project_id: int, mr_iid: int, ref: str) -> dict:
    """Trigger a new pipeline on the MR's source branch, with resume vars."""
    api = os.environ.get("GITLAB_API_URL", "https://gitlab.com/api/v4")
    token = os.environ.get("GITLAB_TOKEN")
    if not token:
        raise RuntimeError("GITLAB_TOKEN env var is required")
    url = f"{api}/projects/{project_id}/pipeline"
    headers = {"PRIVATE-TOKEN": token, "Content-Type": "application/json"}
    payload = {
        "ref": ref,
        "variables": [
            {"key": "TESTBOOST_RESUME", "value": "true"},
            {"key": "TESTBOOST_MR_IID", "value": str(mr_iid)},
        ],
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()


@app.post("/gitlab/note")
async def gitlab_note(
    request: Request,
    x_gitlab_token: str | None = Header(default=None),
    x_gitlab_event: str | None = Header(default=None),
):
    if not hmac.compare_digest(x_gitlab_token or "", _expected_token()):
        raise HTTPException(status_code=401, detail="bad webhook token")
    if x_gitlab_event != "Note Hook":
        raise HTTPException(status_code=400, detail=f"unsupported event: {x_gitlab_event}")

    payload = await request.json()

    # We only care about notes on merge requests
    if (payload.get("object_attributes") or {}).get("noteable_type") != "MergeRequest":
        return {"ignored": "not a MR note"}

    note = payload["object_attributes"]
    mr = payload.get("merge_request") or {}
    user = payload.get("user") or {}

    body = note.get("body", "") or ""
    if not QUESTION_MARKER.search(body):
        return {"ignored": "no testboost question_id marker"}

    commenter_username = user.get("username")

    # Loop guard: the bot's own question comment carries the marker too.
    # When the MR author IS the bot identity (automation-opened MRs), the
    # author check below would let it through and trigger pipelines forever.
    bot_username = os.environ.get("TESTBOOST_BOT_USERNAME")
    if bot_username and commenter_username == bot_username:
        return {"ignored": "comment authored by the bot identity"}
    if body.lstrip().startswith("### 🤖 TestBoost needs input"):
        return {"ignored": "testboost question comment, not an answer"}

    # Author check: only the MR author may answer. Real Note Hook payloads
    # carry the author as `merge_request.author_id` (an integer) and the
    # commenter as the top-level `user.id` — there is NO nested
    # merge_request.author object, so compare the ids directly. (A broader
    # maintainer allow-list would need an extra API call — extend here if
    # you want it.)
    commenter_id = user.get("id")
    author_id = mr.get("author_id")
    if commenter_id is None or author_id is None or commenter_id != author_id:
        log.info(
            "ignored note from user id %s on MR authored by id %s (not the author)",
            commenter_id, author_id,
        )
        return {"ignored": "commenter is not the MR author"}

    project_id = (payload.get("project") or {}).get("id")
    mr_iid = mr.get("iid")
    ref = mr.get("source_branch")
    if not (project_id and mr_iid and ref):
        raise HTTPException(status_code=400, detail="missing project/MR fields")

    try:
        pipe = await _trigger_pipeline(project_id, mr_iid, ref)
    except httpx.HTTPError as e:
        log.error("pipeline trigger failed: %s", e)
        raise HTTPException(status_code=502, detail="pipeline trigger failed") from e

    log.info("triggered resume pipeline %s on %s", pipe.get("id"), ref)
    return {"pipeline_id": pipe.get("id"), "ref": ref}


@app.get("/health")
async def health():
    return {"status": "ok"}
