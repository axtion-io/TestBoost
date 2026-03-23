"""
Generate adaptive unit tests tool.

Generates unit tests adapted to project conventions and class type,
using LLM to create intelligent test cases.
"""

import json
import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.lib.llm import get_llm
from src.lib.logging import get_logger
from src.lib.prompt_utils import load_prompt_template, render_template

logger = get_logger(__name__)


async def generate_adaptive_tests(
    project_path: str,
    source_file: str,
    class_type: str | None = None,
    conventions: dict[str, Any] | None = None,
    coverage_target: float = 80,
    test_requirements: list[dict[str, Any]] | None = None,
) -> str:
    """
    Generate unit tests adapted to project conventions.

    Args:
        project_path: Path to the Java project root directory
        source_file: Path to the source file to generate tests for
        class_type: Classification of the class (controller, service, etc.)
        conventions: Test conventions to follow
        coverage_target: Target code coverage percentage
        test_requirements: Optional list of specific test requirements from impact analysis

    Returns:
        JSON string with generated test code and metadata
    """
    project_dir = Path(project_path)
    source_path = Path(source_file)

    if not source_path.exists():
        # Try as relative path
        source_path = project_dir / source_file
        if not source_path.exists():
            return json.dumps({"success": False, "error": f"Source file not found: {source_file}"})

    # Read source code
    try:
        source_code = source_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return json.dumps({"success": False, "error": f"Failed to read source file: {e}"})

    # Analyze source file
    class_info = _analyze_class(source_code)

    # Auto-detect class type if not provided
    if not class_type:
        class_type = _detect_class_type(source_code, class_info)

    # Generate test file path
    test_file_path = _get_test_file_path(project_dir, source_path)

    # Build test generation context
    context = {
        "class_name": class_info["class_name"],
        "package": class_info["package"],
        "class_type": class_type,
        "methods": class_info["methods"],
        "dependencies": class_info["dependencies"],
        "annotations": class_info["annotations"],
        "conventions": conventions or {},
        "coverage_target": coverage_target,
        "test_requirements": test_requirements or [],
        "imports": class_info.get("imports", []),
        "is_record": class_info.get("is_record", False),
        "source_code": source_code,
        "project_path": project_path,
    }

    # Generate test code using LLM
    logger.info("generating_tests_with_llm", class_name=class_info["class_name"])
    test_code = await _generate_test_code_with_llm(context, source_code)

    results = {
        "success": True,
        "source_file": str(source_path),
        "test_file": str(test_file_path),
        "class_type": class_type,
        "test_code": test_code,
        "methods_covered": len(class_info["methods"]),
        "estimated_coverage": min(coverage_target, 85),
        "test_count": test_code.count("@Test"),
        "context": context,
    }

    return json.dumps(results, indent=2)


@lru_cache(maxsize=16)
def _extract_project_context(project_path: str) -> str:
    """Extract key project info from pom.xml for LLM context (cached per project).

    Args:
        project_path: Root directory of the Java project

    Returns:
        Formatted string with project context, or empty string if unavailable
    """

    pom_file = Path(project_path) / "pom.xml"
    if not pom_file.exists():
        return ""

    try:
        tree = ET.parse(pom_file)
        root = tree.getroot()
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}

        parts = ["## Project Technical Context\n"]

        # Java version
        props = root.find("m:properties", ns) or root.find("properties")
        if props is not None:
            for tag in ["m:java.version", "java.version", "m:maven.compiler.source", "maven.compiler.source"]:
                el = props.find(tag, ns) if tag.startswith("m:") else props.find(tag)
                if el is not None and el.text:
                    parts.append(f"- **Java version**: {el.text}")
                    break

        # Spring Boot version from parent
        parent = root.find("m:parent", ns)
        if parent is None:
            parent = root.find("parent")
        if parent is not None:
            parent_artifact = parent.find("m:artifactId", ns)
            if parent_artifact is None:
                parent_artifact = parent.find("artifactId")
            parent_version = parent.find("m:version", ns)
            if parent_version is None:
                parent_version = parent.find("version")
            if parent_artifact is not None and "spring-boot" in (parent_artifact.text or ""):
                parts.append(f"- **Spring Boot version**: {parent_version.text if parent_version is not None else 'unknown'}")

        # Key dependencies
        key_deps = []
        for dep_path in [".//m:dependency", ".//dependency"]:
            use_ns = ns if dep_path.startswith(".//m:") else {}
            for dep in root.findall(dep_path, use_ns) if use_ns else root.findall(dep_path):
                artifact = dep.find("m:artifactId", ns) if use_ns else dep.find("artifactId")
                version = dep.find("m:version", ns) if use_ns else dep.find("version")
                if artifact is not None and any(k in artifact.text for k in [
                    "lombok", "junit", "mockito", "spring-boot-starter-test",
                    "spring-boot-starter-data-jpa", "spring-boot-starter-web", "h2",
                ]):
                    ver = version.text if version is not None else "managed"
                    key_deps.append(f"  - {artifact.text} ({ver})")
            if key_deps:
                break

        if key_deps:
            parts.append("- **Key dependencies**:")
            parts.extend(key_deps)

        parts.append("")
        return "\n".join(parts)

    except Exception as e:
        logger.debug("project_context_extraction_error", error=str(e))
        return ""


@lru_cache(maxsize=16)
def _detect_test_dependencies(project_path: str) -> dict[str, Any]:
    """Detect available test framework and libraries from pom.xml.

    Returns dict with framework ('junit4' or 'junit5'), available libraries,
    and flags for mockito, assertj, hamcrest.
    """
    result: dict[str, Any] = {
        "framework": "junit5",
        "has_mockito": False,
        "has_assertj": False,
        "has_hamcrest": False,
        "has_spring_test": False,
        "available_deps": [],
    }

    pom_file = Path(project_path) / "pom.xml"
    if not pom_file.exists():
        return result

    try:
        tree = ET.parse(pom_file)
        root = tree.getroot()
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}

        has_junit4 = False
        has_junit5 = False

        for dep_path, use_ns in [(".//m:dependency", ns), (".//dependency", {})]:
            deps = root.findall(dep_path, use_ns) if use_ns else root.findall(dep_path)
            for dep in deps:
                artifact = dep.find("m:artifactId", ns) if use_ns else dep.find("artifactId")
                if artifact is None or not artifact.text:
                    continue
                aid = artifact.text

                if aid in ("junit", "junit-dep"):
                    has_junit4 = True
                    result["available_deps"].append(aid)
                elif aid in ("junit-jupiter", "junit-jupiter-api", "junit-jupiter-engine"):
                    has_junit5 = True
                    result["available_deps"].append(aid)
                elif aid == "spring-boot-starter-test":
                    # Spring Boot 2.2+ bundles JUnit 5; explicit junit dep overrides
                    has_junit5 = True
                    result["has_spring_test"] = True
                    result["available_deps"].append(aid)
                elif "mockito" in aid:
                    result["has_mockito"] = True
                    result["available_deps"].append(aid)
                elif aid == "assertj-core":
                    result["has_assertj"] = True
                    result["available_deps"].append(aid)
                elif "hamcrest" in aid:
                    result["has_hamcrest"] = True
                    result["available_deps"].append(aid)

            if result["available_deps"]:
                break

        # JUnit 5 wins when both are present
        if has_junit5:
            result["framework"] = "junit5"
        elif has_junit4:
            result["framework"] = "junit4"

        return result

    except Exception as e:
        logger.debug("test_dependency_detection_error", error=str(e))
        return result


def _build_framework_instructions(test_deps: dict[str, Any]) -> str:
    """Build framework-specific instructions for the LLM prompt."""
    fw = test_deps["framework"]
    has_mockito = test_deps["has_mockito"]
    has_assertj = test_deps["has_assertj"]

    parts: list[str] = []

    if fw == "junit4":
        parts.append("## Test Framework: JUnit 4")
        parts.append("CRITICAL: This project uses **JUnit 4**, NOT JUnit 5.")
        parts.append("- Import `org.junit.Test` (NOT `org.junit.jupiter.api.Test`)")
        parts.append("- Use `@Before` / `@After` (NOT `@BeforeEach` / `@AfterEach`)")
        parts.append("- Do NOT use `@DisplayName` (JUnit 5 only)")
        parts.append("- Do NOT use `@ExtendWith` (JUnit 5 only)")
        parts.append("- Do NOT use `@Nested` (JUnit 5 only)")
    else:
        parts.append("## Test Framework: JUnit 5")
        parts.append("- Import `org.junit.jupiter.api.Test`")
        parts.append("- Use `@BeforeEach` / `@AfterEach`")
        parts.append("- Use `@DisplayName` for readable test descriptions")

    # Mockito (shared rules, framework-specific runner)
    if has_mockito:
        runner = (
            "- Use `@RunWith(MockitoJUnitRunner.class)` on the test class"
            if fw == "junit4"
            else "- Use `@ExtendWith(MockitoExtension.class)` on the test class"
        )
        parts.append(runner)
        parts.append("- Use `@Mock` and `@InjectMocks` annotations")
        parts.append("")
        parts.append("### Mockito Rules (compilation fails if violated):")
        parts.append(
            "- `void` methods: use `doNothing().when(mock).method()` "
            "-- NEVER `when(mock.method()).thenReturn(null)`"
        )
        parts.append(
            "- `void` methods that should throw: "
            "use `doThrow(new XxxException()).when(mock).method()`"
        )
        parts.append(
            "- Mock arg matchers: use `any(ExactClass.class)` "
            "-- NOT `anyString()` for non-String params"
        )
    else:
        parts.append("- Mockito is NOT available -- do NOT import or use Mockito")
        if fw == "junit4":
            parts.append("- Create test instances manually, use real or stub implementations")
        else:
            parts.append("- Create test instances manually")

    # Assertion library
    if has_assertj:
        parts.append("- Use AssertJ: `assertThat(x).isEqualTo(y)`")
    elif fw == "junit4":
        parts.append("- Use JUnit 4 assertions: `Assert.assertEquals()`, `Assert.assertTrue()`")
        parts.append("- Import from `org.junit.Assert`")
    else:
        parts.append("- Use JUnit 5 assertions: `Assertions.assertEquals()`, etc.")

    deps = test_deps.get("available_deps", [])
    if deps:
        parts.append(f"\n**Available test dependencies**: {', '.join(deps)}")
        parts.append(
            "CRITICAL: Only use libraries listed above. Do NOT import unavailable libraries."
        )

    return "\n".join(parts) + "\n"


@lru_cache(maxsize=32)
def _find_existing_test_example(
    project_path: str, package: str, skip_class: str = "",
) -> str:
    """Find an existing test file in the project as a style reference.

    Returns formatted prompt section, or empty string if none found.
    """
    project_dir = Path(project_path)
    test_dir = project_dir / "src" / "test" / "java"

    if not test_dir.exists():
        return ""

    package_path = package.replace(".", "/")
    skip_filename = f"{skip_class}Test.java" if skip_class else ""

    test_files: list[Path] = []

    # Look in same package first
    same_pkg = test_dir / package_path
    if same_pkg.exists():
        test_files = sorted(same_pkg.glob("*Test.java"))

    # Fallback: parent package
    if not test_files:
        parent_parts = package_path.split("/")[:-1]
        if parent_parts:
            parent_pkg = test_dir / "/".join(parent_parts)
            if parent_pkg.exists():
                test_files = sorted(parent_pkg.glob("*Test.java"))[:3]

    # Fallback: any test file in the project
    if not test_files:
        test_files = sorted(test_dir.rglob("*Test.java"))[:5]

    if not test_files:
        return ""

    for test_file in test_files:
        if skip_filename and test_file.name == skip_filename:
            continue
        try:
            content = test_file.read_text(encoding="utf-8", errors="replace")
            lines = content.split("\n")[:80]
            truncated = "\n".join(lines)
            if len(content.split("\n")) > 80:
                truncated += "\n// ... (truncated)"
            return (
                "\n## Existing Test Example (follow this style and imports):\n"
                f"```java\n{truncated}\n```\n"
            )
        except Exception:
            continue

    return ""


def _validate_generated_imports(test_code: str, test_deps: dict[str, Any]) -> list[str]:
    """Check that generated test imports match available dependencies."""
    warnings: list[str] = []
    fw = test_deps["framework"]

    if fw == "junit4":
        if "org.junit.jupiter" in test_code:
            warnings.append("Uses JUnit 5 imports but project has JUnit 4")
        if "@ExtendWith" in test_code:
            warnings.append("Uses @ExtendWith (JUnit 5) but project has JUnit 4")
        if "@BeforeEach" in test_code:
            warnings.append("Uses @BeforeEach (JUnit 5) but project has JUnit 4")
        if "@DisplayName" in test_code:
            warnings.append("Uses @DisplayName (JUnit 5) but project has JUnit 4")

    if not test_deps["has_mockito"]:
        if "org.mockito" in test_code:
            warnings.append("Uses Mockito but it is not in pom.xml")

    if not test_deps["has_assertj"]:
        if "org.assertj" in test_code:
            warnings.append("Uses AssertJ but it is not in pom.xml")

    return warnings


def _extract_dependency_signatures(project_path: str, dependencies: list[dict]) -> str:
    """Find source files for dependency classes and extract their public method signatures."""
    if not dependencies or not project_path:
        return ""
    project_dir = Path(project_path)
    results = []
    for dep in dependencies:
        dep_type = dep.get("type", "").split("<")[0].strip()
        if not dep_type or _is_primitive_type(dep_type):
            continue
        matches = list(project_dir.rglob(f"{dep_type}.java"))
        if not matches:
            continue
        try:
            source = matches[0].read_text(encoding="utf-8", errors="replace")
            sigs = _extract_public_signatures(source)
            if sigs:
                results.append(f"**{dep_type}** (field: `{dep.get('name', dep_type)}`):\n{sigs}")
        except Exception:
            pass
    return "\n".join(results)


def _extract_public_signatures(source_code: str) -> str:
    """Extract public method signatures with full parameter types from Java source."""
    pattern = re.compile(
        r"public\s+(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?"
        r"(\w[\w<>\[\], ]*?)\s+(\w+)\s*\(([^)]*)\)"
        r"(?:\s+throws\s+([\w, ]+))?",
        re.MULTILINE,
    )
    sigs = []
    for m in pattern.finditer(source_code):
        ret = m.group(1).strip()
        name = m.group(2)
        if name in {"if", "while", "for", "switch", "class", "new", "return"}:
            continue
        params = m.group(3).strip()
        throws = f" throws {m.group(4).strip()}" if m.group(4) else ""
        sigs.append(f"  - `{ret} {name}({params}){throws}`")
    return "\n".join(sigs[:20])


def _extract_token_usage(response: object) -> dict[str, int | None]:
    """Extract token usage from a LangChain response (AIMessage)."""
    usage: dict[str, int | None] = {
        "prompt_tokens": None, "completion_tokens": None, "total_tokens": None,
    }
    # Try response_metadata (Anthropic, OpenAI)
    meta = getattr(response, "response_metadata", None) or {}
    tu = meta.get("token_usage") or meta.get("usage") or {}
    if tu:
        usage["prompt_tokens"] = tu.get("prompt_tokens") or tu.get("input_tokens")
        usage["completion_tokens"] = tu.get("completion_tokens") or tu.get("output_tokens")
        usage["total_tokens"] = tu.get("total_tokens")
    # Try usage_metadata (Google GenAI / newer LangChain)
    um = getattr(response, "usage_metadata", None)
    if um and not usage["total_tokens"]:
        usage["prompt_tokens"] = getattr(um, "input_tokens", None)
        usage["completion_tokens"] = getattr(um, "output_tokens", None)
        usage["total_tokens"] = getattr(um, "total_tokens", None)
    return usage


async def fix_compilation_errors(test_code: str, compile_errors: str, class_name: str) -> str:
    """Fix compilation errors in generated test code using LLM."""
    llm = get_llm()
    template = load_prompt_template("testing/compilation_fix.md")
    prompt = render_template(template, compile_errors=compile_errors, test_code=test_code)

    logger.debug(
        "llm_fix_prompt",
        class_name=class_name,
        prompt_length=len(prompt),
        error_lines=compile_errors.count("\n") + 1,
    )

    response = await llm.ainvoke(prompt)
    raw = response.content if hasattr(response, "content") else str(response)
    code = str(raw) if not isinstance(raw, str) else raw

    usage = _extract_token_usage(response)
    logger.debug(
        "llm_fix_response",
        class_name=class_name,
        response_length=len(raw),
        **usage,
    )

    if "```java" in code:
        code = code.split("```java")[1].split("```")[0].strip()
    elif "```" in code:
        code = code.split("```")[1].split("```")[0].strip()
    return code


async def _generate_test_code_with_llm(context: dict[str, Any], source_code: str) -> str:
    """
    Generate test code using LLM for intelligent, context-aware tests.

    Args:
        context: Test generation context with class info, methods, dependencies
        source_code: The original Java source code

    Returns:
        Generated test code as string
    """
    llm = get_llm()

    class_name = context["class_name"]
    package = context["package"]
    class_type = context["class_type"]
    methods = context["methods"]
    dependencies = context["dependencies"]
    test_requirements = context.get("test_requirements", [])
    conventions = context.get("conventions", {})
    project_path = context.get("project_path", "")

    # Extract project context from pom.xml
    project_context = _extract_project_context(project_path) if project_path else ""

    # Detect test framework and available dependencies (P1/P2)
    test_deps = _detect_test_dependencies(project_path) if project_path else {
        "framework": "junit5", "has_mockito": True, "has_assertj": True,
        "has_hamcrest": False, "has_spring_test": False, "available_deps": [],
    }
    framework_instructions = _build_framework_instructions(test_deps)

    # Find existing test example for style reference (P4)
    existing_test_example = (
        _find_existing_test_example(project_path, package, class_name)
        if project_path else ""
    )

    # Extract method signatures of dependency classes so the LLM uses exact types
    dep_signatures = _extract_dependency_signatures(project_path, dependencies)
    dep_section = ""
    if dep_signatures:
        dep_section = (
            "\n## Dependency Method Signatures "
            "(use EXACT parameter types in any() matchers and doThrow/doNothing calls):\n"
            + dep_signatures + "\n"
        )

    # Build conventions section for the prompt
    conventions_section = ""
    if conventions:
        naming = conventions.get("naming", {})
        assertions = conventions.get("assertions", {})
        mocking = conventions.get("mocking", {})
        setup = conventions.get("setup_patterns", {})
        conventions_section = f"""
## Project Test Conventions (MUST follow):
- **Naming pattern**: {naming.get('dominant_pattern', 'descriptive')}
- **Case style**: {'snake_case' if naming.get('uses_snake_case') else 'camelCase'}
- **Assertion style**: {assertions.get('dominant_style', 'assertj')} (use this, not others)
- **Uses Mockito**: {'yes - use @Mock and @InjectMocks' if mocking.get('uses_mockito', True) else 'no'}
- **Uses @MockBean**: {'yes - for Spring integration' if mocking.get('uses_spring_mock_bean') else 'no - use @Mock'}
- **Uses @Nested classes**: {'yes' if setup.get('uses_nested') else 'no'}
- **Uses @ParameterizedTest**: {'yes - prefer parameterized tests for similar scenarios' if setup.get('uses_parameterized') else 'no'}
"""

    # Build class-type-specific instructions (framework-aware)
    fw = test_deps["framework"]
    mockito_runner = (
        "@RunWith(MockitoJUnitRunner.class)" if fw == "junit4"
        else "@ExtendWith(MockitoExtension.class)"
    )
    spring_runner = (
        "@RunWith(SpringRunner.class)\n- Use " if fw == "junit4"
        else ""
    )

    class_type_instructions = ""
    if class_type == "controller":
        class_type_instructions = f"""
## Controller-Specific Instructions:
- Use {spring_runner}@WebMvcTest({{class_name}}.class) for test class annotation
- Use @MockBean for service dependencies (NOT @Mock)
- Use MockMvc for HTTP request testing
- Test HTTP status codes, response body, and content type
- Skip null parameter tests (Spring @Valid handles validation)
"""
    elif class_type == "service":
        class_type_instructions = f"""
## Service-Specific Instructions:
- Use {mockito_runner}
- Use @Mock for repository and other dependencies
- Use @InjectMocks for the service under test
- Verify mock interactions with verify()
- Test business logic, validation, and exception scenarios
"""
    elif class_type == "repository":
        class_type_instructions = f"""
## Repository-Specific Instructions:
- Use {spring_runner}@DataJpaTest for repository testing
- Use TestEntityManager for test data setup
- Test custom query methods
- Verify data persistence and retrieval
"""

    # Build prompt from template
    methods_json = json.dumps(
        [{"name": m["name"], "params": m.get("parameters", []), "return_type": m.get("return_type", "void")}
         for m in methods],
        indent=2,
    )
    test_requirements_section = (
        json.dumps(test_requirements, indent=2) if test_requirements
        else "Generate standard coverage tests for all public methods."
    )

    template = load_prompt_template("testing/unit_test_generation.md")
    prompt = render_template(
        template,
        project_context=project_context,
        framework_instructions=framework_instructions,
        conventions_section=conventions_section,
        class_type_instructions=class_type_instructions,
        dep_section=dep_section,
        existing_test_example=existing_test_example,
        source_code=source_code,
        class_name=class_name,
        package=package,
        class_type=class_type,
        dependencies_json=json.dumps(dependencies, indent=2),
        methods_json=methods_json,
        test_requirements_section=test_requirements_section,
    )

    try:
        # Call LLM to generate tests
        logger.debug(
            "llm_generate_prompt",
            class_name=class_name,
            prompt_length=len(prompt),
            class_type=class_type,
        )

        response = await llm.ainvoke(prompt)

        # Extract the test code from response
        raw_content = response.content if hasattr(response, 'content') else str(response)
        # Ensure test_code is a string (LangChain content can be str or list)
        test_code: str = str(raw_content) if not isinstance(raw_content, str) else raw_content

        usage = _extract_token_usage(response)
        logger.debug(
            "llm_generate_response",
            class_name=class_name,
            response_length=len(test_code),
            **usage,
        )

        # Clean up any markdown code blocks if present
        if "```java" in test_code:
            test_code = test_code.split("```java")[1].split("```")[0].strip()
        elif "```" in test_code:
            test_code = test_code.split("```")[1].split("```")[0].strip()

        # Validate that we got actual test code
        if "@Test" not in test_code or "class" not in test_code:
            logger.warning(
                "llm_generated_invalid_test",
                class_name=class_name,
                response_preview=test_code[:200],
            )
            raise ValueError(
                f"LLM generated invalid test code for {class_name}: "
                "output does not contain @Test annotation or class declaration"
            )

        # Validate imports match available dependencies (P5)
        import_warnings = _validate_generated_imports(test_code, test_deps)
        if import_warnings:
            logger.warning(
                "generated_test_import_mismatch",
                class_name=class_name,
                warnings=import_warnings,
            )

        # Quality review pass — let LLM fix weak assertions and missing coverage
        test_code = await _review_generated_tests(test_code, source_code, class_name)

        logger.info(
            "llm_test_generation_success",
            class_name=class_name,
            test_count=test_code.count("@Test"),
        )
        return test_code

    except Exception as e:
        logger.error(
            "llm_test_generation_failed",
            class_name=class_name,
            error=str(e),
        )
        # CRITICAL: Do NOT silently fall back to templates.
        # If the LLM is unreachable, the error must propagate immediately.
        raise


async def _review_generated_tests(test_code: str, source_code: str, class_name: str) -> str:
    """Run a quality review pass on generated tests using the test_review prompt.

    Fixes weak assertions, missing coverage, mock anti-patterns.
    Falls back to original code if the review produces invalid output.
    """
    try:
        template = load_prompt_template("testing/test_review.md")
        prompt = render_template(template, test_code=test_code, source_code=source_code)

        llm = get_llm()
        response = await llm.ainvoke(prompt)
        raw = response.content if hasattr(response, "content") else str(response)
        reviewed = str(raw) if not isinstance(raw, str) else raw

        # Clean markdown fences
        if "```java" in reviewed:
            reviewed = reviewed.split("```java")[1].split("```")[0].strip()
        elif "```" in reviewed:
            reviewed = reviewed.split("```")[1].split("```")[0].strip()

        if "@Test" not in reviewed or "class" not in reviewed:
            logger.warning("test_review_invalid_output", class_name=class_name)
            return test_code

        logger.info(
            "test_review_applied",
            class_name=class_name,
            original_tests=test_code.count("@Test"),
            reviewed_tests=reviewed.count("@Test"),
        )
        return reviewed
    except Exception as e:
        logger.warning("test_review_skipped", class_name=class_name, error=str(e))
        return test_code


async def analyze_edge_cases(source_code: str, class_name: str, class_type: str) -> list[dict[str, Any]]:
    """Analyze a Java class for edge case test scenarios using the edge_case_analysis prompt.

    Returns a list of edge case scenarios as dicts with method, scenario, description,
    input_hint, expected_behavior, and category fields.
    """
    template = load_prompt_template("testing/edge_case_analysis.md")
    prompt = render_template(
        template,
        source_code=source_code,
        class_name=class_name,
        class_type=class_type,
    )

    llm = get_llm()
    response = await llm.ainvoke(prompt)
    raw = response.content if hasattr(response, "content") else str(response)
    text = str(raw) if not isinstance(raw, str) else raw

    # Extract JSON from response (may be wrapped in markdown fences)
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        scenarios = json.loads(text)
        if isinstance(scenarios, list):
            logger.info("edge_case_analysis_success", class_name=class_name, scenarios=len(scenarios))
            return scenarios
    except json.JSONDecodeError:
        logger.warning("edge_case_analysis_parse_error", class_name=class_name)

    return []


def _analyze_class(source_code: str) -> dict[str, Any]:
    """Analyze Java class structure."""
    methods: list[dict[str, Any]] = []
    dependencies: list[dict[str, str]] = []
    annotations: list[str] = []
    fields: list[str] = []
    imports: list[str] = []

    info: dict[str, Any] = {
        "class_name": "",
        "package": "",
        "methods": methods,
        "dependencies": dependencies,
        "annotations": annotations,
        "fields": fields,
        "imports": imports,
        "is_record": False,
    }

    # Extract package
    package_match = re.search(r"package\s+([\w.]+);", source_code)
    if package_match:
        info["package"] = package_match.group(1)

    # Extract imports (FIX: Add import extraction from source files)
    import_pattern = re.compile(r"import\s+([\w.]+(?:\.\*)?);", re.MULTILINE)
    for match in import_pattern.finditer(source_code):
        imports.append(match.group(1))

    # Check if this is a Java record (FIX: Add Java record detection)
    record_match = re.search(r"(?:public\s+)?record\s+(\w+)\s*\(([^)]*)\)", source_code)
    if record_match:
        info["class_name"] = record_match.group(1)
        info["is_record"] = True
        # Record components become constructor params - parse them as dependencies
        record_params = record_match.group(2)
        for param in _parse_parameters(record_params):
            # Filter out primitive types from dependencies
            if not _is_primitive_type(param["type"]):
                dependencies.append({"type": param["type"], "name": param["name"]})
        return info

    # Extract class name (also check for record)
    class_match = re.search(r"(?:public\s+)?(?:abstract\s+)?class\s+(\w+)", source_code)
    if class_match:
        info["class_name"] = class_match.group(1)

    # Extract ALL class-level annotations (before the class declaration)
    # Find where the class declaration starts
    class_decl_match = re.search(r'(?:public\s+)?(?:abstract\s+)?class\s+\w+', source_code)
    if class_decl_match:
        # Get all annotations in the code before the class declaration
        before_class = source_code[:class_decl_match.start()]
        # Find the last group of annotations (those closest to class declaration)
        # Look for annotations that are not inside method signatures
        class_annotations = re.findall(r'@(\w+)(?:\([^)]*\))?', before_class)
        # Filter to class-level annotations (skip parameter annotations like @Valid)
        class_level_annots = [a for a in class_annotations if a in (
            'Controller', 'RestController', 'Service', 'Repository', 'Component',
            'RequestMapping', 'Timed', 'Transactional', 'Configuration', 'Bean',
            'Slf4j', 'Log4j2', 'Data', 'Entity', 'Table', 'Document'
        )]
        annotations.extend(class_level_annots)

    # FIX: Extract constructor parameters for dependency injection
    # Modern Spring uses constructor injection without @Autowired annotation
    class_name = info["class_name"]
    if class_name:
        constructor_pattern = re.compile(
            rf"(?:public\s+)?{re.escape(class_name)}\s*\(([^)]*)\)",
            re.MULTILINE | re.DOTALL
        )
        for match in constructor_pattern.finditer(source_code):
            constructor_params = match.group(1)
            if constructor_params.strip():
                for param in _parse_parameters(constructor_params):
                    # Only add non-primitive types as dependencies
                    if not _is_primitive_type(param["type"]):
                        # Avoid duplicates
                        if not any(d["name"] == param["name"] for d in dependencies):
                            dependencies.append({"type": param["type"], "name": param["name"]})

    # Extract methods (FIX: capture visibility to filter private methods)
    # FIX: Use two-step approach to handle annotations with parentheses
    method_sig_pattern = re.compile(
        r"(public|private|protected)\s+"
        r"(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?"
        r"(\w+(?:<[^>]+>)?)\s+"
        r"(\w+)\s*\(",
        re.MULTILINE,
    )

    for match in method_sig_pattern.finditer(source_code):
        visibility = match.group(1)
        return_type = match.group(2)
        method_name = match.group(3)

        # Skip constructors
        if method_name == info["class_name"]:
            continue

        # FIX: Filter private methods - they shouldn't be tested directly
        if visibility == "private":
            continue

        # FIX: Extract balanced parentheses for parameters
        # (handles annotations like @PathVariable("ownerId") correctly)
        params = _extract_balanced_parens(source_code, match.end() - 1)

        # Parse parameters into structured form
        parsed_params = _parse_parameters(params)

        methods.append(
            {
                "name": method_name,
                "return_type": return_type,
                "parameters": params,
                "parsed_params": parsed_params,
                "is_void": return_type == "void",
                "visibility": visibility,
            }
        )

    # Extract dependencies (fields with @Autowired, @Inject, etc.)
    # This is a fallback for field injection pattern
    dep_pattern = re.compile(
        r"@(?:Autowired|Inject|Resource)\s+(?:private\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)", re.MULTILINE
    )

    for match in dep_pattern.finditer(source_code):
        dep_type = match.group(1)
        dep_name = match.group(2)
        # Avoid duplicates (may already be added from constructor)
        if not any(d["name"] == dep_name for d in dependencies):
            dependencies.append({"type": dep_type, "name": dep_name})

    # Analyze JPA entity fields for @GeneratedValue, @Id
    jpa_info = _analyze_jpa_fields(source_code)
    info["jpa_info"] = jpa_info
    info["is_jpa_entity"] = "Entity" in annotations or "Table" in annotations

    return info


def _analyze_jpa_fields(source_code: str) -> dict[str, Any]:
    """Analyze JPA entity fields to detect @GeneratedValue, @Id, and field types.

    This information is critical for generating correct tests that don't call
    setId() on @GeneratedValue fields.
    """
    jpa_info: dict[str, Any] = {
        "id_field": None,
        "id_type": None,
        "has_generated_value": False,
        "generated_value_strategy": None,
        "date_fields": [],  # Fields using Date vs LocalDate
    }

    # Pattern to detect @Id field with potential @GeneratedValue
    # Matches patterns like:
    # @Id
    # @GeneratedValue(strategy = GenerationType.IDENTITY)
    # private Long id;
    id_block_pattern = re.compile(
        r'@Id\s*'
        r'(?:@GeneratedValue\s*(?:\(\s*(?:strategy\s*=\s*)?(?:GenerationType\.)?(\w+)\s*\))?\s*)?'
        r'(?:@\w+(?:\([^)]*\))?\s*)*'  # Other annotations
        r'(?:private|protected)?\s*'
        r'(\w+)\s+'  # Type (Long, Integer, UUID, etc.)
        r'(\w+)\s*;',  # Field name
        re.MULTILINE | re.DOTALL
    )

    id_match = id_block_pattern.search(source_code)
    if id_match:
        strategy = id_match.group(1)  # IDENTITY, SEQUENCE, AUTO, etc.
        id_type = id_match.group(2)   # Long, Integer, UUID
        id_name = id_match.group(3)   # id, entityId, etc.

        jpa_info["id_field"] = id_name
        jpa_info["id_type"] = id_type
        jpa_info["has_generated_value"] = strategy is not None or "@GeneratedValue" in source_code
        jpa_info["generated_value_strategy"] = strategy

    # Also check for simpler @GeneratedValue pattern
    if not jpa_info["has_generated_value"] and "@GeneratedValue" in source_code:
        jpa_info["has_generated_value"] = True

    # Detect date field types (java.util.Date vs java.time.LocalDate)
    date_pattern = re.compile(
        r'(?:private|protected)?\s*'
        r'(Date|LocalDate|LocalDateTime|Instant|ZonedDateTime)\s+'
        r'(\w+)\s*;',
        re.MULTILINE
    )

    for match in date_pattern.finditer(source_code):
        date_type = match.group(1)
        field_name = match.group(2)
        jpa_info["date_fields"].append({
            "name": field_name,
            "type": date_type
        })

    return jpa_info


def _is_primitive_type(type_name: str) -> bool:
    """Check if a type is a Java primitive or wrapper type."""
    primitives = {
        "int", "long", "short", "byte", "double", "float", "boolean", "char",
        "Integer", "Long", "Short", "Byte", "Double", "Float", "Boolean", "Character",
        "String", "java.lang.String", "java.lang.Integer", "java.lang.Long",
        "java.lang.Double", "java.lang.Float", "java.lang.Boolean",
    }
    # Strip generics and 'final' modifier
    clean_type = type_name.replace("final", "").strip().split("<")[0].strip()
    return clean_type in primitives


def _extract_balanced_parens(text: str, start_pos: int) -> str:
    """Extract content between balanced parentheses starting at start_pos.

    This handles nested parentheses correctly, unlike a simple regex [^)]*.
    For example: @PathVariable("ownerId") int ownerId -> correctly captures full params
    """
    depth = 0
    content = []
    i = start_pos
    while i < len(text):
        c = text[i]
        if c == "(":
            if depth > 0:
                content.append(c)
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return "".join(content)
            content.append(c)
        elif depth > 0:
            content.append(c)
        i += 1
    return "".join(content)


def _detect_class_type(source_code: str, class_info: dict[str, Any]) -> str:
    """Auto-detect class type from code patterns."""
    class_name = class_info["class_name"].lower()
    annotations = [a.lower() for a in class_info["annotations"]]

    if "controller" in class_name or "restcontroller" in annotations or "controller" in annotations:
        return "controller"
    elif "service" in class_name or "service" in annotations:
        return "service"
    elif "repository" in class_name or "repository" in annotations:
        return "repository"
    elif "entity" in annotations or "table" in annotations:
        return "model"
    else:
        return "utility"


def _get_test_file_path(project_dir: Path, source_path: Path) -> Path:
    """Generate test file path from source file path."""
    # Convert main/java to test/java
    relative = source_path.relative_to(project_dir)
    parts = list(relative.parts)

    if "main" in parts:
        idx = parts.index("main")
        parts[idx] = "test"

    # Add Test suffix to filename
    filename = parts[-1]
    if filename.endswith(".java"):
        parts[-1] = filename.replace(".java", "Test.java")

    # Return relative path from project root (not absolute path)
    return Path(*parts)


def _parse_parameters(params_str: str) -> list[dict[str, str]]:
    """Parse Java method parameters into structured form."""
    if not params_str or not params_str.strip():
        return []

    params = []
    # Split by comma, handling generic types
    depth = 0
    current = ""
    for char in params_str:
        if char in "<(":
            depth += 1
        elif char in ">)":
            depth -= 1
        elif char == "," and depth == 0:
            if current.strip():
                params.append(current.strip())
            current = ""
            continue
        current += char

    if current.strip():
        params.append(current.strip())

    result = []
    for param in params:
        # Handle annotations like @Valid, @PathVariable, etc.
        param = re.sub(r"@\w+(?:\([^)]*\))?\s*", "", param).strip()
        # FIX: Remove 'final' modifier from parameter type
        param = re.sub(r"\bfinal\s+", "", param).strip()
        parts = param.rsplit(None, 1)
        if len(parts) == 2:
            param_type, param_name = parts
            result.append({"type": param_type, "name": param_name})

    return result
