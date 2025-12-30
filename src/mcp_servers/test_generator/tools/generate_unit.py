"""
Generate adaptive unit tests tool.

Generates unit tests adapted to project conventions and class type,
using LLM to create intelligent test cases.

Two modes:
- LLM mode (default): Uses LLM to generate intelligent, context-aware tests
- Template mode: Uses templates for CI environments without LLM access
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
    use_llm: bool = True,
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
        use_llm: If True (default), use LLM for intelligent test generation.
                 If False, use template-based generation (for CI without LLM).

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
    }

    # Generate test code - LLM mode or template mode
    if use_llm:
        logger.info("generating_tests_with_llm", class_name=class_info["class_name"])
        test_code = await _generate_test_code_with_llm(context, source_code)
    else:
        logger.info("generating_tests_with_templates", class_name=class_info["class_name"])
        test_code = _generate_test_code(context)

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


async def _generate_test_code_with_llm(context: dict[str, Any], source_code: str) -> str:
    """
    Generate test code using LLM for intelligent, context-aware tests.

    Args:
        context: Test generation context with class info, methods, dependencies
        source_code: The original Java source code

    Returns:
        Generated test code as string
    """
    settings = get_settings()
    llm = get_llm()

    class_name = context["class_name"]
    package = context["package"]
    class_type = context["class_type"]
    methods = context["methods"]
    dependencies = context["dependencies"]
    test_requirements = context.get("test_requirements", [])

    # Build the prompt for test generation
    prompt = f"""You are an expert Java test engineer. Generate comprehensive JUnit 5 unit tests for the following Java class.

## Source Code to Test:
```java
{source_code}
```

## Class Analysis:
- Class Name: {class_name}
- Package: {package}
- Type: {class_type}
- Dependencies to mock: {json.dumps(dependencies, indent=2)}
- Public methods: {json.dumps([m["name"] for m in methods], indent=2)}

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
6. Use meaningful test data, not generic placeholders
7. For reactive types (Mono/Flux), use StepVerifier
8. Follow AAA pattern: Arrange, Act, Assert
9. Include proper imports at the top

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
            # Fall back to template generation
            logger.info("falling_back_to_templates", reason="LLM output validation failed")
            return _generate_test_code(context)

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
        # Fall back to template generation
        logger.info("falling_back_to_templates", reason=str(e))
        return _generate_test_code(context)


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

    return info


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

    return project_dir / Path(*parts)


def _generate_test_code(context: dict[str, Any]) -> str:
    """Generate test code based on context and test requirements."""
    class_name = context["class_name"]
    package = context["package"]
    class_type = context["class_type"]
    methods = context["methods"]
    dependencies = context["dependencies"]
    conventions = context.get("conventions", {})
    test_requirements = context.get("test_requirements", [])
    source_imports = context.get("imports", [])
    is_record = context.get("is_record", False)

    # Determine test style from conventions
    uses_mockito = conventions.get("mocking", {}).get("uses_mockito", True)
    uses_assertj = conventions.get("assertions", {}).get("dominant_style") == "assertj"

    # FIX: Track test method names for uniqueness
    used_test_names: set[str] = set()

    # Check if class uses reactive types (Mono/Flux)
    uses_reactive = _uses_reactive_types(methods)

    # Build imports
    imports = [
        f"package {package};",
        "",
        "import org.junit.jupiter.api.Test;",
        "import org.junit.jupiter.api.BeforeEach;",
        "import org.junit.jupiter.api.DisplayName;",
    ]

    if uses_mockito and dependencies:
        imports.extend(
            [
                "import org.mockito.Mock;",
                "import org.mockito.Mockito;",
                "import org.mockito.junit.jupiter.MockitoExtension;",
                "import org.junit.jupiter.api.extension.ExtendWith;",
            ]
        )

    if uses_assertj:
        imports.append("import static org.assertj.core.api.Assertions.*;")
    else:
        imports.append("import static org.junit.jupiter.api.Assertions.*;")

    # FIX: Add reactive type support (StepVerifier for Mono/Flux)
    if uses_reactive:
        imports.append("import reactor.test.StepVerifier;")

    # FIX: Add relevant imports from source file
    # Filter to common useful imports for testing
    for imp in source_imports:
        # Skip test-related imports and framework internals
        if any(skip in imp for skip in ["junit", "mockito", "assertj", "hamcrest"]):
            continue
        # Include model/domain imports, utility imports
        if any(keep in imp for keep in [
            package.rsplit(".", 1)[0] if "." in package else package,  # Same package prefix
            "java.util",
            "java.time",
            "java.math",
        ]):
            import_line = f"import {imp};"
            if import_line not in imports:
                imports.append(import_line)

    imports.append("")

    # Build class body
    test_class_name = f"{class_name}Test"

    class_body = []
    if uses_mockito and dependencies:
        class_body.append("@ExtendWith(MockitoExtension.class)")
    class_body.extend([f'@DisplayName("{class_name} Unit Tests")', f"class {test_class_name} {{", ""])

    # Add mocks for dependencies
    for dep in dependencies:
        class_body.append("    @Mock")
        class_body.append(f"    private {dep['type']} {dep['name']};")
        class_body.append("")

    # Add class under test
    class_body.append(f"    private {class_name} {_to_camel_case(class_name)};")
    class_body.append("")

    # Add setup method
    class_body.extend(
        [
            "    @BeforeEach",
            "    void setUp() {",
        ]
    )

    if dependencies:
        # FIX: Create instance with constructor injection (modern Spring pattern)
        dep_names = ", ".join(d["name"] for d in dependencies)
        class_body.append(f"        {_to_camel_case(class_name)} = new {class_name}({dep_names});")
    elif is_record:
        # FIX: Java records need all-args constructor
        class_body.append(f"        // Note: {class_name} is a record - provide required arguments")
        class_body.append(f"        {_to_camel_case(class_name)} = new {class_name}(/* TODO: provide record components */);")
    else:
        class_body.append(f"        {_to_camel_case(class_name)} = new {class_name}();")

    class_body.extend(["    }", ""])

    # Generate tests from impact analysis requirements FIRST (priority)
    if test_requirements:
        class_body.append("    // ========== Tests from Impact Analysis ==========")
        class_body.append("")
        for req in test_requirements:
            req_tests = _generate_requirement_test(req, class_name, uses_assertj, methods, used_test_names, uses_reactive)
            class_body.extend(req_tests)

    # Generate standard test methods for remaining methods
    class_body.append("    // ========== Standard Coverage Tests ==========")
    class_body.append("")
    for method in methods:
        test_methods = _generate_method_tests(method, class_name, class_type, uses_assertj, used_test_names, uses_reactive, dependencies)
        class_body.extend(test_methods)

    class_body.append("}")

    return "\n".join(imports + class_body)


def _uses_reactive_types(methods: list[dict[str, Any]]) -> bool:
    """Check if any method returns reactive types (Mono/Flux)."""
    for method in methods:
        return_type = method.get("return_type", "")
        if "Mono" in return_type or "Flux" in return_type:
            return True
    return False


def _get_unique_test_name(base_name: str, used_names: set[str]) -> str:
    """Get a unique test method name, adding suffix if needed."""
    if base_name not in used_names:
        used_names.add(base_name)
        return base_name

    # Add suffix to make unique
    counter = 2
    while f"{base_name}{counter}" in used_names:
        counter += 1
    unique_name = f"{base_name}{counter}"
    used_names.add(unique_name)
    return unique_name


def _generate_requirement_test(
    req: dict[str, Any],
    class_name: str,
    uses_assertj: bool,
    methods: list[dict[str, Any]],
    used_test_names: set[str] | None = None,
    uses_reactive: bool = False,
) -> list[str]:
    """Generate a test based on an impact analysis requirement."""
    if used_test_names is None:
        used_test_names = set()

    tests = []
    instance_name = _to_camel_case(class_name)

    # Extract requirement info
    base_test_name = req.get("suggested_test_name", f"test{req.get('id', 'Requirement')}")
    # FIX: Ensure unique test method names
    test_name = _get_unique_test_name(base_test_name, used_test_names)
    description = req.get("description", "Verify requirement")
    scenario_type = req.get("scenario_type", "nominal")
    target_method = req.get("target_method")

    # Find matching method if target_method is specified
    matched_method = None
    if target_method:
        for m in methods:
            if m["name"] == target_method:
                matched_method = m
                break

    # Check if this method returns reactive types (for StepVerifier assertions)
    is_reactive_method = matched_method is not None and (
        "Mono" in (matched_method.get("return_type") or "") or
        "Flux" in (matched_method.get("return_type") or "")
    )
    reactive_return_type = (matched_method.get("return_type") or "") if is_reactive_method and matched_method else ""

    # Generate test based on scenario type
    tests.extend([
        "    @Test",
        f'    @DisplayName("{description[:80]}")',
        f"    void {test_name}() {{",
    ])

    if scenario_type == "edge_case":
        # Edge case: test validation/rejection
        # Generate smart invalid values based on description
        invalid_data = _generate_invalid_data_from_description(description, test_name, matched_method)

        tests.append("        // Arrange - invalid input scenario")
        for line in invalid_data["arrange_lines"]:
            tests.append(f"        {line}")

        tests.extend([
            "",
            "        // Act & Assert - should reject invalid input",
        ])

        method_call = invalid_data["method_call"]
        exception_type = invalid_data.get("exception_type", "IllegalArgumentException")

        if uses_assertj:
            tests.append(f"        assertThatThrownBy(() -> {instance_name}.{method_call})")
            tests.append(f"            .isInstanceOf({exception_type}.class);")
        else:
            tests.append(f"        assertThrows({exception_type}.class, () -> {instance_name}.{method_call});")

    elif scenario_type == "regression":
        # Regression: verify bug fix
        tests.extend([
            "        // Arrange - scenario that previously caused bug",
            "        // TODO: Set up the specific condition that was fixed",
            "",
            "        // Act",
        ])
        if matched_method:
            params = matched_method.get("parsed_params", [])
            if params:
                param_values = [_generate_test_value(p["type"], p["name"]) for p in params]
                method_call = f"{target_method}({', '.join(param_values)})"
            else:
                method_call = f"{target_method}()"
            tests.append(f"        var result = {instance_name}.{method_call};")
        else:
            tests.append("        // TODO: Call the method under test")
        tests.extend([
            "",
            "        // Assert - verify bug is fixed",
            "        // TODO: Add specific assertion for the bug fix",
        ])

    elif scenario_type == "invariant":
        # Invariant: verify business rule always holds
        tests.extend([
            "        // Arrange - business rule scenario",
            "        // TODO: Set up business rule test data",
            "",
            "        // Act",
        ])
        if matched_method:
            params = matched_method.get("parsed_params", [])
            if params:
                param_values = [_generate_test_value(p["type"], p["name"]) for p in params]
                method_call = f"{target_method}({', '.join(param_values)})"
            else:
                method_call = f"{target_method}()"
            tests.append(f"        var result = {instance_name}.{method_call};")
        else:
            tests.append("        // TODO: Call the method under test")
        tests.extend([
            "",
            "        // Assert - business rule must always hold",
            "        // TODO: Verify business invariant",
        ])

    else:  # nominal
        # Nominal: happy path test
        tests.append("        // Arrange")
        if matched_method:
            params = matched_method.get("parsed_params", [])
            for p in params:
                if p["type"] not in ("String", "int", "long", "double", "float", "boolean"):
                    tests.append(f"        {p['type']} {p['name']} = {_generate_test_value(p['type'], p['name'])};")

            tests.append("")
            tests.append("        // Act")
            if params:
                param_values = [_generate_test_value(p["type"], p["name"]) for p in params]
                method_call = f"{target_method}({', '.join(param_values)})"
            else:
                method_call = f"{target_method}()"

            if matched_method.get("is_void"):
                tests.append(f"        {instance_name}.{method_call};")
            elif is_reactive_method:
                # Use StepVerifier for reactive types (Mono/Flux)
                tests.append(f"        {reactive_return_type} result = {instance_name}.{method_call};")
            else:
                tests.append(f"        var result = {instance_name}.{method_call};")

            tests.append("")
            tests.append("        // Assert")
            if not matched_method.get("is_void"):
                if is_reactive_method:
                    # Use StepVerifier for reactive assertions
                    if "Mono" in reactive_return_type:
                        tests.append("        StepVerifier.create(result)")
                        tests.append("            .expectNextCount(1)")
                        tests.append("            .verifyComplete();")
                    else:  # Flux
                        tests.append("        StepVerifier.create(result)")
                        tests.append("            .thenConsumeWhile(item -> true)")
                        tests.append("            .verifyComplete();")
                elif uses_assertj:
                    tests.append("        assertThat(result).isNotNull();")
                else:
                    tests.append("        assertNotNull(result);")
            else:
                tests.append("        // Verify expected side effects")
        else:
            tests.extend([
                "        // TODO: Set up test data",
                "",
                "        // Act",
                "        // TODO: Call method under test",
                "",
                "        // Assert",
                "        // TODO: Verify expected outcome",
            ])

    tests.extend(["    }", ""])
    return tests


def _generate_method_tests(
    method: dict[str, Any],
    class_name: str,
    class_type: str,
    uses_assertj: bool,
    used_test_names: set[str] | None = None,
    uses_reactive: bool = False,
    dependencies: list[dict[str, str]] | None = None,
) -> list[str]:
    """Generate test methods for a single method."""
    if used_test_names is None:
        used_test_names = set()
    if dependencies is None:
        dependencies = []

    method_name = method["name"]
    return_type = method["return_type"]
    is_void = method["is_void"]
    parsed_params = method.get("parsed_params", [])
    instance_name = _to_camel_case(class_name)

    # FIX: Check if this method returns reactive types
    is_reactive = "Mono" in return_type or "Flux" in return_type

    tests = []

    # Generate method call with proper parameters
    if parsed_params:
        param_values = [_generate_test_value(p["type"], p["name"]) for p in parsed_params]
        method_call = f"{method_name}({', '.join(param_values)})"
        # Generate variable declarations for complex types
        arrange_vars = _generate_arrange_variables(parsed_params)
    else:
        method_call = f"{method_name}()"
        arrange_vars = []

    # Test 1: Basic success case
    base_test_name = f"should{_to_pascal_case(method_name)}Successfully"
    test_name = _get_unique_test_name(base_test_name, used_test_names)
    tests.extend(
        [
            "    @Test",
            f'    @DisplayName("{method_name} should execute successfully")',
            f"    void {test_name}() {{",
            "        // Arrange",
        ]
    )

    # Add variable declarations
    for var in arrange_vars:
        tests.append(f"        {var}")

    # FIX: Add basic mock stubs for common repository patterns
    mock_stubs = _generate_mock_stubs(method_name, return_type, parsed_params, dependencies)
    for stub in mock_stubs:
        tests.append(f"        {stub}")

    if arrange_vars or mock_stubs:
        tests.append("")

    if is_void:
        tests.extend(
            [
                "        // Act",
                f"        {instance_name}.{method_call};",
                "",
                "        // Assert",
                "        // Verify expected behavior",
            ]
        )
    elif is_reactive:
        # FIX: Use StepVerifier for reactive types
        tests.extend(
            [
                "        // Act",
                f"        {return_type} result = {instance_name}.{method_call};",
                "",
                "        // Assert - use StepVerifier for reactive types",
            ]
        )
        if "Mono" in return_type:
            tests.append("        StepVerifier.create(result)")
            tests.append("            .expectNextCount(1)")
            tests.append("            .verifyComplete();")
        else:  # Flux
            tests.append("        StepVerifier.create(result)")
            tests.append("            .thenConsumeWhile(item -> true)")
            tests.append("            .verifyComplete();")
    else:
        tests.extend(
            [
                "        // Act",
                f"        {return_type} result = {instance_name}.{method_call};",
                "",
                "        // Assert",
            ]
        )
        if uses_assertj:
            tests.append("        assertThat(result).isNotNull();")
        else:
            tests.append("        assertNotNull(result);")

    tests.extend(["    }", ""])

    # Test 2: Edge case / null handling
    # SKIP for controllers - Spring @Valid handles null validation at HTTP layer,
    # not in the method body. The method never receives null for @Valid params.
    # For service/utility classes, null tests may still be appropriate.
    if class_type not in ("controller",):
        nullable_params = [p for p in parsed_params if not _is_primitive_type(p["type"])]
        if not nullable_params:
            return tests
        base_test_name = f"should{_to_pascal_case(method_name)}HandleNullInput"
        test_name = _get_unique_test_name(base_test_name, used_test_names)
        tests.extend(
            [
                "    @Test",
                f'    @DisplayName("{method_name} should handle null input")',
                f"    void {test_name}() {{",
                "        // Arrange - null parameters",
            ]
        )

        # Generate null values for nullable params, keep valid values for primitives
        null_params = []
        for p in parsed_params:
            if _is_primitive_type(p["type"]):
                null_params.append(_generate_test_value(p["type"], p["name"]))
            else:
                null_params.append("null")

        null_method_call = f"{method_name}({', '.join(null_params)})"

        tests.extend(
            [
                "",
                "        // Act & Assert",
            ]
        )

        if uses_assertj:
            tests.append(f"        assertThatThrownBy(() -> {instance_name}.{null_method_call})")
            tests.append("            .isInstanceOf(NullPointerException.class);")
        else:
            tests.append(f"        assertThrows(NullPointerException.class, () -> {instance_name}.{null_method_call});")

        tests.extend(["    }", ""])

    return tests


def _generate_arrange_variables(parsed_params: list[dict[str, str]]) -> list[str]:
    """Generate variable declarations for test arrange section."""
    vars_list = []
    for param in parsed_params:
        param_type = param["type"]
        param_name = param["name"]
        # FIX: Use _is_primitive_type for consistent type checking
        if not _is_primitive_type(param_type):
            value = _generate_test_value(param_type, param_name)
            vars_list.append(f"{param_type} {param_name} = {value};")
    return vars_list


def _generate_mock_stubs(
    method_name: str,
    return_type: str,
    parsed_params: list[dict[str, str]],
    dependencies: list[dict[str, str]] | None = None,
) -> list[str]:
    """Generate mock stubs for common repository/service patterns.

    This adds Mockito.when(...).thenReturn(...) stubs for methods that likely
    call repository/service dependencies.
    """
    stubs: list[str] = []
    method_lower = method_name.lower()

    # Find repository and mapper dependency names
    repo_name = None
    mapper_name = None
    if dependencies:
        for dep in dependencies:
            dep_type = dep.get("type", "")
            if "Repository" in dep_type and not repo_name:
                repo_name = dep.get("name")
            elif "Mapper" in dep_type and not mapper_name:
                mapper_name = dep.get("name")

    # If no repo found, skip mock generation
    if not repo_name:
        return stubs

    # Common patterns that need mock setup:
    # - create/save methods need repository.save() to return the entity
    # - find/get methods need repository.findById() to return Optional.of(entity)
    # - update methods need repository.findById() + repository.save()

    # Extract the entity type from return type (e.g., Owner from Optional<Owner>)
    entity_type = return_type
    if "Optional<" in return_type:
        entity_type = return_type.replace("Optional<", "").replace(">", "")
    elif "List<" in return_type:
        entity_type = return_type.replace("List<", "").replace(">", "")

    # Check for common method patterns
    if "create" in method_lower or "save" in method_lower or "add" in method_lower:
        # For create methods, mock mapper.map() + repository.save()
        if entity_type and not _is_primitive_type(entity_type):
            stubs.append(f"{entity_type} mappedEntity = new {entity_type}();")
            # Add mapper stub if mapper exists
            if mapper_name:
                # Find Request parameter
                request_param = next((p for p in parsed_params if p["type"].endswith("Request") or p["type"].endswith("DTO")), None)
                if request_param:
                    stubs.append(f"Mockito.when({mapper_name}.map(Mockito.any({entity_type}.class), Mockito.eq({request_param['name']}))).thenReturn(mappedEntity);")
            stubs.append(f"Mockito.when({repo_name}.save(mappedEntity)).thenReturn(mappedEntity);")

    elif "update" in method_lower or "modify" in method_lower:
        # For update methods, mock findById + save
        # For void methods, we need to infer the entity type from the repo name
        actual_entity = entity_type
        if entity_type == "void" or not entity_type or _is_primitive_type(entity_type):
            # Try to infer entity from repo type (e.g., OwnerRepository -> Owner)
            repo_type = next((d.get("type", "") for d in (dependencies or []) if d.get("name") == repo_name), "")
            if "Repository" in repo_type:
                actual_entity = repo_type.replace("Repository", "")

        if actual_entity and actual_entity != "void" and not _is_primitive_type(actual_entity):
            stubs.append(f"{actual_entity} existingEntity = new {actual_entity}();")
            # Check if there's an ID parameter
            id_param = next((p for p in parsed_params if "id" in p["name"].lower()), None)
            if id_param:
                id_value = _generate_test_value(id_param["type"], id_param["name"])
                stubs.append(f"Mockito.when({repo_name}.findById({id_value})).thenReturn(Optional.of(existingEntity));")

    elif "find" in method_lower or "get" in method_lower:
        # For find methods, mock findById or findAll
        if "Optional" in return_type and entity_type:
            stubs.append(f"{entity_type} foundEntity = new {entity_type}();")
            id_param = next((p for p in parsed_params if "id" in p["name"].lower()), None)
            if id_param:
                id_value = _generate_test_value(id_param["type"], id_param["name"])
                stubs.append(f"Mockito.when({repo_name}.findById({id_value})).thenReturn(Optional.of(foundEntity));")
        elif "List" in return_type:
            stubs.append(f"Mockito.when({repo_name}.findAll()).thenReturn(List.of());")

    return stubs


def _to_camel_case(name: str) -> str:
    """Convert PascalCase to camelCase."""
    if not name:
        return name
    return name[0].lower() + name[1:]


def _to_pascal_case(name: str) -> str:
    """Convert camelCase to PascalCase."""
    if not name:
        return name
    return name[0].upper() + name[1:]


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


def _generate_invalid_data_from_description(
    description: str,
    test_name: str,
    matched_method: dict[str, Any] | None,
) -> dict[str, Any]:
    """Generate smart invalid data based on test description and name."""
    desc_lower = description.lower()
    name_lower = test_name.lower()
    combined = desc_lower + " " + name_lower

    arrange_lines = []
    exception_type = "IllegalArgumentException"

    # Detect what kind of invalid data to generate
    if "email" in combined and ("invalid" in combined or "format" in combined):
        # Invalid email format
        arrange_lines.append('String invalidEmail = "not-a-valid-email";')
        if matched_method and matched_method.get("parsed_params"):
            param = matched_method["parsed_params"][0]
            param_type = param["type"]
            arrange_lines.append(f'{param_type} request = new {param_type}();')
            arrange_lines.append('request.setEmail(invalidEmail);')
            method_call = f"{matched_method['name']}(request)"
        else:
            method_call = 'createOwner(request)'

    elif "duplicate" in combined or "already exists" in combined:
        # Duplicate entry
        exception_type = "IllegalStateException"
        if matched_method and matched_method.get("parsed_params"):
            param = matched_method["parsed_params"][0]
            param_type = param["type"]
            arrange_lines.append(f'{param_type} request = new {param_type}();')
            arrange_lines.append('request.setEmail("existing@example.com");')
            arrange_lines.append('// Assume this email already exists in repository')
            method_call = f"{matched_method['name']}(request)"
        else:
            method_call = 'createOwner(request)'

    elif "null" in combined or "empty" in combined:
        # Null or empty input
        if matched_method:
            method_call = f"{matched_method['name']}(null)"
        else:
            method_call = "method(null)"

    elif "past" in combined or "date" in combined:
        # Invalid date (in the past)
        arrange_lines.append('LocalDate pastDate = LocalDate.now().minusDays(1);')
        if matched_method and matched_method.get("parsed_params"):
            param = matched_method["parsed_params"][0]
            param_type = param["type"]
            arrange_lines.append(f'{param_type} request = new {param_type}();')
            arrange_lines.append('request.setDate(pastDate);')
            method_call = f"{matched_method['name']}(request)"
        else:
            method_call = 'create(request)'

    elif "maximum" in combined or "limit" in combined or "exceed" in combined:
        # Exceeds limit
        exception_type = "IllegalStateException"
        arrange_lines.append('// Setup: already at maximum allowed')
        if matched_method and matched_method.get("parsed_params"):
            params = matched_method["parsed_params"]
            param_values = [_generate_test_value(p["type"], p["name"]) for p in params]
            method_call = f"{matched_method['name']}({', '.join(param_values)})"
        else:
            method_call = 'create(request)'

    elif "negative" in combined or "invalid" in combined:
        # Generic invalid value
        if matched_method and matched_method.get("parsed_params"):
            params = matched_method["parsed_params"]
            invalid_values = []
            for p in params:
                if p["type"].lower() in ("int", "integer", "long"):
                    invalid_values.append("-1")
                elif p["type"].lower() in ("string",):
                    invalid_values.append('""')
                else:
                    invalid_values.append("null")
            method_call = f"{matched_method['name']}({', '.join(invalid_values)})"
        else:
            method_call = "method(-1)"

    else:
        # Default: use null for object types
        if matched_method and matched_method.get("parsed_params"):
            params = matched_method["parsed_params"]
            null_values = []
            for p in params:
                if p["type"].lower() in ("int", "long", "double", "float", "boolean"):
                    null_values.append(_generate_test_value(p["type"], p["name"]))
                else:
                    null_values.append("null")
            method_call = f"{matched_method['name']}({', '.join(null_values)})"
        else:
            method_call = "method(null)"

    return {
        "arrange_lines": arrange_lines,
        "method_call": method_call,
        "exception_type": exception_type,
    }


def _generate_test_value(param_type: str, param_name: str) -> str:
    """Generate appropriate test values based on parameter type."""
    type_lower = param_type.lower()

    # Handle common types
    if type_lower in ("string", "java.lang.string"):
        if "email" in param_name.lower():
            return '"test@example.com"'
        elif "name" in param_name.lower():
            return '"Test Name"'
        elif "id" in param_name.lower():
            return '"test-id-123"'
        else:
            return '"test-value"'
    elif type_lower in ("int", "integer", "java.lang.integer"):
        if "id" in param_name.lower():
            return "1"
        elif "count" in param_name.lower() or "size" in param_name.lower():
            return "10"
        else:
            return "42"
    elif type_lower in ("long", "java.lang.long"):
        return "1L"
    elif type_lower in ("double", "java.lang.double"):
        return "3.14"
    elif type_lower in ("float", "java.lang.float"):
        return "1.5f"
    elif type_lower in ("boolean", "java.lang.boolean"):
        return "true"
    elif type_lower == "bigdecimal" or "decimal" in type_lower:
        return 'new BigDecimal("100.00")'
    elif type_lower == "localdate" or "date" in type_lower:
        return "LocalDate.now()"
    elif type_lower == "localdatetime":
        return "LocalDateTime.now()"
    elif "list" in type_lower:
        return "List.of()"
    elif "set" in type_lower:
        return "Set.of()"
    elif "map" in type_lower:
        return "Map.of()"
    elif "optional" in type_lower:
        return "Optional.empty()"
    else:
        # For custom objects, check if it's a common DTO/Request pattern
        simple_type = param_type.split("<")[0].strip()

        # FIX: Handle common record/DTO patterns that need all-args constructors
        # These are typically records in Spring Boot projects
        if simple_type.endswith("Request") or simple_type.endswith("DTO"):
            # Generate with typical string fields for request objects
            return f'new {simple_type}("firstName", "lastName", "address", "city", "1234567890")'
        elif simple_type.endswith("Command") or simple_type.endswith("Event"):
            return f'new {simple_type}("test-id", "test-data")'
        else:
            # Default: try no-args constructor
            return f"new {simple_type}()"
