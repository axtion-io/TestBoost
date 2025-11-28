"""
Analyze project context tool for test generation.

Analyzes Java project structure, frameworks, dependencies, and testing patterns
to provide context for intelligent test generation.
"""

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


async def analyze_project_context(
    project_path: str, include_dependencies: bool = True, scan_depth: int = 10
) -> str:
    """
    Analyze Java project context for test generation.

    Args:
        project_path: Path to the Java project root directory
        include_dependencies: Include dependency analysis
        scan_depth: Maximum directory depth to scan

    Returns:
        JSON string with project context analysis
    """
    project_dir = Path(project_path)

    if not project_dir.exists():
        return json.dumps(
            {"success": False, "error": f"Project path does not exist: {project_path}"}
        )

    results = {
        "success": True,
        "project_path": str(project_dir.absolute()),
        "project_type": "unknown",
        "build_system": "unknown",
        "frameworks": [],
        "test_frameworks": [],
        "source_structure": {},
        "test_structure": {},
        "dependencies": [],
        "java_version": None,
        "module_info": {},
    }

    # Detect build system
    pom_file = project_dir / "pom.xml"
    gradle_file = project_dir / "build.gradle"
    gradle_kts = project_dir / "build.gradle.kts"

    if pom_file.exists():
        results["build_system"] = "maven"
        await _analyze_maven_project(pom_file, results, include_dependencies)
    elif gradle_file.exists() or gradle_kts.exists():
        results["build_system"] = "gradle"
        await _analyze_gradle_project(project_dir, results)

    # Analyze source structure
    results["source_structure"] = await _analyze_source_structure(project_dir, scan_depth)

    # Analyze test structure
    results["test_structure"] = await _analyze_test_structure(project_dir, scan_depth)

    # Detect frameworks from imports
    results["frameworks"] = await _detect_frameworks(project_dir)
    results["test_frameworks"] = await _detect_test_frameworks(project_dir)

    # Determine project type
    results["project_type"] = _determine_project_type(results["frameworks"])

    return json.dumps(results, indent=2)


async def _analyze_maven_project(
    pom_file: Path, results: dict[str, Any], include_dependencies: bool
) -> None:
    """Analyze Maven project structure and dependencies."""
    try:
        tree = ET.parse(pom_file)
        root = tree.getroot()
        ns = {"maven": "http://maven.apache.org/POM/4.0.0"}

        # Get project info
        group_id = root.find("maven:groupId", ns) or root.find("groupId")
        artifact_id = root.find("maven:artifactId", ns) or root.find("artifactId")
        version = root.find("maven:version", ns) or root.find("version")

        results["module_info"] = {
            "groupId": group_id.text if group_id is not None else "",
            "artifactId": artifact_id.text if artifact_id is not None else "",
            "version": version.text if version is not None else "",
        }

        # Get Java version
        props = root.find("maven:properties", ns) or root.find("properties")
        if props is not None:
            java_version = (
                props.find("maven:java.version", ns)
                or props.find("java.version")
                or props.find("maven:maven.compiler.source", ns)
                or props.find("maven.compiler.source")
            )
            if java_version is not None:
                results["java_version"] = java_version.text

        # Parse dependencies
        if include_dependencies:
            dependencies = []
            for dep in root.findall(".//maven:dependency", ns):
                dep_group = dep.find("maven:groupId", ns)
                dep_artifact = dep.find("maven:artifactId", ns)
                dep_version = dep.find("maven:version", ns)
                dep_scope = dep.find("maven:scope", ns)

                if dep_group is not None and dep_artifact is not None:
                    dependencies.append(
                        {
                            "groupId": dep_group.text,
                            "artifactId": dep_artifact.text,
                            "version": dep_version.text if dep_version is not None else "managed",
                            "scope": dep_scope.text if dep_scope is not None else "compile",
                        }
                    )

            # Also check without namespace
            if not dependencies:
                for dep in root.findall(".//dependency"):
                    dep_group = dep.find("groupId")
                    dep_artifact = dep.find("artifactId")
                    dep_version = dep.find("version")
                    dep_scope = dep.find("scope")

                    if dep_group is not None and dep_artifact is not None:
                        dependencies.append(
                            {
                                "groupId": dep_group.text,
                                "artifactId": dep_artifact.text,
                                "version": (
                                    dep_version.text if dep_version is not None else "managed"
                                ),
                                "scope": dep_scope.text if dep_scope is not None else "compile",
                            }
                        )

            results["dependencies"] = dependencies

    except ET.ParseError as e:
        results["pom_parse_error"] = str(e)


async def _analyze_gradle_project(project_dir: Path, results: dict[str, Any]) -> None:
    """Analyze Gradle project structure."""
    gradle_file = project_dir / "build.gradle"
    if not gradle_file.exists():
        gradle_file = project_dir / "build.gradle.kts"

    if gradle_file.exists():
        content = gradle_file.read_text(encoding="utf-8", errors="replace")

        # Extract Java version
        java_version_match = re.search(r"sourceCompatibility\s*=\s*['\"]?(\d+)['\"]?", content)
        if java_version_match:
            results["java_version"] = java_version_match.group(1)


async def _analyze_source_structure(project_dir: Path, scan_depth: int) -> dict[str, Any]:
    """Analyze source code structure."""
    structure = {"main_sources": [], "packages": [], "class_count": 0, "interface_count": 0}

    # Find main source directories
    src_dirs = [project_dir / "src" / "main" / "java", project_dir / "src"]

    for src_dir in src_dirs:
        if src_dir.exists():
            java_files = list(src_dir.rglob("*.java"))
            structure["class_count"] = len(java_files)

            # Extract packages
            packages = set()
            for java_file in java_files[:100]:  # Limit for performance
                try:
                    content = java_file.read_text(encoding="utf-8", errors="replace")
                    package_match = re.search(r"package\s+([\w.]+);", content)
                    if package_match:
                        packages.add(package_match.group(1))
                except Exception:
                    pass

            structure["packages"] = sorted(list(packages))[:50]
            structure["main_sources"] = [str(src_dir)]
            break

    return structure


async def _analyze_test_structure(project_dir: Path, scan_depth: int) -> dict[str, Any]:
    """Analyze test code structure."""
    structure = {"test_sources": [], "test_count": 0, "test_packages": []}

    test_dirs = [project_dir / "src" / "test" / "java", project_dir / "test"]

    for test_dir in test_dirs:
        if test_dir.exists():
            test_files = list(test_dir.rglob("*Test.java"))
            test_files.extend(test_dir.rglob("*Tests.java"))
            test_files.extend(test_dir.rglob("Test*.java"))

            structure["test_count"] = len(set(test_files))

            # Extract test packages
            packages = set()
            for test_file in test_files[:50]:
                try:
                    content = test_file.read_text(encoding="utf-8", errors="replace")
                    package_match = re.search(r"package\s+([\w.]+);", content)
                    if package_match:
                        packages.add(package_match.group(1))
                except Exception:
                    pass

            structure["test_packages"] = sorted(list(packages))[:30]
            structure["test_sources"] = [str(test_dir)]
            break

    return structure


async def _detect_frameworks(project_dir: Path) -> list[str]:
    """Detect application frameworks from code and dependencies."""
    frameworks = set()

    # Check imports in source files
    src_dir = project_dir / "src" / "main" / "java"
    if src_dir.exists():
        for java_file in list(src_dir.rglob("*.java"))[:50]:
            try:
                content = java_file.read_text(encoding="utf-8", errors="replace")

                if "org.springframework" in content:
                    frameworks.add("spring")
                    if "@SpringBootApplication" in content:
                        frameworks.add("spring-boot")
                if "javax.persistence" in content or "jakarta.persistence" in content:
                    frameworks.add("jpa")
                if "io.quarkus" in content:
                    frameworks.add("quarkus")
                if "io.micronaut" in content:
                    frameworks.add("micronaut")
                if "javax.ws.rs" in content or "jakarta.ws.rs" in content:
                    frameworks.add("jax-rs")
                if "org.hibernate" in content:
                    frameworks.add("hibernate")

            except Exception:
                pass

    return sorted(list(frameworks))


async def _detect_test_frameworks(project_dir: Path) -> list[str]:
    """Detect test frameworks from test code."""
    test_frameworks = set()

    test_dir = project_dir / "src" / "test" / "java"
    if test_dir.exists():
        for test_file in list(test_dir.rglob("*.java"))[:50]:
            try:
                content = test_file.read_text(encoding="utf-8", errors="replace")

                if "org.junit.jupiter" in content:
                    test_frameworks.add("junit5")
                elif "org.junit" in content:
                    test_frameworks.add("junit4")
                if "org.mockito" in content:
                    test_frameworks.add("mockito")
                if "org.assertj" in content:
                    test_frameworks.add("assertj")
                if "org.hamcrest" in content:
                    test_frameworks.add("hamcrest")
                if "org.testcontainers" in content:
                    test_frameworks.add("testcontainers")
                if "@SpringBootTest" in content:
                    test_frameworks.add("spring-boot-test")
                if "@WebMvcTest" in content or "@DataJpaTest" in content:
                    test_frameworks.add("spring-test-slices")
                if "io.rest-assured" in content or "RestAssured" in content:
                    test_frameworks.add("rest-assured")
                if "org.wiremock" in content or "WireMock" in content:
                    test_frameworks.add("wiremock")

            except Exception:
                pass

    return sorted(list(test_frameworks))


def _determine_project_type(frameworks: list[str]) -> str:
    """Determine project type from detected frameworks."""
    if "spring-boot" in frameworks:
        return "spring-boot"
    elif "spring" in frameworks:
        return "spring"
    elif "quarkus" in frameworks:
        return "quarkus"
    elif "micronaut" in frameworks:
        return "micronaut"
    elif "jax-rs" in frameworks:
        return "jaxrs"
    else:
        return "java"
