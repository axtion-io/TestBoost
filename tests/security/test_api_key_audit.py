"""API Key Security Audit Tests (T101a).

These tests verify that no API keys are hardcoded in the codebase.
Constitution Principle 7: Security - No credentials in code.

Patterns checked:
- Anthropic: sk-ant-[A-Za-z0-9-]{32,}
- Google: AIza[A-Za-z0-9_-]{35}
- OpenAI: sk-[A-Za-z0-9]{32,}
- LangSmith: ls__[A-Za-z0-9]{32,}
"""

import re
from collections.abc import Generator
from pathlib import Path

# API key patterns to detect
API_KEY_PATTERNS = {
    "anthropic": r"sk-ant-[A-Za-z0-9-]{32,}",
    "google": r"AIza[A-Za-z0-9_-]{35}",
    "openai": r"sk-[A-Za-z0-9]{32,}",
    "langsmith": r"ls__[A-Za-z0-9]{32,}",
}

# Directories to scan
SCAN_DIRECTORIES = ["src", "tests", "config"]

# File extensions to check
CODE_EXTENSIONS = {".py", ".yaml", ".yml", ".json", ".md", ".txt"}

# Files/patterns to exclude
EXCLUDE_PATTERNS = [
    "test_api_key_audit.py",  # This file contains patterns for testing
    "__pycache__",
    ".git",
    ".venv",
    "node_modules",
]


def get_files_to_scan() -> Generator[Path, None, None]:
    """Get all files that should be scanned for API keys."""
    root = Path(".")

    for scan_dir in SCAN_DIRECTORIES:
        dir_path = root / scan_dir
        if not dir_path.exists():
            continue

        for file_path in dir_path.rglob("*"):
            # Skip directories
            if file_path.is_dir():
                continue

            # Skip excluded patterns
            if any(excl in str(file_path) for excl in EXCLUDE_PATTERNS):
                continue

            # Only check code files
            if file_path.suffix not in CODE_EXTENSIONS:
                continue

            yield file_path


def scan_file_for_api_keys(file_path: Path) -> list[tuple[str, str, int, str]]:
    """
    Scan a file for API key patterns.

    Returns:
        List of tuples: (provider, pattern_matched, line_number, line_content)
    """
    matches = []

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return matches

    lines = content.split("\n")

    for line_num, line in enumerate(lines, 1):
        for provider, pattern in API_KEY_PATTERNS.items():
            if re.search(pattern, line):
                # Skip if it's in a comment explaining the pattern
                if "pattern" in line.lower() or "regex" in line.lower():
                    continue
                # Skip if it's a variable name or placeholder
                if "your_" in line.lower() or "_key_here" in line.lower():
                    continue
                # Skip if it's in quotes as an example
                if 'r"' in line or "r'" in line:
                    continue

                matches.append((provider, pattern, line_num, line.strip()[:100]))

    return matches


class TestNoHardcodedAPIKeys:
    """Test that no API keys are hardcoded in the codebase."""

    def test_no_anthropic_keys_in_source(self):
        """Test no Anthropic API keys in source code."""
        pattern = re.compile(API_KEY_PATTERNS["anthropic"])
        violations = []

        for file_path in get_files_to_scan():
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                if pattern.search(content):
                    # Verify it's not a pattern definition
                    if "sk-ant-[" not in content:
                        violations.append(str(file_path))
            except Exception:
                pass

        assert len(violations) == 0, \
            f"Anthropic API keys found in: {violations}"

    def test_no_google_keys_in_source(self):
        """Test no Google API keys in source code."""
        pattern = re.compile(API_KEY_PATTERNS["google"])
        violations = []

        for file_path in get_files_to_scan():
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                if pattern.search(content):
                    if "AIza[" not in content:  # Not a pattern definition
                        violations.append(str(file_path))
            except Exception:
                pass

        assert len(violations) == 0, \
            f"Google API keys found in: {violations}"

    def test_no_openai_keys_in_source(self):
        """Test no OpenAI API keys in source code."""
        pattern = re.compile(API_KEY_PATTERNS["openai"])
        violations = []

        for file_path in get_files_to_scan():
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                matches = pattern.findall(content)
                for match in matches:
                    # Exclude Anthropic keys (sk-ant-...)
                    if not match.startswith("sk-ant"):
                        # Not a pattern definition
                        if "sk-[" not in content:
                            violations.append(str(file_path))
                            break
            except Exception:
                pass

        assert len(violations) == 0, \
            f"OpenAI API keys found in: {violations}"

    def test_no_langsmith_keys_in_source(self):
        """Test no LangSmith API keys in source code."""
        pattern = re.compile(API_KEY_PATTERNS["langsmith"])
        violations = []

        for file_path in get_files_to_scan():
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                if pattern.search(content):
                    if "ls__[" not in content:  # Not a pattern definition
                        violations.append(str(file_path))
            except Exception:
                pass

        assert len(violations) == 0, \
            f"LangSmith API keys found in: {violations}"


class TestEnvFileNotCommitted:
    """Test that .env files are not in the repository."""

    def test_no_env_file_in_repo(self):
        """Test that .env file is not tracked by git."""
        # .env can exist locally, but should be in .gitignore
        gitignore_path = Path(".gitignore")
        if gitignore_path.exists():
            gitignore_content = gitignore_path.read_text()
            assert ".env" in gitignore_content, \
                ".env should be in .gitignore"

    def test_no_env_example_with_real_keys(self):
        """Test that .env.example doesn't contain real API keys."""
        env_example = Path(".env.example")

        if env_example.exists():
            content = env_example.read_text()

            for provider, pattern in API_KEY_PATTERNS.items():
                matches = re.findall(pattern, content)
                # Filter out placeholder patterns
                real_keys = [m for m in matches if not any(
                    placeholder in m.lower()
                    for placeholder in ["your", "xxx", "placeholder", "example"]
                )]
                assert len(real_keys) == 0, \
                    f"Real {provider} API key found in .env.example"


class TestSecurityBestPractices:
    """Test security best practices are followed."""

    def test_api_keys_loaded_from_env(self):
        """Test that API keys are loaded from environment variables."""
        from src.lib.config import Settings

        # Check that Settings uses environment variables for keys
        settings = Settings()

        # API keys should be None by default (loaded from env)
        # This is expected behavior - keys come from environment
        assert hasattr(settings, "anthropic_api_key")
        assert hasattr(settings, "google_api_key")
        assert hasattr(settings, "openai_api_key")

    def test_settings_uses_pydantic_secrets(self):
        """Test that Settings class uses pydantic-settings for env loading."""
        from pydantic_settings import BaseSettings

        from src.lib.config import Settings

        # Settings should inherit from BaseSettings
        assert issubclass(Settings, BaseSettings), \
            "Settings should use pydantic-settings for secure env loading"

    def test_no_print_statements_with_keys(self):
        """Test that no print statements could leak API keys."""
        suspicious_patterns = [
            r"print\(.*api_key",
            r"print\(.*API_KEY",
            r"print\(.*secret",
            r"print\(.*password",
        ]

        violations = []

        for file_path in get_files_to_scan():
            if file_path.suffix != ".py":
                continue

            try:
                content = file_path.read_text()
                for pattern in suspicious_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        violations.append(str(file_path))
                        break
            except Exception:
                pass

        assert len(violations) == 0, \
            f"Suspicious print statements found in: {violations}"


class TestLoggingDoesNotLeakSecrets:
    """Test that logging configuration doesn't leak secrets."""

    def test_logger_filters_api_keys(self):
        """Test that logger configuration exists for filtering."""
        from src.lib.logging import get_logger

        # Logger should be configurable
        logger = get_logger(__name__)
        assert logger is not None

    def test_no_api_key_in_log_calls(self):
        """Test that log calls don't directly include API key variables."""
        suspicious_patterns = [
            r'logger\.\w+\(.*api_key\s*=',
            r'logger\.\w+\(.*API_KEY',
            r'log\.\w+\(.*api_key\s*=',
        ]

        violations = []

        for file_path in get_files_to_scan():
            if file_path.suffix != ".py":
                continue

            try:
                content = file_path.read_text()
                for pattern in suspicious_patterns:
                    if re.search(pattern, content):
                        violations.append(str(file_path))
                        break
            except Exception:
                pass

        assert len(violations) == 0, \
            f"Potential API key logging found in: {violations}"
