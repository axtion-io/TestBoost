# SPDX-License-Identifier: Apache-2.0
"""Abstract base class for TestBoost technology plugins."""

from abc import ABC, abstractmethod
from pathlib import Path


class TechnologyPlugin(ABC):
    """Abstract base class that all TestBoost technology plugins must implement.

    A plugin encapsulates all technology-specific knowledge:
    - Source file discovery and classification
    - Test file patterns
    - Validation and test run commands
    - LLM prompt template directory

    Register plugins in priority order in src/lib/plugins/__init__.py.
    Python raises TypeError at instantiation if any abstract member is missing.
    """

    @property
    @abstractmethod
    def identifier(self) -> str:
        """Unique technology identifier, e.g. 'java-spring', 'python-pytest'.

        Format: lowercase, hyphen-separated, <language>-<framework>.
        Used as the value stored in session metadata (technology field)
        and with the --tech CLI override.
        """

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable single-sentence description for --list-plugins output."""

    @property
    @abstractmethod
    def detection_patterns(self) -> list[str]:
        """Filenames (not globs) to check for existence in the project root.

        OR semantics: any matching file triggers detection.
        Examples: ['pom.xml', 'build.gradle'], ['pyproject.toml', 'setup.py']
        """

    @property
    @abstractmethod
    def prompt_template_dir(self) -> str:
        """Prompt template directory, relative to src/prompts/.

        Must contain unit_test_generation.md at minimum.
        Examples: 'testing', 'testing/python_pytest'
        """

    @abstractmethod
    def find_source_files(self, project_path: Path) -> list[str]:
        """Discover all testable source files in the project.

        Args:
            project_path: Absolute path to the project root.

        Returns:
            List of paths relative to project_path, sorted alphabetically.
            Test files, build files, and generated files are excluded.
            Empty list if no files found.
        """

    @abstractmethod
    def classify_source_file(self, relative_path: str) -> str:
        """Classify a source file into a semantic category.

        Args:
            relative_path: Path relative to project root (from find_source_files).

        Returns:
            Non-empty string category. Returns 'other' for unrecognized files.
            Java examples: 'controller', 'service', 'repository', 'entity'
            Python examples: 'class', 'function', 'module'
        """

    @abstractmethod
    def test_file_name(self, source_relative_path: str) -> str:
        """Derive the test file path for a given source file.

        Used by `generate` to decide WHERE the generated test is written —
        the result must never collide with a production source path
        (history: a Java-only fallback used to return Python sources
        unchanged, overwriting them with generated tests).

        Args:
            source_relative_path: Path relative to project root.

        Returns:
            Test file path relative to project root. Deterministic for a
            given input.
        """

    @abstractmethod
    def test_file_pattern(self) -> list[str]:
        """Return glob patterns identifying test files for this technology.

        Used by the conventions detection tool.
        Examples: ['**/*Test.java', '**/*Tests.java'] or ['**/test_*.py']
        """

    @abstractmethod
    def validation_command(self, project_path: Path, session_config: dict) -> list[str]:
        """Return the command to compile/syntax-check generated tests.

        Args:
            project_path: Project root directory.
            session_config: Dict from session metadata (may contain command overrides
                such as maven_compile_cmd or maven_test_cmd).

        Returns:
            Command as list of strings suitable for subprocess.run().
            May include '{test_file}' placeholder for the caller to substitute.
        """

    @abstractmethod
    def test_run_command(self, project_path: Path, session_config: dict) -> list[str]:
        """Return the command to execute generated tests.

        Args:
            project_path: Project root directory.
            session_config: Dict from session metadata (may contain command overrides).

        Returns:
            Command as list of strings suitable for subprocess.run().
            May include '{test_file}' placeholder for the caller to substitute.
        """

