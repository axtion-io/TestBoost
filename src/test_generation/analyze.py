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

from src.java.pom import pom_child, pom_findall, pom_text


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

    frameworks: list[str] = []
    test_frameworks: list[str] = []
    dependencies: list[dict[str, Any]] = []

    results: dict[str, Any] = {
        "success": True,
        "project_path": str(project_dir.absolute()),
        "project_type": "unknown",
        "build_system": "unknown",
        "frameworks": frameworks,
        "test_frameworks": test_frameworks,
        "source_structure": {},
        "test_structure": {},
        "dependencies": dependencies,
        "java_version": None,
        "module_info": {},
    }

    # Detect technology via plugin registry
    from src.lib.plugins import get_registry
    detected_plugin = get_registry().detect(project_dir)
    if detected_plugin:
        results["project_type"] = detected_plugin.identifier

    # Detect build system (Java-specific detailed analysis when applicable)
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
    frameworks.extend(await _detect_frameworks(project_dir))
    test_frameworks.extend(await _detect_test_frameworks(project_dir))

    # Determine project type (only refine for Java plugins; non-Java keeps plugin identifier)
    if not detected_plugin or detected_plugin.identifier == "java-spring":
        results["project_type"] = _determine_project_type(frameworks)

    return json.dumps(results, indent=2)


async def _analyze_maven_project(
    pom_file: Path, results: dict[str, Any], include_dependencies: bool
) -> None:
    """Analyze Maven project structure and dependencies."""
    try:
        tree = ET.parse(pom_file)
        root = tree.getroot()
        # Get project info
        results["module_info"] = {
            "groupId": pom_text(root, "groupId") or "",
            "artifactId": pom_text(root, "artifactId") or "",
            "version": pom_text(root, "version") or "",
        }

        # Get Java version
        props = pom_child(root, "properties")
        java_version = (
            pom_text(props, "java.version")
            or pom_text(props, "maven.compiler.release")
            or pom_text(props, "maven.compiler.source")
        )
        if java_version:
            results["java_version"] = java_version

        # Parse dependencies
        if include_dependencies:
            dependencies = [
                {
                    "groupId": pom_text(dep, "groupId"),
                    "artifactId": pom_text(dep, "artifactId"),
                    "version": pom_text(dep, "version") or "managed",
                    "scope": pom_text(dep, "scope") or "compile",
                }
                for dep in pom_findall(root, "dependency")
                if pom_text(dep, "groupId") and pom_text(dep, "artifactId")
            ]
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


def _java_dirs(project_dir: Path, kind: str) -> list[Path]:
    """`src/<kind>/java` of the project and of its direct Maven submodules."""
    dirs = [project_dir / "src" / kind / "java"]
    dirs += [
        sub / "src" / kind / "java"
        for sub in sorted(project_dir.iterdir())
        if sub.is_dir() and (sub / "pom.xml").exists()
    ]
    return [d for d in dirs if d.exists()]


def _packages(files: list[Path]) -> set[str]:
    packages = set()
    for file in files:
        try:
            match = re.search(r"package\s+([\w.]+);", file.read_text(encoding="utf-8", errors="replace"))
        except OSError:  # unreadable file
            continue
        if match:
            packages.add(match.group(1))
    return packages


async def _analyze_source_structure(project_dir: Path, scan_depth: int) -> dict[str, Any]:
    """Analyze source code structure (single- or multi-module, generic src/ fallback)."""
    src_dirs = _java_dirs(project_dir, "main")
    if not src_dirs and (project_dir / "src").exists():
        src_dirs = [project_dir / "src"]
    java_files = [f for d in src_dirs for f in d.rglob("*.java")]
    return {
        "main_sources": [str(d) for d in src_dirs],
        "class_count": len(java_files),
        "packages": sorted(_packages(java_files[:200]))[:50],  # capped for performance
    }


async def _analyze_test_structure(project_dir: Path, scan_depth: int) -> dict[str, Any]:
    """Analyze test code structure."""
    test_dirs = _java_dirs(project_dir, "test")
    if not test_dirs and (project_dir / "test").exists():
        test_dirs = [project_dir / "test"]
    test_files = sorted({
        f for d in test_dirs
        for pattern in ("*Test.java", "*Tests.java", "Test*.java")
        for f in d.rglob(pattern)
    })
    return {
        "test_sources": [str(d) for d in test_dirs],
        "test_count": len(test_files),
        "test_packages": sorted(_packages(test_files[:100]))[:30],
    }


async def _detect_frameworks(project_dir: Path) -> list[str]:
    """Detect application frameworks from code and dependencies."""
    frameworks = set()

    java_files = [f for d in _java_dirs(project_dir, "main") for f in list(d.rglob("*.java"))[:30]]

    for java_file in java_files[:100]:
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

        except OSError:
            # Skip unreadable files
            continue

    return sorted(frameworks)


async def _detect_test_frameworks(project_dir: Path) -> list[str]:
    """Detect test frameworks from test code."""
    test_frameworks = set()

    test_files = [f for d in _java_dirs(project_dir, "test") for f in list(d.rglob("*.java"))[:30]]

    for test_file in test_files[:100]:
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

        except OSError:
            # Skip unreadable files
            continue

    return sorted(test_frameworks)


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
