"""
Centralized path utilities for Java project structure discovery.

Uses Maven pom.xml parsing for efficient module discovery instead of
blind filesystem globbing. Builds an indexed project structure for
fast source and test file lookup.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

# Known test class suffixes, longest first for greedy matching
_TEST_SUFFIXES = ("IntegrationTest", "SnapshotTest", "KillerTest", "Tests", "Test")


# ---------------------------------------------------------------------------
# pom.xml parsing
# ---------------------------------------------------------------------------


def _parse_pom_modules(pom_path: Path) -> list[str]:
    """
    Parse ``<modules>`` from a pom.xml file.

    Returns:
        List of declared module directory names (e.g. ``["module-a", "module-b"]``),
        or an empty list if not a multi-module pom or if parsing fails.
    """
    try:
        tree = ET.parse(pom_path)
        root = tree.getroot()
        # Maven pom.xml often declares an xmlns namespace on the root element.
        ns_match = re.match(r"\{(.+?)}", root.tag)
        ns = ns_match.group(1) if ns_match else ""

        if ns:
            modules_elem = root.find(f"{{{ns}}}modules")
            tag = f"{{{ns}}}module"
        else:
            modules_elem = root.find("modules")
            tag = "module"

        if modules_elem is None:
            return []

        return [m.text.strip() for m in modules_elem.findall(tag) if m.text]
    except (ET.ParseError, OSError):
        return []


# ---------------------------------------------------------------------------
# Maven module detection
# ---------------------------------------------------------------------------


def _collect_modules_recursive(
    project_dir: Path, current_dir: Path, modules: list[Path]
) -> None:
    """Walk *declared* ``<modules>`` in pom.xml files recursively."""
    pom = current_dir / "pom.xml"
    if not pom.exists():
        return

    for module_name in _parse_pom_modules(pom):
        module_dir = (current_dir / module_name).resolve()
        # Stay within the project boundary
        try:
            module_dir.relative_to(project_dir.resolve())
        except ValueError:
            continue
        if not module_dir.is_dir():
            continue
        if module_dir != project_dir.resolve():
            modules.append(module_dir)
        # Recurse into sub-modules (e.g. parent → child → grandchild)
        _collect_modules_recursive(project_dir, module_dir, modules)


def detect_maven_modules(project_dir: Path) -> list[Path]:
    """
    Detect Maven module directories by parsing pom.xml ``<modules>`` declarations.

    Recursively follows parent → child module references, which mirrors
    how Maven itself resolves the reactor build order.  This replaces the
    previous ``**/pom.xml`` glob approach that was expensive on large
    projects and could match false positives inside ``target/``.

    Args:
        project_dir: Root project directory

    Returns:
        List of module directory paths (empty if not multi-module)
    """
    if not (project_dir / "pom.xml").exists():
        return []

    modules: list[Path] = []
    _collect_modules_recursive(project_dir, project_dir, modules)
    return modules


# ---------------------------------------------------------------------------
# Source / test directory discovery
# ---------------------------------------------------------------------------


def _module_roots(project_dir: Path) -> list[Path]:
    """Return the project root + every declared Maven module root."""
    roots = [project_dir]
    roots.extend(detect_maven_modules(project_dir))
    return roots


def get_source_directories(project_dir: Path) -> list[Path]:
    """
    Discover all Java source directories (``src/main/java``) in a project.

    Uses Maven module detection to check only declared modules,
    avoiding filesystem-wide globbing.

    Args:
        project_dir: Root project directory

    Returns:
        List of source directory paths
    """
    src_dirs: list[Path] = []

    for root in _module_roots(project_dir):
        candidate = root / "src" / "main" / "java"
        if candidate.is_dir():
            src_dirs.append(candidate)

    # Fallback to generic src directory
    if not src_dirs:
        generic_src = project_dir / "src"
        if generic_src.is_dir():
            src_dirs.append(generic_src)

    return src_dirs


def get_test_directories(project_dir: Path) -> list[Path]:
    """
    Discover all Java test directories (``src/test/java``) in a project.

    Uses Maven module detection to check only declared modules,
    avoiding filesystem-wide globbing.

    Args:
        project_dir: Root project directory

    Returns:
        List of test directory paths
    """
    test_dirs: list[Path] = []

    for root in _module_roots(project_dir):
        candidate = root / "src" / "test" / "java"
        if candidate.is_dir():
            test_dirs.append(candidate)

    # Fallback to generic test directory
    if not test_dirs:
        generic_test = project_dir / "test"
        if generic_test.is_dir():
            test_dirs.append(generic_test)

    return test_dirs


# ---------------------------------------------------------------------------
# Package extraction
# ---------------------------------------------------------------------------


def extract_package(source_content: str) -> str | None:
    """
    Extract the Java package declaration from source content.

    Args:
        source_content: Java source file content

    Returns:
        Package name (e.g. ``com.example.service``) or ``None`` if not found
    """
    match = re.search(r"package\s+([\w.]+);", source_content)
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# Helpers for test ↔ source suffix handling
# ---------------------------------------------------------------------------


def _strip_test_suffix(class_name: str) -> str:
    """Strip the first matching test suffix from *class_name*."""
    for suffix in _TEST_SUFFIXES:
        if class_name.endswith(suffix) and len(class_name) > len(suffix):
            return class_name[: -len(suffix)]
    return class_name


def _find_src_main_java_triplet(parts: list[str]) -> int | None:
    """Return the index of ``src`` in the first ``src/main/java`` triplet, or ``None``."""
    for i in range(len(parts) - 2):
        if parts[i] == "src" and parts[i + 1] == "main" and parts[i + 2] == "java":
            return i
    return None


def _find_src_test_java_triplet(parts: list[str]) -> int | None:
    """Return the index of ``src`` in the first ``src/test/java`` triplet, or ``None``."""
    for i in range(len(parts) - 2):
        if parts[i] == "src" and parts[i + 1] == "test" and parts[i + 2] == "java":
            return i
    return None


# ---------------------------------------------------------------------------
# Path conversions: source ↔ test
# ---------------------------------------------------------------------------


def source_path_to_test_path(
    project_dir: Path, source_path: Path, suffix: str = "Test"
) -> Path:
    """
    Convert a source file path to its corresponding test file path.

    Precisely targets the ``src/main/java`` triplet to swap ``main`` → ``test``,
    so a ``main`` directory appearing elsewhere in the path (e.g. in a
    package name) is never touched.

    Args:
        project_dir: Root project directory
        source_path: Path to the source file
        suffix: Test class suffix (default ``"Test"``; also
                ``"IntegrationTest"``, ``"SnapshotTest"``, ``"KillerTest"``, etc.)

    Returns:
        Relative path to the test file from project root
    """
    relative = source_path.relative_to(project_dir)
    parts = list(relative.parts)

    idx = _find_src_main_java_triplet(parts)
    if idx is not None:
        parts[idx + 1] = "test"

    filename = parts[-1]
    if filename.endswith(".java"):
        parts[-1] = filename.replace(".java", f"{suffix}.java")

    return Path(*parts)


def test_path_to_source_path(test_path: str, project_path: str) -> str | None:
    """
    Find the source file corresponding to a test file.

    Handles all known test suffixes (``Test``, ``IntegrationTest``,
    ``SnapshotTest``, ``KillerTest``, ``Tests``).  When the direct
    ``src/test → src/main`` mapping does not resolve, falls back to
    searching all source directories in the project (cross-module lookup).

    Args:
        test_path: Relative path to test file
        project_path: Project root path

    Returns:
        Relative path to source file or ``None`` if not found
    """
    project_dir = Path(project_path)
    test_file = Path(test_path)
    test_class_name = test_file.stem

    # Determine the source class name by stripping the test suffix
    source_class_name = _strip_test_suffix(test_class_name)
    if source_class_name == test_class_name:
        # No known test suffix — cannot derive source name
        return None

    source_filename = source_class_name + ".java"

    # Strategy 1: precise triplet swap src/test/java → src/main/java
    parts = list(test_file.parts)
    triplet_idx = _find_src_test_java_triplet(parts)

    if triplet_idx is not None:
        parts[triplet_idx + 1] = "main"
        parts[-1] = source_filename
        direct = Path(*parts)
        full_path = project_dir / direct
        if full_path.exists():
            return str(direct)

        # Strategy 2: extract the package-relative path and search all
        # source directories (handles cross-module cases)
        java_idx = triplet_idx + 2  # index of "java" in parts
        package_parts = list(parts[java_idx + 1 : -1])
        package_relative = (
            Path(*package_parts, source_filename)
            if package_parts
            else Path(source_filename)
        )

        for src_dir in get_source_directories(project_dir):
            candidate = src_dir / package_relative
            if candidate.exists():
                return str(candidate.relative_to(project_dir))

    return None


# ---------------------------------------------------------------------------
# Source file lookup by class name
# ---------------------------------------------------------------------------


def find_source_file_by_class(project_dir: Path, class_name: str) -> Path | None:
    """
    Find a source file by its fully-qualified class name.

    Computes the expected file path directly from the class name and
    checks each known source directory — no ``rglob`` / ``**`` needed.

    Args:
        project_dir: Root project directory
        class_name: Fully-qualified class name (e.g. ``com.example.Foo``)

    Returns:
        Path to the source file or ``None`` if not found
    """
    class_path = class_name.replace(".", "/") + ".java"

    for src_dir in get_source_directories(project_dir):
        candidate = src_dir / class_path
        if candidate.exists():
            return candidate

    return None


def class_name_to_test_path(
    project_dir: Path, class_name: str, suffix: str = "Test"
) -> Path:
    """
    Generate a test file path from a fully-qualified class name.

    Resolves the source file first to determine the correct module, then
    derives the test path.  Falls back to root ``src/test/java`` if the
    source file is not found.

    Args:
        project_dir: Root project directory
        class_name: Fully-qualified class name (e.g. ``com.example.Foo``)
        suffix: Test class suffix (default ``"Test"``)

    Returns:
        Absolute path to the test file
    """
    source_file = find_source_file_by_class(project_dir, class_name)
    if source_file is not None:
        return project_dir / source_path_to_test_path(
            project_dir, source_file, suffix=suffix
        )

    # Fallback: place in root src/test/java
    class_path = class_name.replace(".", "/")
    simple_name = class_name.rsplit(".", 1)[-1]
    package_path = class_path[: class_path.rfind("/")] if "/" in class_path else ""
    return (
        project_dir / "src" / "test" / "java" / package_path / f"{simple_name}{suffix}.java"
    )


# ---------------------------------------------------------------------------
# Test file discovery
# ---------------------------------------------------------------------------


def find_test_files(project_dir: Path) -> list[Path]:
    """
    Find all Java test files across all test directories.

    Searches for ``*Test.java``, ``*Tests.java``, and ``Test*.java`` patterns.

    Args:
        project_dir: Root project directory

    Returns:
        Deduplicated list of test file paths
    """
    test_files: list[Path] = []
    for test_dir in get_test_directories(project_dir):
        test_files.extend(test_dir.rglob("*Test.java"))
        test_files.extend(test_dir.rglob("*Tests.java"))
        test_files.extend(test_dir.rglob("Test*.java"))
    return list(set(test_files))


# ---------------------------------------------------------------------------
# Testable source file discovery
# ---------------------------------------------------------------------------

# Patterns for finding testable source files
_INCLUDE_PATTERNS = [
    "**/web/**/*.java",
    "**/controller/**/*.java",
    "**/service/**/*.java",
    "**/application/**/*.java",
    "**/api/**/*.java",
]

_EXCLUDE_DIRS = {"test", "model", "entity", "dto", "config", "configuration", "mapper"}

_EXCLUDE_SUFFIXES = (
    "Application.java",
    "Config.java",
    "Configuration.java",
    "Request.java",
    "Response.java",
    "DTO.java",
    "Exception.java",
)


def find_testable_source_files(project_dir: Path) -> list[str]:
    """
    Find Java source files that are candidates for test generation.

    Includes files in ``web/controller/service/application/api`` packages,
    excludes test files, DTOs, entities, configuration, and other
    non-testable classes.

    Args:
        project_dir: Root project directory

    Returns:
        List of relative paths to testable source files
    """
    source_files: list[str] = []

    for src_dir in get_source_directories(project_dir):
        for pattern in _INCLUDE_PATTERNS:
            for source_file in src_dir.glob(pattern):
                relative_path = str(source_file.relative_to(project_dir))

                # Check directory-based exclusions
                parts = set(source_file.relative_to(src_dir).parts[:-1])
                if parts & _EXCLUDE_DIRS:
                    continue

                # Check suffix-based exclusions
                if source_file.name.endswith(_EXCLUDE_SUFFIXES):
                    continue

                if relative_path not in source_files:
                    source_files.append(relative_path)

    return source_files


# ---------------------------------------------------------------------------
# Module extraction
# ---------------------------------------------------------------------------


def extract_module_from_path(project_dir: Path, file_path: str) -> str:
    """
    Extract the Maven module directory from a file path.

    Uses the declared module index to find which module contains the file,
    instead of walking up the filesystem checking for ``pom.xml`` at every
    level.

    Args:
        project_dir: Root project directory
        file_path: Relative path to a file within the project

    Returns:
        Relative module path (e.g. ``"parent/module-a"``) or ``""`` for root module
    """
    file_abs = (project_dir / file_path).resolve()
    modules = detect_maven_modules(project_dir)

    # Sort by depth descending so the deepest (most specific) module wins
    modules_sorted = sorted(modules, key=lambda m: len(m.resolve().parts), reverse=True)

    for module_dir in modules_sorted:
        module_resolved = module_dir.resolve()
        try:
            file_abs.relative_to(module_resolved)
            return str(module_dir.relative_to(project_dir))
        except ValueError:
            continue

    return ""
