# SPDX-License-Identifier: Apache-2.0
"""Unit tests for testboost_lite.lib.integrity."""


import pytest

from testboost_lite.lib.integrity import (
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


class TestEmitToken:
    def test_emit_prints_token(self, project_with_testboost, capsys):
        token = emit_token(str(project_with_testboost), "generation", "001-test-generation")
        captured = capsys.readouterr()
        assert TOKEN_PREFIX in captured.out
        assert token in captured.out
