# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the GitLab webhook handler.

Skipped if fastapi is not installed (it's an optional tool dependency,
not part of the testboost core deps).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
WEBHOOK_DIR = REPO_ROOT / "tools" / "gitlab-webhook"


@pytest.fixture
def webhook_app(monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("starlette")
    monkeypatch.setenv("GITLAB_WEBHOOK_TOKEN", "test-secret")
    monkeypatch.setenv("GITLAB_TOKEN", "api-token")
    monkeypatch.setenv("GITLAB_API_URL", "https://gitlab.example.com/api/v4")
    sys.path.insert(0, str(WEBHOOK_DIR))
    try:
        import importlib

        import webhook as webhook_module
        importlib.reload(webhook_module)
        yield webhook_module.app
    finally:
        sys.path.remove(str(WEBHOOK_DIR))


def _note_payload(commenter: str = "alice", author: str = "alice", body: str = "") -> dict:
    return {
        "object_kind": "note",
        "object_attributes": {
            "noteable_type": "MergeRequest",
            "body": body,
        },
        "user": {"username": commenter},
        "merge_request": {
            "iid": 7,
            "source_branch": "feature/x",
            "author": {"username": author},
        },
        "project": {"id": 100},
    }


class TestWebhook:
    def test_rejects_bad_token(self, webhook_app):
        from starlette.testclient import TestClient
        client = TestClient(webhook_app)
        r = client.post(
            "/gitlab/note",
            headers={"X-Gitlab-Token": "wrong", "X-Gitlab-Event": "Note Hook"},
            json={},
        )
        assert r.status_code == 401

    def test_rejects_non_note_event(self, webhook_app):
        from starlette.testclient import TestClient
        client = TestClient(webhook_app)
        r = client.post(
            "/gitlab/note",
            headers={"X-Gitlab-Token": "test-secret", "X-Gitlab-Event": "Push Hook"},
            json={},
        )
        assert r.status_code == 400

    def test_ignores_stranger_comment(self, webhook_app):
        from starlette.testclient import TestClient
        client = TestClient(webhook_app)
        body = "ok\n<!-- testboost:question_id=" + "a" * 32 + " -->"
        payload = _note_payload(commenter="bob", author="alice", body=body)
        r = client.post(
            "/gitlab/note",
            headers={"X-Gitlab-Token": "test-secret", "X-Gitlab-Event": "Note Hook"},
            json=payload,
        )
        assert r.status_code == 200
        assert "ignored" in r.json()

    def test_ignores_comment_without_marker(self, webhook_app):
        from starlette.testclient import TestClient
        client = TestClient(webhook_app)
        payload = _note_payload(body="hello")
        r = client.post(
            "/gitlab/note",
            headers={"X-Gitlab-Token": "test-secret", "X-Gitlab-Event": "Note Hook"},
            json=payload,
        )
        assert r.status_code == 200
        assert "ignored" in r.json()

    def test_triggers_pipeline_for_author_comment(self, webhook_app):
        from starlette.testclient import TestClient
        client = TestClient(webhook_app)
        body = "answer\n```json\n{\"x\":1}\n```\n<!-- testboost:question_id=" + "b" * 32 + " -->"
        payload = _note_payload(commenter="alice", author="alice", body=body)

        # Mock the pipeline trigger so we don't hit GitLab
        with patch(
            "webhook._trigger_pipeline",
            new=AsyncMock(return_value={"id": 999}),
        ) as mock_trigger:
            r = client.post(
                "/gitlab/note",
                headers={"X-Gitlab-Token": "test-secret", "X-Gitlab-Event": "Note Hook"},
                json=payload,
            )
        assert r.status_code == 200
        assert r.json()["pipeline_id"] == 999
        mock_trigger.assert_called_once_with(100, 7, "feature/x")


class TestWebhookLoopGuards:
    """P5.9 — the bot's own comments must never trigger resume pipelines."""

    def test_ignores_bot_identity_comment(self, webhook_app, monkeypatch):
        from starlette.testclient import TestClient
        monkeypatch.setenv("TESTBOOST_BOT_USERNAME", "tb-bot")
        client = TestClient(webhook_app)
        marker = "testboost:question_id=" + "a" * 32
        r = client.post(
            "/gitlab/note",
            headers={"X-Gitlab-Token": "test-secret", "X-Gitlab-Event": "Note Hook"},
            json=_note_payload(commenter="tb-bot", author="tb-bot",
                               body=f"```json\n{{}}\n```\n<!-- {marker} -->"),
        )
        assert r.status_code == 200
        assert "bot identity" in r.json()["ignored"]

    def test_ignores_question_comment_shape(self, webhook_app):
        """Even without TESTBOOST_BOT_USERNAME, a comment that IS the
        question (bot author == MR author) must not trigger a pipeline."""
        from starlette.testclient import TestClient
        client = TestClient(webhook_app)
        marker = "testboost:question_id=" + "b" * 32
        body = (
            "### 🤖 TestBoost needs input (missing_business_context)\n\n"
            f"**Question**: …\n\n<!-- {marker} -->"
        )
        r = client.post(
            "/gitlab/note",
            headers={"X-Gitlab-Token": "test-secret", "X-Gitlab-Event": "Note Hook"},
            json=_note_payload(commenter="alice", author="alice", body=body),
        )
        assert r.status_code == 200
        assert "question comment" in r.json()["ignored"]
