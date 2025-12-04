"""
Security audit tests for detecting hardcoded API keys in the codebase.

This module scans all Python files for patterns matching known API key formats
from Anthropic, Google, and OpenAI to prevent accidental credential exposure.
"""

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False

# API key patterns to detect
API_KEY_PATTERNS = {
    "Anthropic": r"sk-ant-[A-Za-z0-9-]{32,}",
    "Google": r"AIza[A-Za-z0-9_-]{35}",
    "OpenAI": r"sk-[A-Za-z0-9]{32,}",
}

# Directories to exclude from scanning
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".tox",
    "dist",
    "build",
    "*.egg-info",
}

# Files to exclude (test files and this audit file itself)
EXCLUDED_FILES = {
    "test_api_key_audit.py",
}


@dataclass
class KeyMatch:
    """Represents a detected API key match."""

    file_path: str
    line_number: int
    provider: str
    matched_text: str
    line_content: str


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


def should_exclude_path(path: Path) -> bool:
    """Check if a path should be excluded from scanning."""
    path_parts = path.parts
    for excluded in EXCLUDED_DIRS:
        if excluded in path_parts:
            return True
    return False


def find_python_files(root: Path) -> list[Path]:
    """Find all Python files in the project, excluding specified directories."""
    python_files = []
    for py_file in root.rglob("*.py"):
        if should_exclude_path(py_file):
            continue
        if py_file.name in EXCLUDED_FILES:
            continue
        python_files.append(py_file)
    return python_files


def scan_file_for_keys(file_path: Path) -> list[KeyMatch]:
    """Scan a single file for API key patterns."""
    matches = []
    try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        for line_num, line in enumerate(lines, start=1):
            # Skip comments that explain patterns (like in this test file)
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue

            for provider, pattern in API_KEY_PATTERNS.items():
                for match in re.finditer(pattern, line):
                    # Skip if the match is inside a regex pattern definition (quoted)
                    # This avoids false positives from pattern definitions like r"sk-ant-..."
                    match_start = match.start()
                    preceding_content = line[:match_start]

                    # Check if match is inside a string that defines a regex pattern
                    if 'r"' in preceding_content or "r'" in preceding_content:
                        # Check if we're still inside that string
                        quote_char = '"' if 'r"' in preceding_content else "'"
                        last_r_quote = preceding_content.rfind(f"r{quote_char}")
                        if last_r_quote != -1:
                            # Count quotes after r" to see if string is closed
                            after_r_quote = preceding_content[last_r_quote + 2:]
                            if after_r_quote.count(quote_char) % 2 == 0:
                                # We're inside a raw string (regex pattern definition)
                                continue

                    matches.append(
                        KeyMatch(
                            file_path=str(file_path.relative_to(get_project_root())),
                            line_number=line_num,
                            provider=provider,
                            matched_text=match.group()[:20] + "..." if len(match.group()) > 20 else match.group(),
                            line_content=line.strip()[:100],
                        )
                    )
    except (OSError, UnicodeDecodeError) as e:
        print(f"Warning: Could not read {file_path}: {e}")

    return matches


def scan_codebase() -> tuple[list[KeyMatch], list[Path]]:
    """Scan the entire codebase for API keys."""
    root = get_project_root()
    python_files = find_python_files(root)
    all_matches = []

    for py_file in python_files:
        matches = scan_file_for_keys(py_file)
        all_matches.extend(matches)

    return all_matches, python_files


def generate_audit_report(matches: list[KeyMatch], scanned_files: list[Path]) -> str:
    """Generate a markdown audit report."""
    report_lines = [
        "# API Key Security Audit Report",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        f"- **Files scanned:** {len(scanned_files)}",
        f"- **API keys detected:** {len(matches)}",
        f"- **Status:** {'PASS' if len(matches) == 0 else 'FAIL'}",
        "",
        "## Patterns Checked",
        "",
        "| Provider | Pattern |",
        "|----------|---------|",
    ]

    for provider, pattern in API_KEY_PATTERNS.items():
        report_lines.append(f"| {provider} | `{pattern}` |")

    report_lines.extend([
        "",
        "## Results",
        "",
    ])

    if matches:
        report_lines.extend([
            "### Detected API Keys",
            "",
            "| File | Line | Provider | Matched Text |",
            "|------|------|----------|--------------|",
        ])
        for match in matches:
            report_lines.append(
                f"| {match.file_path} | {match.line_number} | {match.provider} | `{match.matched_text}` |"
            )
        report_lines.extend([
            "",
            "**Action Required:** Remove or externalize the detected API keys immediately.",
            "",
        ])
    else:
        report_lines.extend([
            "No hardcoded API keys detected in the codebase.",
            "",
        ])

    report_lines.extend([
        "## Scanned Files",
        "",
        "<details>",
        "<summary>Click to expand file list</summary>",
        "",
    ])

    for file_path in sorted(scanned_files):
        relative_path = file_path.relative_to(get_project_root())
        report_lines.append(f"- `{relative_path}`")

    report_lines.extend([
        "",
        "</details>",
        "",
        "---",
        "*This report was generated by `tests/security/test_api_key_audit.py`*",
    ])

    return "\n".join(report_lines)


class TestApiKeyAudit:
    """Test class for API key security audits."""

    def test_no_anthropic_keys_in_codebase(self):
        """Verify no Anthropic API keys (sk-ant-*) are hardcoded."""
        matches, _ = scan_codebase()
        anthropic_matches = [m for m in matches if m.provider == "Anthropic"]

        assert len(anthropic_matches) == 0, (
            f"Found {len(anthropic_matches)} Anthropic API key(s) in codebase:\n"
            + "\n".join(f"  - {m.file_path}:{m.line_number}" for m in anthropic_matches)
        )

    def test_no_google_keys_in_codebase(self):
        """Verify no Google API keys (AIza*) are hardcoded."""
        matches, _ = scan_codebase()
        google_matches = [m for m in matches if m.provider == "Google"]

        assert len(google_matches) == 0, (
            f"Found {len(google_matches)} Google API key(s) in codebase:\n"
            + "\n".join(f"  - {m.file_path}:{m.line_number}" for m in google_matches)
        )

    def test_no_openai_keys_in_codebase(self):
        """Verify no OpenAI API keys (sk-*) are hardcoded."""
        matches, _ = scan_codebase()
        openai_matches = [m for m in matches if m.provider == "OpenAI"]

        assert len(openai_matches) == 0, (
            f"Found {len(openai_matches)} OpenAI API key(s) in codebase:\n"
            + "\n".join(f"  - {m.file_path}:{m.line_number}" for m in openai_matches)
        )

    def test_no_api_keys_in_codebase(self):
        """Comprehensive test: verify ZERO API keys from any provider."""
        matches, scanned_files = scan_codebase()

        # Generate report regardless of result
        report = generate_audit_report(matches, scanned_files)
        report_path = Path(__file__).parent / "audit_report.md"
        report_path.write_text(report, encoding="utf-8")

        assert len(matches) == 0, (
            f"SECURITY ALERT: Found {len(matches)} API key(s) in codebase!\n"
            f"See {report_path} for details.\n"
            + "\n".join(
                f"  - [{m.provider}] {m.file_path}:{m.line_number}"
                for m in matches
            )
        )

    def test_audit_report_generation(self):
        """Test that audit report is generated correctly."""
        matches, scanned_files = scan_codebase()
        report = generate_audit_report(matches, scanned_files)

        # Verify report structure
        assert "# API Key Security Audit Report" in report
        assert "## Summary" in report
        assert "## Patterns Checked" in report
        assert "## Results" in report
        assert "## Scanned Files" in report

        # Verify patterns are documented
        for provider in API_KEY_PATTERNS:
            assert provider in report


# Allow running as standalone script
if __name__ == "__main__":
    print("Running API Key Security Audit...")
    print("=" * 50)

    matches, scanned_files = scan_codebase()

    print(f"\nScanned {len(scanned_files)} Python files")
    print(f"Found {len(matches)} potential API key(s)")

    if matches:
        print("\n SECURITY ALERT: API keys detected!")
        for match in matches:
            print(f"  [{match.provider}] {match.file_path}:{match.line_number}")
    else:
        print("\n All clear: No API keys detected")

    # Generate report
    report = generate_audit_report(matches, scanned_files)
    report_path = Path(__file__).parent / "audit_report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nAudit report saved to: {report_path}")
