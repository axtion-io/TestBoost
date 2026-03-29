# SPDX-License-Identifier: Apache-2.0
"""Java project discovery utilities.

Functions to find and classify Java source files in a Maven project.
Used by testboost via testboost_bridge.
"""

from pathlib import Path

from src.lib.logging import get_logger

logger = get_logger(__name__)


def find_source_files(project_path: str) -> list[str]:
    """Find Java source files that are candidates for test generation.

    Uses an inclusive approach: collect ALL Java files under src/main/java,
    then exclude only files that are clearly non-testable (package-info,
    module-info, and test sources).

    Args:
        project_path: Path to the Java project root

    Returns:
        List of relative paths to source files
    """
    project_dir = Path(project_path)
    source_files = []

    exclude_filenames = {"package-info.java", "module-info.java"}

    for main_java_dir in project_dir.glob("**/src/main/java"):
        for source_file in main_java_dir.glob("**/*.java"):
            if source_file.name in exclude_filenames:
                continue
            relative_path = str(source_file.relative_to(project_dir))
            if "/test/" in relative_path.replace("\\", "/"):
                continue
            if relative_path not in source_files:
                source_files.append(relative_path)

    source_files.sort()
    logger.info("source_files_found", count=len(source_files), project_path=project_path)
    return source_files


def classify_source_file(relative_path: str) -> str:
    """Classify a Java source file by category based on its path and name."""
    path_lower = relative_path.replace("\\", "/").lower()
    name = Path(relative_path).stem

    path_categories = [
        ("/controller/", "controller"),
        ("/web/", "controller"),
        ("/rest/", "controller"),
        ("/resource/", "controller"),
        ("/api/", "api"),
        ("/service/", "service"),
        ("/repository/", "repository"),
        ("/dao/", "repository"),
        ("/entity/", "entity"),
        ("/model/", "model"),
        ("/dto/", "dto"),
        ("/mapper/", "mapper"),
        ("/converter/", "converter"),
        ("/config/", "config"),
        ("/configuration/", "config"),
        ("/security/", "security"),
        ("/exception/", "exception"),
        ("/util/", "util"),
        ("/utils/", "util"),
        ("/helper/", "util"),
        ("/builder/", "builder"),
        ("/factory/", "factory"),
        ("/validator/", "validator"),
        ("/handler/", "handler"),
        ("/listener/", "listener"),
        ("/interceptor/", "interceptor"),
        ("/filter/", "filter"),
        ("/aop/", "aop"),
        ("/aspect/", "aop"),
        ("/document/", "document"),
        ("/schema/", "schema"),
        ("/imports/", "import"),
        ("/math/", "math"),
        ("/concurrent/", "concurrent"),
        ("/description/", "description"),
        ("/patch/", "patch"),
        ("/pdf/", "pdf"),
        ("/messages/", "messages"),
        ("/core/", "core"),
    ]

    for pattern, category in path_categories:
        if pattern in path_lower:
            return category

    name_categories = [
        ("Controller", "controller"),
        ("Resource", "controller"),
        ("Service", "service"),
        ("ServiceImpl", "service"),
        ("Repository", "repository"),
        ("Dao", "repository"),
        ("Entity", "entity"),
        ("Dto", "dto"),
        ("DTO", "dto"),
        ("Mapper", "mapper"),
        ("Converter", "converter"),
        ("Config", "config"),
        ("Configuration", "config"),
        ("Exception", "exception"),
        ("Utils", "util"),
        ("Util", "util"),
        ("Helper", "util"),
        ("Builder", "builder"),
        ("Factory", "factory"),
        ("Validator", "validator"),
        ("Handler", "handler"),
        ("Listener", "listener"),
        ("Interceptor", "interceptor"),
        ("Filter", "filter"),
        ("Test", "test"),
    ]

    for suffix, category in name_categories:
        if name.endswith(suffix):
            return category

    return "other"


def find_existing_test(project_path: str, source_relative_path: str) -> str | None:
    """Find the existing test file for a given source file, if any.

    Searches for common test naming conventions:
      - FooTest.java
      - FooTests.java
      - TestFoo.java

    Returns the relative path to the test file, or None.
    """
    project_dir = Path(project_path)
    source_path = Path(source_relative_path.replace("\\", "/"))
    class_name = source_path.stem

    parts = source_path.parts
    try:
        main_idx = list(parts).index("main")
        package_parts = parts[main_idx + 2 : -1]
    except (ValueError, IndexError):
        package_parts = ()

    test_names = [
        f"{class_name}Test.java",
        f"{class_name}Tests.java",
        f"Test{class_name}.java",
    ]

    for test_dir in project_dir.glob("**/src/test/java"):
        if package_parts:
            pkg_dir = test_dir.joinpath(*package_parts)
            for test_name in test_names:
                candidate = pkg_dir / test_name
                if candidate.exists():
                    return str(candidate.relative_to(project_dir))

        for test_name in test_names:
            matches = list(test_dir.glob(f"**/{test_name}"))
            if matches:
                return str(matches[0].relative_to(project_dir))

    return None
