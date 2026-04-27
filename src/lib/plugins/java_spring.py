# SPDX-License-Identifier: Apache-2.0
"""Java Spring plugin for TestBoost.

Wraps existing Java/Maven behavior. All analysis logic delegates to the
unchanged src.java.* modules. This plugin is a thin adapter — it does not
duplicate any parsing or discovery code.
"""

import re
import shlex
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from src.lib.plugins.base import TechnologyPlugin


class JavaSpringPlugin(TechnologyPlugin):
    """Plugin for Java projects using Spring Framework with Maven or Gradle.

    Detection: checks for pom.xml, build.gradle, or build.gradle.kts in the
    project root. Maven is assumed when pom.xml is present; Gradle otherwise.

    All source discovery and class analysis delegate to src.java.discovery and
    src.java.class_analyzer — behavior is identical to the pre-plugin code.
    """

    @property
    def identifier(self) -> str:
        return "java-spring"

    @property
    def description(self) -> str:
        return "Java projects using Spring Framework with Maven or Gradle"

    @property
    def detection_patterns(self) -> list[str]:
        return ["pom.xml", "build.gradle", "build.gradle.kts"]

    @property
    def prompt_template_dir(self) -> str:
        return "config/prompts/testing"

    # ------------------------------------------------------------------
    # Source discovery
    # ------------------------------------------------------------------

    def find_source_files(self, project_path: Path) -> list[str]:
        """Discover testable Java source files. Delegates to src.java.discovery."""
        from src.java.discovery import find_source_files
        return find_source_files(str(project_path))

    def classify_source_file(self, relative_path: str) -> str:
        """Classify a Java source file by semantic category."""
        from src.java.discovery import classify_source_file
        return classify_source_file(relative_path)

    # ------------------------------------------------------------------
    # Test file naming
    # ------------------------------------------------------------------

    def test_file_name(self, source_relative_path: str) -> str:
        """Derive the test file path for a Java source file.

        src/main/java/com/example/UserService.java
          → src/test/java/com/example/UserServiceTest.java
        """
        normalized = source_relative_path.replace("\\", "/")
        # Replace src/main/java/ (with or without leading slash) with src/test/java/
        if "src/main/java/" in normalized:
            test_path = normalized.replace("src/main/java/", "src/test/java/", 1)
        else:
            test_path = normalized

        if test_path.endswith(".java") and not test_path.endswith("Test.java"):
            test_path = test_path[:-5] + "Test.java"

        return test_path

    def test_file_pattern(self) -> list[str]:
        return ["**/*Test.java", "**/*Tests.java", "**/Test*.java"]

    # ------------------------------------------------------------------
    # Build commands (extracted from cli._detect_maven_build_config)
    # ------------------------------------------------------------------

    def validation_command(self, project_path: Path, session_config: dict) -> list[str]:
        """Return the mvn test-compile command, honoring session config overrides."""
        maven_compile_cmd = session_config.get("maven_compile_cmd")
        if maven_compile_cmd:
            return _parse_maven_cmd(maven_compile_cmd)

        config = _detect_maven_build_config(project_path)
        return _parse_maven_cmd(config["compile_cmd"])

    def test_run_command(self, project_path: Path, session_config: dict) -> list[str]:
        """Return the mvn test command, honoring session config overrides."""
        maven_test_cmd = session_config.get("maven_test_cmd")
        if maven_test_cmd:
            return _parse_maven_cmd(maven_test_cmd)

        config = _detect_maven_build_config(project_path)
        return _parse_maven_cmd(config["test_cmd"])

    # ------------------------------------------------------------------
    # Generation context
    # ------------------------------------------------------------------

    def build_generation_context(self, project_path: Path, source_file: str) -> dict:
        """Build the LLM context dict using the Java class analyzer."""
        from src.java.class_analyzer import build_class_index, extract_test_examples

        source_files = self.find_source_files(project_path)
        class_index = build_class_index(str(project_path), source_files)
        existing_tests = extract_test_examples(str(project_path))

        # Find this specific file's entry in the index
        normalized = source_file.replace("\\", "/")
        class_info = class_index.get(normalized, {})

        return {
            "source_code": class_info.get("source_code", ""),
            "class_name": class_info.get("class_name", Path(source_file).stem),
            "class_type": self.classify_source_file(normalized),
            "dependencies": class_info.get("dependencies", []),
            "existing_tests": [t.get("content", "") for t in existing_tests],
            "conventions": {},
            # Java-specific extras
            "class_index": class_index,
            "spring_annotations": class_info.get("annotations", []),
            "java_version": class_info.get("java_version", ""),
        }


# ---------------------------------------------------------------------------
# Private helpers (moved from src/lib/cli.py)
# ---------------------------------------------------------------------------

_ALLOWED_MAVEN_BINARIES = {"mvn", "mvn.cmd", "./mvnw", "mvnw"}


def _detect_maven_build_config(project_path: Path) -> dict:
    """Detect Maven build configuration from pom.xml and .mvn/maven.config.

    Returns a dict with:
      - compile_cmd: str  (e.g. "mvn test-compile -q --no-transfer-progress")
      - test_cmd:    str  (e.g. "mvn test -q --no-transfer-progress")
      - notes:       list[str]  (human-readable config notes)
    """
    project_dir = Path(project_path)
    notes: list[str] = []
    extra_flags = ""

    # Check for .mvn/maven.config (flags applied to every Maven invocation)
    maven_config_file = project_dir / ".mvn" / "maven.config"
    if maven_config_file.exists():
        try:
            config_content = maven_config_file.read_text(encoding="utf-8").strip()
            if config_content:
                extra_flags = " " + config_content.replace("\n", " ")
                notes.append(
                    f"`.mvn/maven.config` adds flags: "
                    f"`{config_content.replace(chr(10), ' ')}`"
                )
        except OSError:
            pass

    # Check for activeByDefault profiles in pom.xml
    pom_file = project_dir / "pom.xml"
    active_profiles: list[str] = []
    if pom_file.exists():
        try:
            tree = ET.parse(pom_file)
            root = tree.getroot()
            ns = {"maven": "http://maven.apache.org/POM/4.0.0"}

            profiles = root.findall(".//maven:profile", ns) or root.findall(".//profile")
            for profile in profiles:
                activation = (
                    profile.find("maven:activation", ns)
                    or profile.find("activation")
                )
                if activation is not None:
                    active_by_default = (
                        activation.find("maven:activeByDefault", ns)
                        or activation.find("activeByDefault")
                    )
                    if active_by_default is not None and active_by_default.text == "true":
                        profile_id = profile.find("maven:id", ns) or profile.find("id")
                        if profile_id is not None and profile_id.text:
                            pid = profile_id.text.strip()
                            if re.match(r"^[a-zA-Z0-9_.\-]+$", pid):
                                active_profiles.append(pid)
                            else:
                                notes.append(
                                    f"Skipped profile with invalid ID: {pid!r} "
                                    f"(only alphanumeric, _, ., - allowed)"
                                )
        except ET.ParseError:
            pass

    if active_profiles:
        profile_flags = " -P " + ",".join(active_profiles)
        extra_flags += profile_flags
        notes.append(
            f"Detected active-by-default profiles: `{', '.join(active_profiles)}` "
            f"— added `-P {','.join(active_profiles)}`"
        )

    if not notes:
        notes.append("No special profiles or Maven config detected — using default flags")

    return {
        "compile_cmd": f"mvn test-compile -q --no-transfer-progress{extra_flags}",
        "test_cmd": f"mvn test -q --no-transfer-progress{extra_flags}",
        "notes": notes,
    }


def _parse_maven_cmd(cmd_str: str) -> list[str]:
    """Parse a Maven command string into a list, resolving the mvn binary.

    Only binaries in _ALLOWED_MAVEN_BINARIES are accepted to prevent arbitrary
    command execution from user-editable session config fields.

    Example: "mvn test-compile -q -P corp" -> ["/usr/bin/mvn", "test-compile", "-q", "-P", "corp"]

    Raises:
        ValueError: If the command starts with a disallowed binary.
    """
    try:
        parts = shlex.split(cmd_str)
    except ValueError:
        parts = cmd_str.split()

    if not parts:
        return []

    binary = parts[0]
    if binary not in _ALLOWED_MAVEN_BINARIES:
        raise ValueError(
            f"Disallowed Maven binary in command: {binary!r}. "
            f"Allowed values: {sorted(_ALLOWED_MAVEN_BINARIES)}"
        )

    if binary in ("mvn", "mvn.cmd"):
        resolved = shutil.which("mvn") or shutil.which("mvn.cmd") or "mvn"
        return [resolved] + parts[1:]

    # Local wrapper (./mvnw, mvnw) — keep as-is
    return parts
