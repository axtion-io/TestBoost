# SPDX-License-Identifier: Apache-2.0
"""The `check` report as ONE sticky MR/PR comment: created once, updated on every push,
and only ever TestBoost's own (a comment someone else wrote with the marker is left alone).
APIs faked with httpx.MockTransport."""

import json

import httpx
import pytest

from src.lib.commands.check_cmd import REPORT_MARKER
from src.lib.gitlab_mr import GitLabConfigError
from src.lib.mr_report import GITHUB_MAX_BODY, post_github, post_gitlab

REPORT = f"## TestBoost check — PASSED\n\n{REPORT_MARKER}\n"


@pytest.fixture
def project(tmp_path):
    (tmp_path / ".testboost/check").mkdir(parents=True)
    (tmp_path / ".testboost/check/report.md").write_text(REPORT)
    return tmp_path


class _Api:
    def __init__(self, existing):
        self.existing, self.calls = existing, []

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self.handle))

    def handle(self, request):
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, request.url.path, body))
        if request.method == "GET" and request.url.path.endswith("/user"):
            return httpx.Response(200, json={"id": 7})
        if request.method == "GET":
            return httpx.Response(200, json=self.existing)
        return httpx.Response(200, json={"id": 99})


class TestGitLab:
    @pytest.fixture(autouse=True)
    def env(self, monkeypatch):
        for k, v in {"CI_PROJECT_ID": "1", "CI_MERGE_REQUEST_IID": "5", "GITLAB_TOKEN": "t",
                     "CI_API_V4_URL": "https://gl/api/v4"}.items():
            monkeypatch.setenv(k, v)

    def test_first_push_creates_the_note(self, project):
        api = _Api([{"id": 3, "body": "LGTM", "author": {"id": 7}}])
        assert post_gitlab(str(project), client=api.client()) == {"id": 99, "updated": False}
        assert api.calls[-1] == ("POST", "/api/v4/projects/1/merge_requests/5/notes", {"body": REPORT})

    def test_next_push_updates_our_note_not_someone_elses(self, project):
        api = _Api([{"id": 4, "body": f"copied {REPORT_MARKER}", "author": {"id": 8}},
                    {"id": 2, "body": f"old {REPORT_MARKER}", "author": {"id": 7}}])
        assert post_gitlab(str(project), client=api.client())["updated"] is True
        assert api.calls[-1][:2] == ("PUT", "/api/v4/projects/1/merge_requests/5/notes/2")

    def test_no_report_yet(self, tmp_path):
        with pytest.raises(GitLabConfigError, match="run `testboost check` first"):
            post_gitlab(str(tmp_path), client=_Api([]).client())


class TestGitHub:
    @pytest.fixture(autouse=True)
    def env(self, monkeypatch, tmp_path):
        event = tmp_path / "event.json"
        event.write_text(json.dumps({"pull_request": {"number": 12}}))
        for k, v in {"GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": "o/r", "GITHUB_EVENT_PATH": str(event),
                     "GITHUB_API_URL": "https://gh"}.items():
            monkeypatch.setenv(k, v)
        monkeypatch.delenv("TESTBOOST_PR_NUMBER", raising=False)

    def test_sticky_comment_by_the_actions_bot(self, project):
        api = _Api([{"id": 5, "body": REPORT, "user": {"login": "someone"}},
                    {"id": 6, "body": REPORT, "user": {"login": "github-actions[bot]"}}])
        assert post_github(str(project), client=api.client())["updated"] is True
        assert api.calls[-1][:2] == ("PATCH", "/repos/o/r/issues/comments/6")

    def test_created_when_absent_and_truncated_to_the_api_limit(self, project):
        (project / ".testboost/check/report.md").write_text("x" * (GITHUB_MAX_BODY + 10))
        api = _Api([])
        post_github(str(project), client=api.client())
        method, path, body = api.calls[-1]
        assert (method, path) == ("POST", "/repos/o/r/issues/12/comments")
        assert len(body["body"]) < 65_536 and body["body"].endswith(REPORT_MARKER)

    def test_outside_a_pull_request(self, project, monkeypatch):
        monkeypatch.delenv("GITHUB_EVENT_PATH")
        with pytest.raises(GitLabConfigError, match="pull request number"):
            post_github(str(project), client=_Api([]).client())


def test_cli_reports_missing_env(project, monkeypatch, capsys):
    from src.lib.cli import main
    for k in ("GITHUB_TOKEN", "GITHUB_REPOSITORY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr("sys.argv", ["testboost", "github", "post-report", str(project)])
    assert main() == 1
    assert "GITHUB_TOKEN" in capsys.readouterr().err
