# SPDX-License-Identifier: Apache-2.0
"""Post the `check` report on the merge request — one sticky comment, updated on each push.

The comment is found by the `<!-- testboost:check -->` marker AND its author
(TestBoost's own token): a note anyone else wrote with the marker is never
edited, and a new push does not stack a new comment.

GitLab (CI variables): CI_PROJECT_ID, CI_MERGE_REQUEST_IID, GITLAB_TOKEN, CI_API_V4_URL.
GitHub (Actions): GITHUB_TOKEN, GITHUB_REPOSITORY, the PR number from GITHUB_EVENT_PATH
(or TESTBOOST_PR_NUMBER), GITHUB_API_URL; the comment author is `github-actions[bot]`
unless TESTBOOST_COMMENT_AUTHOR says otherwise (a personal or app token).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from src.lib.commands.check_cmd import CHECK_DIR, REPORT_MARKER
from src.lib.gitlab_mr import GitLabConfigError, _require_env

GITHUB_MAX_BODY = 65_000          # GitHub refuses comments above 65 536 characters


def report_body(project_path: str, report_file: str | None = None) -> str:
    path = Path(report_file) if report_file else Path(project_path) / CHECK_DIR / "report.md"
    if not path.exists():
        raise GitLabConfigError(f"no report at {path}: run `testboost check` first")
    body = path.read_text(encoding="utf-8")
    return body if REPORT_MARKER in body else body.rstrip() + "\n\n" + REPORT_MARKER + "\n"


def _client(client: httpx.Client | None) -> tuple[httpx.Client, bool]:
    return (client, False) if client is not None else (httpx.Client(timeout=15), True)


def post_gitlab(project_path: str, report_file: str | None = None,
                client: httpx.Client | None = None) -> dict:
    env = _require_env()
    body = report_body(project_path, report_file)
    headers = {"PRIVATE-TOKEN": env["token"]}
    notes_url = f"{env['api']}/projects/{env['project_id']}/merge_requests/{env['mr_iid']}/notes"
    http, own = _client(client)
    try:
        me = http.get(f"{env['api']}/user", headers=headers)
        me.raise_for_status()
        notes = http.get(notes_url, params={"per_page": 100, "sort": "desc"}, headers=headers)
        notes.raise_for_status()
        mine = next((n for n in notes.json() if REPORT_MARKER in (n.get("body") or "")
                     and (n.get("author") or {}).get("id") == me.json().get("id")), None)
        if mine:
            resp = http.put(f"{notes_url}/{mine['id']}", json={"body": body}, headers=headers)
        else:
            resp = http.post(notes_url, json={"body": body}, headers=headers)
        resp.raise_for_status()
        return {"id": resp.json().get("id"), "updated": mine is not None}
    finally:
        if own:
            http.close()


def _github_env() -> dict[str, str]:
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    number = os.environ.get("TESTBOOST_PR_NUMBER")
    event = os.environ.get("GITHUB_EVENT_PATH")
    if not number and event and Path(event).exists():
        payload = json.loads(Path(event).read_text(encoding="utf-8"))
        number = str((payload.get("pull_request") or {}).get("number") or "")
    missing = [name for name, value in (("GITHUB_TOKEN", token), ("GITHUB_REPOSITORY", repo),
                                        ("a pull request number (pull_request event or TESTBOOST_PR_NUMBER)",
                                         number)) if not value]
    if missing:
        raise GitLabConfigError(f"missing required env: {', '.join(missing)}")
    return {"token": token, "repo": repo, "number": number,
            "api": os.environ.get("GITHUB_API_URL", "https://api.github.com"),
            "author": os.environ.get("TESTBOOST_COMMENT_AUTHOR", "github-actions[bot]")}


def post_github(project_path: str, report_file: str | None = None,
                client: httpx.Client | None = None) -> dict:
    env = _github_env()
    body = report_body(project_path, report_file)
    if len(body) > GITHUB_MAX_BODY:
        body = body[:GITHUB_MAX_BODY] + "\n\n… (truncated: see the job's report.md)\n\n" + REPORT_MARKER
    headers = {"Authorization": f"Bearer {env['token']}", "Accept": "application/vnd.github+json"}
    base = f"{env['api']}/repos/{env['repo']}/issues"
    http, own = _client(client)
    try:
        comments = http.get(f"{base}/{env['number']}/comments", params={"per_page": 100}, headers=headers)
        comments.raise_for_status()
        mine = next((c for c in comments.json() if REPORT_MARKER in (c.get("body") or "")
                     and (c.get("user") or {}).get("login") == env["author"]), None)
        if mine:
            resp = http.patch(f"{base}/comments/{mine['id']}", json={"body": body}, headers=headers)
        else:
            resp = http.post(f"{base}/{env['number']}/comments", json={"body": body}, headers=headers)
        resp.raise_for_status()
        return {"id": resp.json().get("id"), "updated": mine is not None}
    finally:
        if own:
            http.close()
