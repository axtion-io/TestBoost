# SPDX-License-Identifier: Apache-2.0
"""Java project discovery utilities.

Functions to find and classify Java source files in a Maven project.
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
