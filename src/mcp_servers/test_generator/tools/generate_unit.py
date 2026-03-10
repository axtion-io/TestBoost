"""
Generate adaptive unit tests tool.

Generates unit tests adapted to project conventions and class type,
using LLM to create intelligent test cases.
"""

import json
import re
from pathlib import Path
from typing import Any

from src.lib.config import get_settings
from src.lib.llm import get_llm
from src.lib.logging import get_logger

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


def _extract_project_context(project_path: str) -> str:
    """Extract key project info from pom.xml for LLM context.

    Args:
        project_path: Root directory of the Java project

    Returns:
        Formatted string with project context, or empty string if unavailable
    """
    import xml.etree.ElementTree as ET

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


def _load_strategy_guidelines(project_path: str) -> str:
    """Load key guidelines from the unit test strategy template.

    Args:
        project_path: Project root (used to locate TestBoost root)

    Returns:
        Formatted string with strategy guidelines, or empty string
    """
    # Try to find the strategy file relative to the TestBoost root
    for base in [Path(__file__).parent.parent.parent.parent.parent, Path(project_path)]:
        strategy_file = base / "config" / "prompts" / "testing" / "unit_test_strategy.md"
        if strategy_file.exists():
            try:
                content = strategy_file.read_text(encoding="utf-8")
                # Extract the mutation-resistant patterns section
                sections = []
                if "## Mutation-Resistant" in content:
                    start = content.index("## Mutation-Resistant")
                    end = content.index("## Expected Output", start) if "## Expected Output" in content[start:] else len(content)
                    sections.append(content[start:end].strip())
                if sections:
                    return "\n\n" + "\n\n".join(sections) + "\n"
            except Exception:
                pass
    return ""


async def _generate_test_code_with_llm(context: dict[str, Any], source_code: str) -> str:
    """
    Generate test code using LLM for intelligent, context-aware tests.

    Args:
        context: Test generation context with class info, methods, dependencies
        source_code: The original Java source code

    Returns:
        Generated test code as string
    """
    get_settings()
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

    # Build class-type-specific instructions
    class_type_instructions = ""
    if class_type == "controller":
        class_type_instructions = """
## Controller-Specific Instructions:
- Use @WebMvcTest({class_name}.class) for test class annotation
- Use @MockBean for service dependencies (NOT @Mock)
- Use MockMvc for HTTP request testing
- Test HTTP status codes, response body, and content type
- Skip null parameter tests (Spring @Valid handles validation)
"""
    elif class_type == "service":
        class_type_instructions = """
## Service-Specific Instructions:
- Use @ExtendWith(MockitoExtension.class)
- Use @Mock for repository and other dependencies
- Use @InjectMocks for the service under test
- Verify mock interactions with verify()
- Test business logic, validation, and exception scenarios
"""
    elif class_type == "repository":
        class_type_instructions = """
## Repository-Specific Instructions:
- Use @DataJpaTest for repository testing
- Use TestEntityManager for test data setup
- Test custom query methods
- Verify data persistence and retrieval
"""

    # Load strategy template if available
    strategy_guidelines = _load_strategy_guidelines(project_path)

    # Build the prompt for test generation
    prompt = f"""You are an expert Java test engineer specializing in unit testing with JUnit 5, Mockito, and AssertJ. Generate comprehensive, mutation-resistant unit tests for the following Java class.

{project_context}
{conventions_section}
{class_type_instructions}
## Source Code to Test:
```java
{source_code}
```

## Class Analysis:
- Class Name: {class_name}
- Package: {package}
- Type: {class_type}
- Dependencies to mock: {json.dumps(dependencies, indent=2)}
- Public methods: {json.dumps([{"name": m["name"], "params": m.get("parameters", []), "return_type": m.get("return_type", "void")} for m in methods], indent=2)}

## Test Requirements:
{json.dumps(test_requirements, indent=2) if test_requirements else "Generate standard coverage tests for all public methods."}

## Instructions:
1. Generate a complete, compilable JUnit 5 test class
2. Use Mockito for mocking dependencies (constructor injection pattern)
3. Include @BeforeEach setup method
4. For each public method, generate:
   - Happy path test (valid inputs, expected output)
   - Edge case tests (null handling, boundary values)
   - Error scenario tests where applicable
5. Use @DisplayName for readable test descriptions
6. Use meaningful test data, not generic placeholders (e.g. "john@example.com" not "test")
7. For reactive types (Mono/Flux), use StepVerifier
8. Follow AAA pattern: Arrange, Act, Assert
9. Include proper imports at the top
10. Make tests mutation-resistant:
    - Assert exact return values, not just non-null
    - Test boundary conditions (at, below, above)
    - Verify both true AND false paths for boolean returns
    - Use specific equality assertions
{strategy_guidelines}
## JPA Entity Guidelines (CRITICAL):
- NEVER call setId() on @GeneratedValue fields - use ReflectionTestUtils.setField(entity, "id", 1L)
- Use Optional.of(entity) for present values, Optional.empty() for not-found scenarios
- Use correct ID types (Long for JPA, not Integer)
- Check actual date field type before using date values

## Output Format:
Return ONLY the complete Java test class code, starting with `package` statement.
Do not include any explanation or markdown - just the raw Java code.
"""

    try:
        # Call LLM to generate tests
        response = await llm.ainvoke(prompt)

        # Extract the test code from response
        raw_content = response.content if hasattr(response, 'content') else str(response)
        # Ensure test_code is a string (LangChain content can be str or list)
        test_code: str = str(raw_content) if not isinstance(raw_content, str) else raw_content

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
