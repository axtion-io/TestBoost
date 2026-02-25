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


def source_path_to_test_path(project_dir: Path, source_path: Path) -> Path:
    """
    Convert a source file path to its corresponding test file path.

    Transforms src/main/java/... to src/test/java/...Test.java.

    Args:
        project_dir: Root project directory
        source_path: Path to the source file

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
        parts[-1] = filename.replace(".java", "Test.java")

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
