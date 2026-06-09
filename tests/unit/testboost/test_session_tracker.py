# SPDX-License-Identifier: Apache-2.0
"""Unit tests for src.lib.session_tracker."""

import re

from src.lib.session_tracker import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_IN_PROGRESS,
    STEPS,
    _make_frontmatter,
    _parse_frontmatter,
    create_session,
    get_current_session,
    get_session_status,
    get_sessions_dir,
    get_testboost_dir,
    init_project,
    update_step_file,
    write_log,
)

# ============================================================================
# init_project
# ============================================================================


class TestInitProject:
    def test_creates_testboost_dir(self, tmp_path):
        result = init_project(str(tmp_path))
        assert result["success"] is True
        assert (tmp_path / ".testboost").is_dir()

    def test_creates_sessions_dir(self, tmp_path):
        init_project(str(tmp_path))
        assert (tmp_path / ".testboost" / "sessions").is_dir()

    def test_creates_config_yaml(self, tmp_path):
        init_project(str(tmp_path))
        config = tmp_path / ".testboost" / "config.yaml"
        assert config.exists()
        content = config.read_text()
        assert "coverage_target: 80" in content
        assert "mock_framework: mockito" in content

    def test_creates_gitignore(self, tmp_path):
        init_project(str(tmp_path))
        gi = tmp_path / ".testboost" / ".gitignore"
        assert gi.exists()
        assert "logs" in gi.read_text()

    def test_idempotent(self, tmp_path):
        """Calling init twice should not fail or overwrite config."""
        init_project(str(tmp_path))
        config = tmp_path / ".testboost" / "config.yaml"
        config.write_text("custom: true\n")

        init_project(str(tmp_path))
        assert config.read_text() == "custom: true\n"

    def test_returns_message(self, tmp_path):
        result = init_project(str(tmp_path))
        assert "Initialized" in result["message"]
        assert str(tmp_path) in result["message"]


# ============================================================================
# create_session
# ============================================================================


class TestCreateSession:
    def test_creates_session_dir(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        assert result["success"] is True
        assert "001-test-generation" in result["session_id"]

    def test_creates_spec_md(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        spec = (tmp_path / ".testboost" / "sessions" / result["session_id"] / "spec.md")
        assert spec.exists()
        content = spec.read_text()
        assert "status: in_progress" in content
        assert "## Progress" in content

    def test_creates_logs_dir(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        logs = (tmp_path / ".testboost" / "sessions" / result["session_id"] / "logs")
        assert logs.is_dir()

    def test_custom_name(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path), name="My Custom Session")
        assert result["session_id"] == "001-my-custom-session"

    def test_custom_description(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path), description="Test the auth module")
        spec = (tmp_path / ".testboost" / "sessions" / result["session_id"] / "spec.md")
        assert "Test the auth module" in spec.read_text()

    def test_sequential_numbering(self, tmp_path):
        init_project(str(tmp_path))
        r1 = create_session(str(tmp_path), name="first")
        r2 = create_session(str(tmp_path), name="second")
        assert r1["session_id"].startswith("001-")
        assert r2["session_id"].startswith("002-")

    def test_progress_table_has_all_steps(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        spec = (tmp_path / ".testboost" / "sessions" / result["session_id"] / "spec.md")
        content = spec.read_text()
        for step in STEPS:
            assert f"| {step} | pending |" in content

    def test_sanitizes_name(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path), name="Hello World! @#$")
        assert "hello-world" in result["session_id"]
        # No special characters
        assert re.match(r"^\d{3}-[a-z0-9-]+$", result["session_id"])


# ============================================================================
# get_current_session
# ============================================================================


class TestGetCurrentSession:
    def test_returns_none_when_no_sessions(self, tmp_path):
        init_project(str(tmp_path))
        assert get_current_session(str(tmp_path)) is None

    def test_returns_none_when_no_testboost_dir(self, tmp_path):
        assert get_current_session(str(tmp_path)) is None

    def test_returns_latest_session(self, tmp_path):
        init_project(str(tmp_path))
        create_session(str(tmp_path), name="first")
        create_session(str(tmp_path), name="second")
        session = get_current_session(str(tmp_path))
        assert session is not None
        assert session["session_id"] == "002-second"

    def test_returns_session_fields(self, tmp_path):
        init_project(str(tmp_path))
        create_session(str(tmp_path))
        session = get_current_session(str(tmp_path))
        assert "session_id" in session
        assert "session_dir" in session
        assert "status" in session
        assert session["status"] == STATUS_IN_PROGRESS


# ============================================================================
# update_step_file
# ============================================================================


class TestUpdateStepFile:
    def test_writes_step_file(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        session_dir = result["session_dir"]

        path = update_step_file(session_dir, "analysis", STATUS_COMPLETED, "# Analysis\n\nDone.")
        assert path.exists()
        content = path.read_text()
        assert "status: completed" in content
        assert "# Analysis" in content

    def test_includes_json_data(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        session_dir = result["session_dir"]

        path = update_step_file(
            session_dir, "analysis", STATUS_COMPLETED,
            "# Analysis\n\nDone.",
            data={"source_files": ["A.java", "B.java"]},
        )
        content = path.read_text()
        assert "```json" in content
        assert '"source_files"' in content
        assert "A.java" in content

    def test_updates_spec_progress(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        session_dir = result["session_dir"]

        update_step_file(session_dir, "analysis", STATUS_COMPLETED, "# Done")
        spec = (tmp_path / ".testboost" / "sessions" / result["session_id"] / "spec.md")
        content = spec.read_text()
        assert "| analysis | completed |" in content

    def test_in_progress_status(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        session_dir = result["session_dir"]

        path = update_step_file(session_dir, "generation", STATUS_IN_PROGRESS, "# Generating...")
        content = path.read_text()
        assert "status: in_progress" in content

    def test_failed_status(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        session_dir = result["session_dir"]

        path = update_step_file(session_dir, "validation", STATUS_FAILED, "# Failed\n\nError: timeout")
        content = path.read_text()
        assert "status: failed" in content


# ============================================================================
# write_log
# ============================================================================


class TestWriteLog:
    def test_creates_log_file(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        session_dir = result["session_dir"]

        write_log(session_dir, "analysis", "INFO", "Test message")

        log_files = list((tmp_path / ".testboost" / "sessions" / result["session_id"] / "logs").glob("*.md"))
        assert len(log_files) == 1

    def test_log_contains_message(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        session_dir = result["session_dir"]

        write_log(session_dir, "analysis", "INFO", "Found 12 files")

        log_files = list((tmp_path / ".testboost" / "sessions" / result["session_id"] / "logs").glob("*.md"))
        content = log_files[0].read_text()
        assert "Found 12 files" in content
        assert "INFO" in content
        assert "analysis" in content

    def test_appends_multiple_entries(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        session_dir = result["session_dir"]

        write_log(session_dir, "analysis", "INFO", "Step 1")
        write_log(session_dir, "analysis", "INFO", "Step 2")
        write_log(session_dir, "analysis", "ERROR", "Something failed")

        log_files = list((tmp_path / ".testboost" / "sessions" / result["session_id"] / "logs").glob("*.md"))
        content = log_files[0].read_text()
        assert "Step 1" in content
        assert "Step 2" in content
        assert "Something failed" in content

    def test_includes_kwargs(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        session_dir = result["session_dir"]

        write_log(session_dir, "analysis", "INFO", "Files found", count=12, path="/tmp")

        log_files = list((tmp_path / ".testboost" / "sessions" / result["session_id"] / "logs").glob("*.md"))
        content = log_files[0].read_text()
        assert "count=12" in content


# ============================================================================
# get_session_status
# ============================================================================


class TestGetSessionStatus:
    def test_no_session(self, tmp_path):
        status = get_session_status(str(tmp_path))
        assert "No active session" in status

    def test_with_session(self, tmp_path):
        init_project(str(tmp_path))
        create_session(str(tmp_path), name="test")
        status = get_session_status(str(tmp_path))
        assert "001-test" in status
        assert "pending" in status

    def test_with_completed_step(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        update_step_file(result["session_dir"], "analysis", STATUS_COMPLETED, "# Done")
        status = get_session_status(str(tmp_path))
        assert "completed" in status


# ============================================================================
# Frontmatter helpers
# ============================================================================


class TestFrontmatter:
    def test_make_frontmatter(self):
        fm = _make_frontmatter(status="completed", step="analysis")
        assert "---" in fm
        assert "status: completed" in fm
        assert "step: analysis" in fm

    def test_make_frontmatter_skips_none(self):
        fm = _make_frontmatter(status="ok", extra=None)
        assert "extra" not in fm

    def test_parse_frontmatter(self):
        content = "---\nstatus: completed\nstep: analysis\n---\n\n# Title"
        result = _parse_frontmatter(content)
        assert result["status"] == "completed"
        assert result["step"] == "analysis"

    def test_parse_frontmatter_no_frontmatter(self):
        result = _parse_frontmatter("# Just a title\nNo frontmatter here")
        assert result == {}


# ============================================================================
# Path helpers
# ============================================================================


class TestPathHelpers:
    def test_get_testboost_dir(self, tmp_path):
        result = get_testboost_dir(str(tmp_path))
        assert result == tmp_path / ".testboost"

    def test_get_sessions_dir(self, tmp_path):
        result = get_sessions_dir(str(tmp_path))
        assert result == tmp_path / ".testboost" / "sessions"


# ============================================================================
# Project-level analysis
# ============================================================================


class TestProjectAnalysis:
    def test_get_project_analysis_path(self, tmp_path):
        from src.lib.session_tracker import get_project_analysis_path
        result = get_project_analysis_path(str(tmp_path))
        assert result == tmp_path / ".testboost" / "analysis.md"

    def test_write_and_read_project_analysis(self, tmp_path):
        from src.lib.session_tracker import (
            read_project_analysis_data,
            write_project_analysis,
        )
        init_project(str(tmp_path))
        data = {
            "class_index": {"Foo": {"class_name": "Foo", "category": "service"}},
            "source_files": ["src/main/java/Foo.java"],
            "maven_compile_cmd": "mvn test-compile -q",
        }
        path = write_project_analysis(str(tmp_path), "# Project Analysis\n\nSome content.\n", data)
        assert path.exists()
        assert "analysis.md" in str(path)
        # Not inside sessions/
        assert "sessions" not in str(path)

        result = read_project_analysis_data(str(tmp_path))
        assert result is not None
        assert "class_index" in result
        assert result["class_index"]["Foo"]["class_name"] == "Foo"
        assert result["maven_compile_cmd"] == "mvn test-compile -q"

    def test_write_project_analysis_has_frontmatter(self, tmp_path):
        from src.lib.session_tracker import (
            get_project_analysis_path,
            write_project_analysis,
        )
        init_project(str(tmp_path))
        write_project_analysis(str(tmp_path), "# Title\n", {"key": "val"})
        content = get_project_analysis_path(str(tmp_path)).read_text()
        assert "---" in content
        assert "status: completed" in content
        assert "updated_at:" in content

    def test_read_project_analysis_returns_none_when_missing(self, tmp_path):
        from src.lib.session_tracker import read_project_analysis_data
        result = read_project_analysis_data(str(tmp_path))
        assert result is None

    def test_read_project_analysis_returns_none_on_invalid_json(self, tmp_path):
        from src.lib.session_tracker import (
            get_project_analysis_path,
            read_project_analysis_data,
        )
        init_project(str(tmp_path))
        # Write a file with no valid JSON block
        get_project_analysis_path(str(tmp_path)).write_text(
            "---\nstatus: completed\n---\n\n# No JSON here\n", encoding="utf-8"
        )
        result = read_project_analysis_data(str(tmp_path))
        assert result is None


# ============================================================================
# Human-in-the-loop: emit_question / consume_answer (spike)
# ============================================================================


class TestEmitQuestion:
    def _new_session(self, tmp_path):
        from src.lib.session_tracker import create_session, init_project
        init_project(str(tmp_path))
        return create_session(str(tmp_path), name="hitl")

    def test_writes_question_json(self, tmp_path):
        import json

        from src.lib.session_tracker import emit_question
        session = self._new_session(tmp_path)
        path = emit_question(
            session["session_dir"],
            "generation",
            {"kind": "missing_business_context", "question": "What are the rules?"},
        )
        assert path.name == "question.json"
        assert path.exists()
        payload = json.loads(path.read_text())
        assert payload["kind"] == "missing_business_context"
        assert payload["step"] == "generation"
        assert payload["question"] == "What are the rules?"
        assert "created_at" in payload

    def test_sets_status_awaiting_input(self, tmp_path):
        from pathlib import Path

        from src.lib.session_tracker import (
            STATUS_AWAITING_INPUT,
            _parse_frontmatter,
            emit_question,
        )
        session = self._new_session(tmp_path)
        emit_question(session["session_dir"], "generation", {"question": "?"})
        step_file = (Path(session["session_dir"]) / "generation.md")
        fm = _parse_frontmatter(step_file.read_text())
        assert fm["status"] == STATUS_AWAITING_INPUT

    def test_preserves_explicit_step_and_timestamp(self, tmp_path):
        import json

        from src.lib.session_tracker import emit_question
        session = self._new_session(tmp_path)
        path = emit_question(
            session["session_dir"],
            "generation",
            {"step": "custom", "created_at": "2024-01-01T00:00:00Z", "question": "?"},
        )
        payload = json.loads(path.read_text())
        assert payload["step"] == "custom"
        assert payload["created_at"] == "2024-01-01T00:00:00Z"


class TestConsumeAnswer:
    def _new_session(self, tmp_path):
        from src.lib.session_tracker import create_session, init_project
        init_project(str(tmp_path))
        return create_session(str(tmp_path), name="hitl")

    def test_reads_answer_payload(self, tmp_path):
        import json

        from src.lib.session_tracker import consume_answer
        session = self._new_session(tmp_path)
        answer = tmp_path / "answer.json"
        answer.write_text(json.dumps({"test_requirements": [{"scenario": "edge"}]}))
        payload = consume_answer(session["session_dir"], answer)
        assert payload == {"test_requirements": [{"scenario": "edge"}]}

    def test_writes_consumed_copy(self, tmp_path):
        import json
        from pathlib import Path

        from src.lib.session_tracker import consume_answer
        session = self._new_session(tmp_path)
        answer = tmp_path / "answer.json"
        answer.write_text(json.dumps({"k": "v"}))
        consume_answer(session["session_dir"], answer)
        consumed = Path(session["session_dir"]) / "answer.json.consumed"
        assert consumed.exists()
        assert json.loads(consumed.read_text()) == {"k": "v"}

    def test_clears_existing_question(self, tmp_path):
        import json
        from pathlib import Path

        from src.lib.session_tracker import consume_answer, emit_question
        session = self._new_session(tmp_path)
        emit_question(session["session_dir"], "generation", {"question": "?"})
        qpath = Path(session["session_dir"]) / "question.json"
        assert qpath.exists()

        answer = tmp_path / "answer.json"
        answer.write_text(json.dumps({"k": "v"}))
        consume_answer(session["session_dir"], answer)
        assert not qpath.exists()

    def test_missing_file_raises(self, tmp_path):
        from src.lib.session_tracker import consume_answer
        session = self._new_session(tmp_path)
        try:
            consume_answer(session["session_dir"], tmp_path / "nope.json")
        except FileNotFoundError:
            return
        raise AssertionError("expected FileNotFoundError")

    def test_malformed_json_raises(self, tmp_path):
        from src.lib.session_tracker import consume_answer
        session = self._new_session(tmp_path)
        bad = tmp_path / "bad.json"
        bad.write_text("{ not json")
        try:
            consume_answer(session["session_dir"], bad)
        except ValueError:
            return
        raise AssertionError("expected ValueError")

    def test_non_object_top_level_raises(self, tmp_path):
        from src.lib.session_tracker import consume_answer
        session = self._new_session(tmp_path)
        bad = tmp_path / "list.json"
        bad.write_text("[1, 2, 3]")
        try:
            consume_answer(session["session_dir"], bad)
        except ValueError:
            return
        raise AssertionError("expected ValueError")


# ============================================================================
# Per-file cursor (P1.1)
# ============================================================================


class TestFileCursor:
    def _new_session(self, tmp_path):
        from src.lib.session_tracker import create_session, init_project
        init_project(str(tmp_path))
        return create_session(str(tmp_path), name="cursor")

    def test_load_returns_none_when_absent(self, tmp_path):
        from src.lib.session_tracker import load_generation_cursor
        session = self._new_session(tmp_path)
        assert load_generation_cursor(session["session_dir"]) is None

    def test_save_then_load_roundtrip(self, tmp_path):
        from src.lib.session_tracker import load_generation_cursor, save_generation_cursor
        session = self._new_session(tmp_path)
        save_generation_cursor(
            session["session_dir"],
            target_files=["a.java", "b.java", "c.java"],
            current_index=1,
            completed_files=["a.java"],
        )
        cursor = load_generation_cursor(session["session_dir"])
        assert cursor["target_files"] == ["a.java", "b.java", "c.java"]
        assert cursor["current_index"] == 1
        assert cursor["completed_files"] == ["a.java"]
        assert "updated_at" in cursor

    def test_save_overwrites_existing(self, tmp_path):
        from src.lib.session_tracker import load_generation_cursor, save_generation_cursor
        session = self._new_session(tmp_path)
        save_generation_cursor(
            session["session_dir"],
            target_files=["a"], current_index=0, completed_files=[],
        )
        save_generation_cursor(
            session["session_dir"],
            target_files=["a"], current_index=1, completed_files=["a"],
        )
        cursor = load_generation_cursor(session["session_dir"])
        assert cursor["current_index"] == 1
        assert cursor["completed_files"] == ["a"]

    def test_clear_removes_file(self, tmp_path):
        from src.lib.session_tracker import (
            clear_generation_cursor,
            load_generation_cursor,
            save_generation_cursor,
        )
        session = self._new_session(tmp_path)
        save_generation_cursor(
            session["session_dir"],
            target_files=["a"], current_index=0, completed_files=[],
        )
        clear_generation_cursor(session["session_dir"])
        assert load_generation_cursor(session["session_dir"]) is None
        # idempotent: clearing again is fine
        clear_generation_cursor(session["session_dir"])


# ============================================================================
# Cleanup helpers (P3.1)
# ============================================================================


class TestSessionCleanup:
    def test_list_sessions_empty(self, tmp_path):
        from src.lib.session_tracker import init_project, list_sessions
        init_project(str(tmp_path))
        assert list_sessions(str(tmp_path)) == []

    def test_list_sessions_returns_meta(self, tmp_path):
        from src.lib.session_tracker import create_session, init_project, list_sessions
        init_project(str(tmp_path))
        create_session(str(tmp_path), name="first")
        sessions = list_sessions(str(tmp_path))
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == "001-first"
        assert sessions[0]["status"] in ("in_progress", "pending")

    def test_find_abandoned_returns_only_old_awaiting(self, tmp_path):
        from src.lib.session_tracker import (
            STATUS_AWAITING_INPUT,
            create_session,
            find_abandoned_sessions,
            init_project,
        )
        init_project(str(tmp_path))
        s1 = create_session(str(tmp_path), name="recent")
        s2 = create_session(str(tmp_path), name="old")

        # Both flipped to awaiting_input; backdate s2 in the spec
        for sid in (s1["session_id"], s2["session_id"]):
            spec = tmp_path / ".testboost" / "sessions" / sid / "spec.md"
            content = spec.read_text()
            content = content.replace("status: in_progress", f"status: {STATUS_AWAITING_INPUT}")
            spec.write_text(content)
        # Backdate s2 to 48h ago
        old_spec = tmp_path / ".testboost" / "sessions" / s2["session_id"] / "spec.md"
        c = old_spec.read_text()
        import re
        c = re.sub(
            r"started_at:.*", "started_at: 2020-01-01T00:00:00Z", c, count=1,
        )
        old_spec.write_text(c)

        found = find_abandoned_sessions(str(tmp_path), ttl_hours=24)
        ids = [s["session_id"] for s in found]
        assert s2["session_id"] in ids
        assert s1["session_id"] not in ids

    def test_mark_abandoned_flips_status(self, tmp_path):
        from src.lib.session_tracker import (
            STATUS_ABANDONED,
            _parse_frontmatter,
            create_session,
            init_project,
            mark_abandoned,
        )
        init_project(str(tmp_path))
        s = create_session(str(tmp_path), name="x")
        mark_abandoned(s["session_dir"])
        fm = _parse_frontmatter((tmp_path / ".testboost" / "sessions" / s["session_id"] / "spec.md").read_text())
        assert fm["status"] == STATUS_ABANDONED


class TestPauseVisibleAtSessionLevel:
    """P5.C — a real pause (emit_question) must be visible in spec.md so
    cleanup/find_abandoned_sessions can detect it without manual edits."""

    def test_emit_question_flips_spec_status(self, tmp_path):
        from src.lib.session_tracker import (
            STATUS_AWAITING_INPUT,
            _parse_frontmatter,
            create_session,
            emit_question,
            init_project,
        )
        init_project(str(tmp_path))
        s = create_session(str(tmp_path), name="hitl")
        emit_question(
            s["session_dir"], "generation", {"question": "?"},
            project_path=str(tmp_path), session_id=s["session_id"],
        )
        spec = tmp_path / ".testboost" / "sessions" / s["session_id"] / "spec.md"
        fm = _parse_frontmatter(spec.read_text())
        assert fm["status"] == STATUS_AWAITING_INPUT

    def test_resumed_step_lifts_awaiting_status(self, tmp_path):
        from src.lib.session_tracker import (
            STATUS_IN_PROGRESS,
            _parse_frontmatter,
            create_session,
            emit_question,
            init_project,
            update_step_file,
        )
        init_project(str(tmp_path))
        s = create_session(str(tmp_path), name="hitl")
        emit_question(s["session_dir"], "generation", {"question": "?"})
        update_step_file(
            s["session_dir"], "generation", STATUS_IN_PROGRESS, "# resuming",
        )
        spec = tmp_path / ".testboost" / "sessions" / s["session_id"] / "spec.md"
        fm = _parse_frontmatter(spec.read_text())
        assert fm["status"] == STATUS_IN_PROGRESS

    def test_emitted_pause_is_found_by_cleanup(self, tmp_path):
        """End-to-end: emit_question → find_abandoned_sessions, with NO
        manual status edit (only the timestamp is backdated via _now_iso)."""
        from unittest.mock import patch

        from src.lib import session_tracker
        from src.lib.session_tracker import (
            create_session,
            emit_question,
            find_abandoned_sessions,
            init_project,
        )
        init_project(str(tmp_path))
        # Create the session "two days ago"
        with patch.object(session_tracker, "_now_iso", return_value="2020-01-01T00:00:00Z"):
            s = create_session(str(tmp_path), name="old-pause")
            emit_question(s["session_dir"], "generation", {"question": "?"})

        found = find_abandoned_sessions(str(tmp_path), ttl_hours=24)
        assert [x["session_id"] for x in found] == [s["session_id"]]


class TestBatchQuestionRendering:
    """P6.A — multi-item questions render as one MR-ready comment."""

    def test_batch_markdown_lists_items_and_combined_schema(self, tmp_path):
        import json as _json

        from src.lib.session_tracker import create_session, emit_question, init_project
        init_project(str(tmp_path))
        s = create_session(str(tmp_path), name="batch")
        payload = {
            "kind": "batch",
            "question": "2 file(s) need your input.",
            "items": [
                {
                    "kind": "missing_business_context",
                    "subject": {"class_name": "OrderService"},
                    "question": "No edge cases for OrderService.",
                    "answer_schema": {"test_requirements": {"OrderService": []}},
                },
                {
                    "kind": "compilation_fix_exhausted",
                    "subject": {"class_name": "UserController"},
                    "question": "Cannot compile UserControllerTest.",
                    "answer_schema": {"compile_fixes": {"UserController": {}}},
                },
            ],
            "answer_schema": {
                "test_requirements": {"OrderService": []},
                "compile_fixes": {"UserController": {}},
            },
        }
        qpath = emit_question(
            s["session_dir"], "generation", payload,
            project_path=str(tmp_path), session_id=s["session_id"],
        )
        question = _json.loads(qpath.read_text())
        preview = question["markdown_preview"]
        assert "2 item(s)" in preview
        assert "#### 1. missing_business_context" in preview
        assert "#### 2. compilation_fix_exhausted" in preview
        assert "OrderService" in preview and "UserController" in preview
        assert "combining your answers" in preview


class TestAnswerFinalization:
    """P6.C — verify-then-finalize keeps a crashed resume retryable."""

    def _session_with_question(self, tmp_path):
        from src.lib.session_tracker import create_session, emit_question, init_project
        init_project(str(tmp_path))
        s = create_session(str(tmp_path), name="hitl")
        emit_question(
            s["session_dir"], "generation", {"question": "?"},
            project_path=str(tmp_path), session_id=s["session_id"],
        )
        return s

    def test_load_and_verify_keeps_question_in_place(self, tmp_path):
        import json as _json
        from pathlib import Path

        from src.lib.integrity import sign_answer
        from src.lib.session_tracker import load_and_verify_answer
        s = self._session_with_question(tmp_path)
        sdir = Path(s["session_dir"])
        question = _json.loads((sdir / "question.json").read_text())
        signed = sign_answer({"test_requirements": {}}, question, str(tmp_path))
        afile = tmp_path / "answer.json"
        afile.write_text(_json.dumps(signed))

        payload = load_and_verify_answer(str(sdir), afile, project_path=str(tmp_path))

        assert payload["question_id"] == question["question_id"]
        # Question still pending, no consumed marker: a crash here is retryable
        assert (sdir / "question.json").exists()
        assert not (sdir / "answer.json.consumed").exists()

    def test_finalize_consumes_and_clears(self, tmp_path):
        import json as _json
        from pathlib import Path

        from src.lib.session_tracker import finalize_answer
        s = self._session_with_question(tmp_path)
        sdir = Path(s["session_dir"])

        finalize_answer(str(sdir), {"test_requirements": {}})

        assert not (sdir / "question.json").exists()
        consumed = _json.loads((sdir / "answer.json.consumed").read_text())
        assert consumed == {"test_requirements": {}}
