"""
Generate adaptive unit tests tool.

Generates unit tests adapted to project conventions and class type,
using LLM to create intelligent test cases.
"""

import json
import re
from pathlib import Path
from typing import Any


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
    }

    # Generate test code based on class type and requirements
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


def _analyze_class(source_code: str) -> dict[str, Any]:
    """Analyze Java class structure."""
    methods: list[dict[str, Any]] = []
    dependencies: list[dict[str, str]] = []
    annotations: list[str] = []
    fields: list[str] = []

    info: dict[str, Any] = {
        "class_name": "",
        "package": "",
        "methods": methods,
        "dependencies": dependencies,
        "annotations": annotations,
        "fields": fields,
    }

    # Extract package
    package_match = re.search(r"package\s+([\w.]+);", source_code)
    if package_match:
        info["package"] = package_match.group(1)

    # Extract class name
    class_match = re.search(r"(?:public\s+)?(?:abstract\s+)?class\s+(\w+)", source_code)
    if class_match:
        info["class_name"] = class_match.group(1)

    # Extract class annotations
    class_annotations = re.findall(
        r"@(\w+)(?:\([^)]*\))?\s*(?:public\s+)?(?:abstract\s+)?class", source_code
    )
    annotations.extend(class_annotations)

    # Extract methods
    method_pattern = re.compile(
        r"(?:@\w+(?:\([^)]*\))?\s*)*"
        r"(?:public|private|protected)\s+"
        r"(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?"
        r"(\w+(?:<[^>]+>)?)\s+"
        r"(\w+)\s*\(([^)]*)\)",
        re.MULTILINE,
    )

    for match in method_pattern.finditer(source_code):
        return_type = match.group(1)
        method_name = match.group(2)
        params = match.group(3)

        # Skip constructors and getters/setters for basic testing
        if method_name == info["class_name"]:
            continue

        # Parse parameters into structured form
        parsed_params = _parse_parameters(params)

        methods.append(
            {
                "name": method_name,
                "return_type": return_type,
                "parameters": params,
                "parsed_params": parsed_params,
                "is_void": return_type == "void",
            }
        )

    # Extract dependencies (fields with @Autowired, @Inject, etc.)
    dep_pattern = re.compile(
        r"@(?:Autowired|Inject|Resource)\s+(?:private\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)", re.MULTILINE
    )

    for match in dep_pattern.finditer(source_code):
        dependencies.append({"type": match.group(1), "name": match.group(2)})

    return info


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

    # Determine test style from conventions
    uses_mockito = conventions.get("mocking", {}).get("uses_mockito", True)
    uses_assertj = conventions.get("assertions", {}).get("dominant_style") == "assertj"

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
                "import org.mockito.InjectMocks;",
                "import org.mockito.MockitoAnnotations;",
                "import static org.mockito.Mockito.*;",
            ]
        )

    if uses_assertj:
        imports.append("import static org.assertj.core.api.Assertions.*;")
    else:
        imports.append("import static org.junit.jupiter.api.Assertions.*;")

    imports.append("")

    # Build class body
    test_class_name = f"{class_name}Test"

    class_body = [f'@DisplayName("{class_name} Unit Tests")', f"class {test_class_name} {{", ""]

    # Add mocks for dependencies
    for dep in dependencies:
        class_body.append("    @Mock")
        class_body.append(f"    private {dep['type']} {dep['name']};")
        class_body.append("")

    # Add class under test
    if dependencies:
        class_body.append("    @InjectMocks")
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
        class_body.append("        MockitoAnnotations.openMocks(this);")
    else:
        class_body.append(f"        {_to_camel_case(class_name)} = new {class_name}();")

    class_body.extend(["    }", ""])

    # Generate tests from impact analysis requirements FIRST (priority)
    if test_requirements:
        class_body.append("    // ========== Tests from Impact Analysis ==========")
        class_body.append("")
        for req in test_requirements:
            req_tests = _generate_requirement_test(req, class_name, uses_assertj, methods)
            class_body.extend(req_tests)

    # Generate standard test methods for remaining methods
    class_body.append("    // ========== Standard Coverage Tests ==========")
    class_body.append("")
    for method in methods:
        test_methods = _generate_method_tests(method, class_name, class_type, uses_assertj)
        class_body.extend(test_methods)

    class_body.append("}")

    return "\n".join(imports + class_body)


def _generate_requirement_test(
    req: dict[str, Any],
    class_name: str,
    uses_assertj: bool,
    methods: list[dict[str, Any]],
) -> list[str]:
    """Generate a test based on an impact analysis requirement."""
    tests = []
    instance_name = _to_camel_case(class_name)

    # Extract requirement info
    test_name = req.get("suggested_test_name", f"test{req.get('id', 'Requirement')}")
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
            else:
                tests.append(f"        var result = {instance_name}.{method_call};")

            tests.append("")
            tests.append("        // Assert")
            if not matched_method.get("is_void"):
                if uses_assertj:
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
    method: dict[str, Any], class_name: str, class_type: str, uses_assertj: bool
) -> list[str]:
    """Generate test methods for a single method."""
    method_name = method["name"]
    return_type = method["return_type"]
    is_void = method["is_void"]
    parsed_params = method.get("parsed_params", [])
    instance_name = _to_camel_case(class_name)

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
    test_name = f"should{_to_pascal_case(method_name)}Successfully"
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
    if arrange_vars:
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

    # Test 2: Edge case / null handling (for methods with parameters)
    if parsed_params:
        test_name = f"should{_to_pascal_case(method_name)}HandleNullInput"
        tests.extend(
            [
                "    @Test",
                f'    @DisplayName("{method_name} should handle null input")',
                f"    void {test_name}() {{",
                "        // Arrange - null parameters",
            ]
        )

        # Generate null values for nullable params
        null_params = []
        for p in parsed_params:
            if p["type"].lower() in ("int", "long", "double", "float", "boolean", "byte", "short", "char"):
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
            tests.append("            .isInstanceOf(IllegalArgumentException.class);")
        else:
            tests.append(f"        assertThrows(IllegalArgumentException.class, () -> {instance_name}.{null_method_call});")

        tests.extend(["    }", ""])

    return tests


def _generate_arrange_variables(parsed_params: list[dict[str, str]]) -> list[str]:
    """Generate variable declarations for test arrange section."""
    vars_list = []
    for param in parsed_params:
        param_type = param["type"]
        param_name = param["name"]
        # Only generate variables for complex types
        if param_type not in ("String", "int", "long", "double", "float", "boolean", "Integer", "Long", "Double", "Float", "Boolean"):
            value = _generate_test_value(param_type, param_name)
            vars_list.append(f"{param_type} {param_name} = {value};")
    return vars_list


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
        # For custom objects, try to create a new instance or mock
        simple_type = param_type.split("<")[0].strip()
        return f"new {simple_type}()"
