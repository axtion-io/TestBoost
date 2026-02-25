"""
Centralized path utilities for Java project structure discovery.

Provides reusable functions for Maven module detection, source/test directory
discovery, package extraction, and path conversions used across the codebase.
"""

import re
from pathlib import Path


def detect_maven_modules(project_dir: Path) -> list[Path]:
    """
    Detect Maven module directories in a multi-module project.

    Looks for subdirectories containing a pom.xml and src/main/java.

    Args:
        project_dir: Root project directory

    Returns:
        List of module directory paths (empty if not multi-module)
    """
    modules: list[Path] = []
    if not (project_dir / "pom.xml").exists():
        return modules

    for pom in project_dir.glob("**/pom.xml"):
        subdir = pom.parent
        if subdir == project_dir:
            continue
        if (subdir / "src" / "main" / "java").exists():
            modules.append(subdir)

    return modules


def get_source_directories(project_dir: Path) -> list[Path]:
    """
    Discover all Java source directories (src/main/java) in a project.

    Supports single-module and multi-module Maven structures with a
    fallback to a generic 'src' directory.

    Args:
        project_dir: Root project directory

    Returns:
        List of source directory paths
    """
    src_dirs: list[Path] = []

    # Find all src/main/java directories at any depth (handles both
    # single-module and nested multi-module Maven structures)
    for src_dir in project_dir.glob("**/src/main/java"):
        src_dirs.append(src_dir)

    # Fallback to generic src directory
    if not src_dirs:
        generic_src = project_dir / "src"
        if generic_src.exists():
            src_dirs.append(generic_src)

    return src_dirs


def get_test_directories(project_dir: Path) -> list[Path]:
    """
    Discover all Java test directories (src/test/java) in a project.

    Supports single-module and multi-module Maven structures with a
    fallback to a generic 'test' directory.

    Args:
        project_dir: Root project directory

    Returns:
        List of test directory paths
    """
    test_dirs: list[Path] = []

    # Find all src/test/java directories at any depth (handles both
    # single-module and nested multi-module Maven structures)
    for test_dir in project_dir.glob("**/src/test/java"):
        test_dirs.append(test_dir)

    # Fallback to generic test directory
    if not test_dirs:
        generic_test = project_dir / "test"
        if generic_test.exists():
            test_dirs.append(generic_test)

    return test_dirs


def extract_package(source_content: str) -> str | None:
    """
    Extract the Java package declaration from source content.

    Args:
        source_content: Java source file content

    Returns:
        Package name (e.g. 'com.example.service') or None if not found
    """
    match = re.search(r"package\s+([\w.]+);", source_content)
    return match.group(1) if match else None


def source_path_to_test_path(
    project_dir: Path, source_path: Path, suffix: str = "Test"
) -> Path:
    """
    Convert a source file path to its corresponding test file path.

    Transforms src/main/java/... to src/test/java/...<suffix>.java.

    Args:
        project_dir: Root project directory
        source_path: Path to the source file
        suffix: Test class suffix (default "Test", also "IntegrationTest",
                "SnapshotTest", "KillerTest", etc.)

    Returns:
        Relative path to the test file from project root
    """
    relative = source_path.relative_to(project_dir)
    parts = list(relative.parts)

    if "main" in parts:
        idx = parts.index("main")
        parts[idx] = "test"

    filename = parts[-1]
    if filename.endswith(".java"):
        parts[-1] = filename.replace(".java", f"{suffix}.java")

    return Path(*parts)


def test_path_to_source_path(test_path: str, project_path: str) -> str | None:
    """
    Find the source file corresponding to a test file.

    Transforms src/test/java/.../FooTest.java to src/main/java/.../Foo.java
    and verifies the file exists.

    Args:
        test_path: Relative path to test file
        project_path: Project root path

    Returns:
        Relative path to source file or None if not found
    """
    test_file = Path(test_path)
    test_class_name = test_file.stem

    # Remove "Test" suffix to get source class name
    if test_class_name.endswith("Test"):
        source_class_name = test_class_name[:-4]
    else:
        source_class_name = test_class_name

    # Convert test path to source path
    source_path = test_path.replace("/test/", "/main/").replace("\\test\\", "\\main\\")
    source_path = source_path.replace(test_class_name + ".java", source_class_name + ".java")

    full_source_path = Path(project_path) / source_path
    if full_source_path.exists():
        return str(full_source_path.relative_to(project_path))

    return None


def find_source_file_by_class(project_dir: Path, class_name: str) -> Path | None:
    """
    Find a source file by its fully-qualified class name.

    Searches in standard source directories and multi-module structures.

    Args:
        project_dir: Root project directory
        class_name: Fully-qualified class name (e.g. 'com.example.Foo')

    Returns:
        Path to the source file or None if not found
    """
    class_path = class_name.replace(".", "/") + ".java"

    # Search in all src/main/java directories (including nested modules)
    for src_dir in project_dir.glob("**/src/main/java"):
        candidate = src_dir / class_path
        if candidate.exists():
            return candidate

    # Fallback to generic src
    fallback = project_dir / "src" / class_path
    if fallback.exists():
        return fallback

    return None


def class_name_to_test_path(
    project_dir: Path, class_name: str, suffix: str = "Test"
) -> Path:
    """
    Generate a test file path from a fully-qualified class name.

    Resolves the source file first to determine the correct module, then
    derives the test path. Falls back to root src/test/java if the source
    file is not found.

    Args:
        project_dir: Root project directory
        class_name: Fully-qualified class name (e.g. 'com.example.Foo')
        suffix: Test class suffix (default "Test")

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
    return project_dir / "src" / "test" / "java" / package_path / f"{simple_name}{suffix}.java"


def find_test_files(project_dir: Path) -> list[Path]:
    """
    Find all Java test files across all test directories.

    Searches for *Test.java, *Tests.java, and Test*.java patterns.

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

    Includes files in web/controller/service/application/api packages,
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


def extract_module_from_path(project_dir: Path, file_path: str) -> str:
    """
    Extract the Maven module directory from a file path.

    Walks up the path components looking for the deepest directory that
    contains a pom.xml, returning its path relative to project_dir.

    Args:
        project_dir: Root project directory
        file_path: Relative path to a file within the project

    Returns:
        Relative module path (e.g. "parent/module-a") or "" for root module
    """
    parts = Path(file_path).parts
    # Walk from deepest to shallowest looking for a module pom.xml
    for i in range(len(parts), 0, -1):
        candidate = project_dir / Path(*parts[:i])
        if candidate == project_dir:
            continue
        if (candidate / "pom.xml").exists() and (candidate / "src").exists():
            return str(Path(*parts[:i]))
    return ""
