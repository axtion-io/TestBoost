# SPDX-License-Identifier: Apache-2.0
"""Unit tests for src.lib.integrity."""


import pytest

from src.lib.integrity import (
    TOKEN_PREFIX,
    emit_token,
    generate_token,
    get_or_create_secret,
    verify_token,
)


@pytest.fixture
def project_with_testboost(tmp_path):
    """Create a project with .testboost/ directory."""
    tb_dir = tmp_path / ".testboost"
    tb_dir.mkdir()
    return tmp_path


class TestGetOrCreateSecret:
    def test_creates_secret_on_first_call(self, project_with_testboost):
        secret = get_or_create_secret(str(project_with_testboost))
        assert len(secret) == 64  # 32 bytes hex = 64 chars
        assert (project_with_testboost / ".testboost" / ".tb_secret").exists()

    def test_returns_same_secret_on_second_call(self, project_with_testboost):
        secret1 = get_or_create_secret(str(project_with_testboost))
        secret2 = get_or_create_secret(str(project_with_testboost))
        assert secret1 == secret2

    def test_adds_to_gitignore(self, project_with_testboost):
        get_or_create_secret(str(project_with_testboost))
        gitignore = (project_with_testboost / ".testboost" / ".gitignore").read_text()
        assert ".tb_secret" in gitignore

    def test_creates_testboost_dir_if_missing(self, tmp_path):
        secret = get_or_create_secret(str(tmp_path))
        assert len(secret) == 64
        assert (tmp_path / ".testboost" / ".tb_secret").exists()


class TestGenerateToken:
    def test_generates_token_with_correct_format(self, project_with_testboost):
        token = generate_token(str(project_with_testboost), "analysis", "001-test-generation")
        assert token.startswith("[TESTBOOST_INTEGRITY:sha256=")
        assert token.endswith("]")
        assert ":analysis:" in token
        assert ":001-test-generation:" in token

    def test_different_steps_produce_different_tokens(self, project_with_testboost):
        t1 = generate_token(str(project_with_testboost), "analysis", "001-test-generation")
        t2 = generate_token(str(project_with_testboost), "generation", "001-test-generation")
        assert t1 != t2


class TestVerifyToken:
    def test_valid_token_verifies(self, project_with_testboost):
        token = generate_token(str(project_with_testboost), "analysis", "001-test-generation")
        assert verify_token(str(project_with_testboost), token) is True

    def test_tampered_token_fails(self, project_with_testboost):
        token = generate_token(str(project_with_testboost), "analysis", "001-test-generation")
        # Tamper with one character in the digest
        tampered = token[:30] + "x" + token[31:]
        assert verify_token(str(project_with_testboost), tampered) is False

    def test_fabricated_token_fails(self, project_with_testboost):
        get_or_create_secret(str(project_with_testboost))
        fake = "[TESTBOOST_INTEGRITY:sha256=abc123:analysis:001-test-generation:20260310T120000Z]"
        assert verify_token(str(project_with_testboost), fake) is False

    def test_wrong_format_fails(self, project_with_testboost):
        assert verify_token(str(project_with_testboost), "not a token") is False
        assert verify_token(str(project_with_testboost), "[TESTBOOST_INTEGRITY:md5=abc]") is False


class TestCmdVerify:
    """Tests for the CLI verify subcommand."""

    def _make_args(self, project_path, token):
        import argparse
        return argparse.Namespace(project_path=project_path, token=token)

    def test_valid_token_exits_zero(self, project_with_testboost, capsys):
        from src.lib.cli import cmd_verify

        token = generate_token(str(project_with_testboost), "init", "001-test-generation")
        args = self._make_args(str(project_with_testboost), token)
        rc = cmd_verify(args)
        captured = capsys.readouterr()
        assert rc == 0
        assert "[TESTBOOST_VERIFY:OK]" in captured.out

    def test_fabricated_token_exits_one(self, project_with_testboost, capsys):
        from src.lib.cli import cmd_verify

        get_or_create_secret(str(project_with_testboost))
        fake = "[TESTBOOST_INTEGRITY:sha256=deadbeef:init:001-test-generation:20260310T120000Z]"
        args = self._make_args(str(project_with_testboost), fake)
        rc = cmd_verify(args)
        captured = capsys.readouterr()
        assert rc == 1
        assert "[TESTBOOST_VERIFY:FAILED]" in captured.out

    def test_garbage_input_exits_one(self, project_with_testboost, capsys):
        from src.lib.cli import cmd_verify

        args = self._make_args(str(project_with_testboost), "not a token at all")
        rc = cmd_verify(args)
        captured = capsys.readouterr()
        assert rc == 1
        assert "[TESTBOOST_VERIFY:FAILED]" in captured.out

    def test_tampered_digest_exits_one(self, project_with_testboost, capsys):
        from src.lib.cli import cmd_verify

        token = generate_token(str(project_with_testboost), "analysis", "001-test-generation")
        tampered = token[:30] + ("a" if token[30] != "a" else "b") + token[31:]
        args = self._make_args(str(project_with_testboost), tampered)
        rc = cmd_verify(args)
        captured = capsys.readouterr()
        assert rc == 1
        assert "[TESTBOOST_VERIFY:FAILED]" in captured.out


class TestEmitToken:
    def test_emit_prints_token(self, project_with_testboost, capsys):
        token = emit_token(str(project_with_testboost), "generation", "001-test-generation")
        captured = capsys.readouterr()
        assert TOKEN_PREFIX in captured.out
        assert token in captured.out


# ============================================================================
# Question / answer signing (P1.3, P1.4)
# ============================================================================


class TestQuestionSigning:
    def test_sign_adds_id_and_signature(self, project_with_testboost):
        from src.lib.integrity import sign_question
        signed = sign_question(
            {"kind": "x", "question": "?"}, str(project_with_testboost)
        )
        assert "question_id" in signed
        assert len(signed["question_id"]) == 32  # 16-byte hex
        assert "signature" in signed
        assert "created_at" in signed

    def test_verify_accepts_freshly_signed(self, project_with_testboost):
        from src.lib.integrity import sign_question, verify_question
        signed = sign_question({"k": "v"}, str(project_with_testboost))
        assert verify_question(signed, str(project_with_testboost)) is True

    def test_verify_rejects_tampered_payload(self, project_with_testboost):
        from src.lib.integrity import sign_question, verify_question
        signed = sign_question({"kind": "x"}, str(project_with_testboost))
        signed["kind"] = "y"  # tamper after signing
        assert verify_question(signed, str(project_with_testboost)) is False

    def test_verify_rejects_unsigned(self, project_with_testboost):
        from src.lib.integrity import verify_question
        assert verify_question({"kind": "x"}, str(project_with_testboost)) is False


class TestAnswerSigning:
    def test_sign_answer_binds_question_id(self, project_with_testboost):
        from src.lib.integrity import sign_answer, sign_question
        q = sign_question({"q": 1}, str(project_with_testboost))
        a = sign_answer({"data": "x"}, q, str(project_with_testboost))
        assert a["question_id"] == q["question_id"]
        assert "signature" in a

    def test_verify_answer_round_trip(self, project_with_testboost):
        from src.lib.integrity import sign_answer, sign_question, verify_answer
        q = sign_question({"q": 1}, str(project_with_testboost))
        a = sign_answer({"data": "x"}, q, str(project_with_testboost))
        verify_answer(a, q, str(project_with_testboost))  # no exception

    def test_verify_answer_rejects_mismatched_question_id(self, project_with_testboost):
        from src.lib.integrity import (
            SignatureError,
            sign_answer,
            sign_question,
            verify_answer,
        )
        q1 = sign_question({"q": 1}, str(project_with_testboost))
        q2 = sign_question({"q": 2}, str(project_with_testboost))
        a = sign_answer({"data": "x"}, q1, str(project_with_testboost))
        try:
            verify_answer(a, q2, str(project_with_testboost))
        except SignatureError:
            return
        raise AssertionError("expected SignatureError on question-id mismatch")

    def test_verify_answer_rejects_tampered_content(self, project_with_testboost):
        from src.lib.integrity import (
            SignatureError,
            sign_answer,
            sign_question,
            verify_answer,
        )
        q = sign_question({"q": 1}, str(project_with_testboost))
        a = sign_answer({"data": "x"}, q, str(project_with_testboost))
        a["data"] = "tampered"
        try:
            verify_answer(a, q, str(project_with_testboost))
        except SignatureError:
            return
        raise AssertionError("expected SignatureError on tampered content")

    def test_verify_answer_rejects_tampered_question(self, project_with_testboost):
        from src.lib.integrity import (
            SignatureError,
            sign_answer,
            sign_question,
            verify_answer,
        )
        q = sign_question({"q": 1}, str(project_with_testboost))
        a = sign_answer({"data": "x"}, q, str(project_with_testboost))
        q["q"] = 999  # tamper question after answering
        try:
            verify_answer(a, q, str(project_with_testboost))
        except SignatureError:
            return
        raise AssertionError("expected SignatureError on tampered question")


class TestAnswerTTL:
    def test_verify_rejects_expired_question(self, project_with_testboost):
        from datetime import UTC, datetime, timedelta

        from src.lib.integrity import (
            ExpiredQuestionError,
            sign_answer,
            sign_question,
            verify_answer,
        )
        q = sign_question({"q": 1}, str(project_with_testboost))
        # Backdate the question past the TTL but keep the signature consistent
        old = (datetime.now(UTC) - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
        q["created_at"] = old
        # Re-sign with the back-dated timestamp so the signature is valid
        q = sign_question(
            {k: v for k, v in q.items() if k not in ("signature",)},
            str(project_with_testboost),
        )
        q["created_at"] = old  # ensure it is the back-dated value
        # Re-derive signature one more time on the back-dated payload
        from src.lib.integrity import _canonical_json, _hmac_hex, get_or_create_secret
        content = {k: v for k, v in q.items() if k != "signature"}
        q["signature"] = _hmac_hex(get_or_create_secret(str(project_with_testboost)), _canonical_json(content))

        a = sign_answer({"x": 1}, q, str(project_with_testboost))
        try:
            verify_answer(a, q, str(project_with_testboost), ttl_hours=24)
        except ExpiredQuestionError:
            return
        raise AssertionError("expected ExpiredQuestionError")


class TestSecretGitignoredWhenPreSeeded:
    """CI seeds .tb_secret from a masked variable BEFORE init runs — the
    gitignore entry must be ensured on read too, or the pause-state commit
    would push the raw secret to the MR branch."""

    def test_preseeded_secret_gets_gitignored_on_first_access(self, tmp_path):
        from src.lib.integrity import get_or_create_secret

        tb_dir = tmp_path / ".testboost"
        tb_dir.mkdir()
        (tb_dir / ".tb_secret").write_text("a" * 64)
        assert not (tb_dir / ".gitignore").exists()

        secret = get_or_create_secret(str(tmp_path))

        assert secret == "a" * 64
        gitignore = (tb_dir / ".gitignore").read_text()
        assert ".tb_secret" in gitignore

    def test_existing_gitignore_without_entry_is_amended(self, tmp_path):
        from src.lib.integrity import get_or_create_secret

        tb_dir = tmp_path / ".testboost"
        tb_dir.mkdir()
        (tb_dir / ".tb_secret").write_text("b" * 64)
        (tb_dir / ".gitignore").write_text("sessions/*/logs/*.md\n")

        get_or_create_secret(str(tmp_path))

        assert ".tb_secret" in (tb_dir / ".gitignore").read_text()
