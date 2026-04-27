# SPDX-License-Identifier: Apache-2.0
"""Go testing plugin stub for TestBoost.

This stub demonstrates how a third plugin can be added by:
1. Creating this file (one new file)
2. Adding register(GoTestingPlugin()) in __init__.py (one line)

No changes to the core engine are required.

NOTE: This is a minimal proof-of-concept stub. It demonstrates interface compliance
but does not provide real Go source analysis. A production Go plugin would use
`go/ast` via subprocess or a Go analysis tool.
"""

from pathlib import Path

from src.lib.plugins.base import TechnologyPlugin


class GoTestingPlugin(TechnologyPlugin):
    """Stub plugin for Go projects using the standard `go test` toolchain.

    Detection: checks for go.mod in the project root.
    """

    @property
    def identifier(self) -> str:
        return "go-testing"

    @property
    def description(self) -> str:
        return "Go projects using the standard go test toolchain"

    @property
    def detection_patterns(self) -> list[str]:
        return ["go.mod"]

    @property
    def prompt_template_dir(self) -> str:
        # A full plugin would have its own templates; reuse Java dir as placeholder
        return "config/prompts/testing"

    # ------------------------------------------------------------------
    # Source discovery
    # ------------------------------------------------------------------

    def find_source_files(self, project_path: Path) -> list[str]:
        """Discover non-test Go source files."""
        project_path = Path(project_path)
        result = []
        for go_file in sorted(project_path.rglob("*.go")):
            name = go_file.name
            if name.endswith("_test.go"):
                continue
            # Skip vendor directory
            parts = go_file.relative_to(project_path).parts
            if "vendor" in parts:
                continue
            relative = str(go_file.relative_to(project_path)).replace("\\", "/")
            result.append(relative)
        return result

    def classify_source_file(self, relative_path: str) -> str:
        """Basic classification for Go source files."""
        path_lower = relative_path.lower()
        if "handler" in path_lower or "controller" in path_lower:
            return "handler"
        if "service" in path_lower:
            return "service"
        if "repository" in path_lower or "store" in path_lower:
            return "repository"
        return "other"

    # ------------------------------------------------------------------
    # Test file naming
    # ------------------------------------------------------------------

    def test_file_name(self, source_relative_path: str) -> str:
        """Derive Go test file: foo.go → foo_test.go."""
        normalized = source_relative_path.replace("\\", "/")
        if normalized.endswith(".go"):
            return normalized[:-3] + "_test.go"
        return source_relative_path + "_test.go"

    def test_file_pattern(self) -> list[str]:
        return ["**/*_test.go"]

    # ------------------------------------------------------------------
    # Build commands
    # ------------------------------------------------------------------

    def validation_command(self, project_path: Path, session_config: dict) -> list[str]:
        return ["go", "build", "./..."]

    def test_run_command(self, project_path: Path, session_config: dict) -> list[str]:
        return ["go", "test", "./..."]

    # ------------------------------------------------------------------
    # Generation context
    # ------------------------------------------------------------------

    def build_generation_context(self, project_path: Path, source_file: str) -> dict:
        """Return minimal context for Go test generation."""
        source_path = Path(source_file)
        if not source_path.is_absolute():
            source_path = Path(project_path) / source_file

        try:
            source_code = source_path.read_text(encoding="utf-8")
        except OSError:
            source_code = ""

        return {
            "source_code": source_code,
            "class_name": source_path.stem,
            "class_type": self.classify_source_file(str(source_file)),
            "dependencies": [],
            "existing_tests": [],
            "conventions": {},
        }
