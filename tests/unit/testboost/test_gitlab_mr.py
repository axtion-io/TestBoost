# SPDX-License-Identifier: Apache-2.0
"""Tests for src/lib/gitlab_mr.py (testboost gitlab post-question / fetch-answer).

These replace the former bash-script tests (scripts/gitlab/*.sh) — the MR
helpers now ship as CLI subcommands so a `pip install testboost` is enough
in consumer repos. The GitLab API is faked with httpx.MockTransport.
"""

import argparse
import json
from pathlib import Path

import httpx
import pytest

from src.lib.session_tracker import create_session, emit_question, init_project


def _make_session_with_question(project_path: Path) -> dict:
    init_project(str(project_path))
    session = create_session(str(project_path), name="hitl")
    emit_question(
        session["session_dir"],
        "generation",
        {
            "kind": "missing_business_context",
            "subject": {"class_name": "OrderService"},
            "question": "What are the business rules?",
            "answer_schema": {"test_requirements": {"OrderService": []}},
        },
        project_path=str(project_path),
        session_id=session["session_id"],
    )
    question = json.loads(
        (Path(session["session_dir"]) / "question.json").read_text()
    )
    return {"session": session, "question": question}


def _ci_env(monkeypatch, mr_iid_var="CI_MERGE_REQUEST_IID"):
    monkeypatch.setenv("CI_PROJECT_ID", "123")
    monkeypatch.delenv("CI_MERGE_REQUEST_IID", raising=False)
    monkeypatch.delenv("TESTBOOST_MR_IID", raising=False)
    monkeypatch.setenv(mr_iid_var, "42")
    monkeypatch.setenv("GITLAB_TOKEN", "glpat-test")
    monkeypatch.setenv("CI_API_V4_URL", "https://gitlab.example.com/api/v4")


class TestPostQuestion:
    def test_posts_markdown_preview_with_marker(self, tmp_path, monkeypatch):
        from src.lib.gitlab_mr import post_question

        ctx = _make_session_with_question(tmp_path)
        qid = ctx["question"]["question_id"]
        _ci_env(monkeypatch)

        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["token"] = request.headers.get("PRIVATE-TOKEN")
            captured["body"] = json.loads(request.content)["body"]
            return httpx.Response(201, json={"id": 777})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        result = post_question(str(tmp_path), client=client)

        assert result == {"question_id": qid, "note_id": 777}
        assert (
            captured["url"]
            == "https://gitlab.example.com/api/v4/projects/123/merge_requests/42/notes"
        )
        assert captured["token"] == "glpat-test"
        assert "TestBoost needs input" in captured["body"]
        assert f"<!-- testboost:question_id={qid} -->" in captured["body"]

    def test_fails_without_pending_question(self, tmp_path, monkeypatch):
        from src.lib.gitlab_mr import GitLabConfigError, post_question

        init_project(str(tmp_path))
        create_session(str(tmp_path), name="empty")
        _ci_env(monkeypatch)

        with pytest.raises(GitLabConfigError, match="no pending question"):
            post_question(str(tmp_path))

    def test_fails_with_missing_env(self, tmp_path, monkeypatch):
        from src.lib.gitlab_mr import GitLabConfigError, post_question

        _make_session_with_question(tmp_path)
        monkeypatch.delenv("CI_PROJECT_ID", raising=False)
        monkeypatch.delenv("CI_MERGE_REQUEST_IID", raising=False)
        monkeypatch.delenv("TESTBOOST_MR_IID", raising=False)
        monkeypatch.delenv("GITLAB_TOKEN", raising=False)

        with pytest.raises(GitLabConfigError, match="CI_PROJECT_ID"):
            post_question(str(tmp_path))


class TestFetchAnswer:
    def _gitlab_with_notes(self, notes, author="devuser"):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/notes"):
                return httpx.Response(200, json=notes)
            return httpx.Response(200, json={"author": {"username": author}})

        return httpx.Client(transport=httpx.MockTransport(handler))

    def test_picks_author_note_with_matching_qid_and_signs(self, tmp_path, monkeypatch):
        from src.lib.gitlab_mr import fetch_answer
        from src.lib.integrity import verify_answer

        ctx = _make_session_with_question(tmp_path)
        qid = ctx["question"]["question_id"]
        _ci_env(monkeypatch)

        answer_json = {"test_requirements": {"OrderService": [
            {"scenario": "zero items must throw", "expected": "IllegalArgumentException"},
        ]}}
        notes = [
            {"system": True, "author": {"username": "devuser"}, "body": "merged X"},
            {"author": {"username": "stranger"},
             "body": f"```json\n{{}}\n```\n<!-- testboost:question_id={qid} -->"},
            {"author": {"username": "devuser"},
             "body": (
                 "Here you go:\n```json\n"
                 + json.dumps(answer_json)
                 + f"\n```\n<!-- testboost:question_id={qid} -->"
             )},
        ]
        out = tmp_path / "answer.json"
        fetch_answer(
            str(tmp_path), output=out, client=self._gitlab_with_notes(notes)
        )

        signed = json.loads(out.read_text())
        assert signed["test_requirements"] == answer_json["test_requirements"]
        assert signed["question_id"] == qid
        # Must verify against the pending question (i.e. correctly signed)
        verify_answer(signed, ctx["question"], str(tmp_path))

    def test_returns_error_when_no_matching_note(self, tmp_path, monkeypatch):
        from src.lib.gitlab_mr import NoAnswerFoundError, fetch_answer

        _make_session_with_question(tmp_path)
        _ci_env(monkeypatch)

        notes = [
            {"author": {"username": "devuser"}, "body": "unrelated comment"},
        ]
        with pytest.raises(NoAnswerFoundError):
            fetch_answer(
                str(tmp_path),
                output=tmp_path / "answer.json",
                client=self._gitlab_with_notes(notes),
            )

    def test_skips_the_bots_own_question_note(self, tmp_path, monkeypatch):
        """The question note carries the marker + fenced JSON (the schema) —
        it must never be mistaken for an answer, even if author == bot."""
        from src.lib.gitlab_mr import NoAnswerFoundError, fetch_answer

        ctx = _make_session_with_question(tmp_path)
        qid = ctx["question"]["question_id"]
        _ci_env(monkeypatch)

        question_body = (
            ctx["question"]["markdown_preview"]
            + f"\n\n<!-- testboost:question_id={qid} -->"
        )
        notes = [{"author": {"username": "devuser"}, "body": question_body}]
        with pytest.raises(NoAnswerFoundError):
            fetch_answer(
                str(tmp_path),
                output=tmp_path / "answer.json",
                client=self._gitlab_with_notes(notes),
            )

    def test_mr_iid_fallback_to_testboost_var(self, tmp_path, monkeypatch):
        """Branch pipelines triggered by the webhook have no
        CI_MERGE_REQUEST_IID — TESTBOOST_MR_IID must be honoured."""
        from src.lib.gitlab_mr import fetch_answer

        ctx = _make_session_with_question(tmp_path)
        qid = ctx["question"]["question_id"]
        _ci_env(monkeypatch, mr_iid_var="TESTBOOST_MR_IID")

        urls = []

        def handler(request: httpx.Request) -> httpx.Response:
            urls.append(str(request.url))
            if request.url.path.endswith("/notes"):
                return httpx.Response(200, json=[
                    {"author": {"username": "devuser"},
                     "body": (
                         "```json\n{\"test_requirements\": {}}\n```\n"
                         f"<!-- testboost:question_id={qid} -->"
                     )},
                ])
            return httpx.Response(200, json={"author": {"username": "devuser"}})

        out = fetch_answer(
            str(tmp_path), output=tmp_path / "a.json",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        assert out.exists()
        assert all("/merge_requests/42" in u for u in urls)


class TestCmdGitlab:
    def test_post_question_without_env_returns_1(self, tmp_path, monkeypatch, capsys):
        from src.lib.cli import cmd_gitlab

        monkeypatch.delenv("CI_PROJECT_ID", raising=False)
        monkeypatch.delenv("GITLAB_TOKEN", raising=False)
        rc = cmd_gitlab(argparse.Namespace(
            gitlab_command="post-question", project_path=str(tmp_path),
        ))
        assert rc == 1
        assert "Error" in capsys.readouterr().err

    def test_fetch_answer_no_match_returns_2(self, tmp_path, monkeypatch, capsys):
        from unittest.mock import patch

        from src.lib.cli import cmd_gitlab
        from src.lib.gitlab_mr import NoAnswerFoundError

        with patch("src.lib.gitlab_mr.fetch_answer",
                   side_effect=NoAnswerFoundError("nope")):
            rc = cmd_gitlab(argparse.Namespace(
                gitlab_command="fetch-answer",
                project_path=str(tmp_path),
                output="./answer.json",
            ))
        assert rc == 2
        assert "nope" in capsys.readouterr().err
