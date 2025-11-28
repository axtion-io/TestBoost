"""
Generate snapshot tests tool.

Generates snapshot tests for API responses, serialization,
and other deterministic outputs.
"""

import json
import re
from pathlib import Path
from typing import Any


async def generate_snapshot_tests(
    project_path: str, source_file: str, snapshot_format: str = "json"
) -> str:
    """
    Generate snapshot tests for a source file.

    Args:
        project_path: Path to the Java project root directory
        source_file: Path to the source file to generate tests for
        snapshot_format: Format for snapshot files (json, xml, text)

    Returns:
        JSON string with generated snapshot test code
    """
    project_dir = Path(project_path)
    source_path = Path(source_file)

    if not source_path.exists():
        source_path = project_dir / source_file
        if not source_path.exists():
            return json.dumps({"success": False, "error": f"Source file not found: {source_file}"})

    # Read source code
    try:
        source_code = source_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return json.dumps({"success": False, "error": f"Failed to read source file: {e}"})

    # Analyze source
    class_info = _analyze_for_snapshot(source_code)

    # Generate test file path
    test_file_path = _get_snapshot_test_path(project_dir, source_path)

    # Generate test code
    test_code = _generate_snapshot_code(class_info, snapshot_format)

    results = {
        "success": True,
        "source_file": str(source_path),
        "test_file": str(test_file_path),
        "snapshot_format": snapshot_format,
        "test_code": test_code,
        "endpoints_covered": len(class_info.get("endpoints", [])),
        "test_count": test_code.count("@Test"),
    }

    return json.dumps(results, indent=2)


def _analyze_for_snapshot(source_code: str) -> dict[str, Any]:
    """Analyze source for snapshot test generation."""
    info = {
        "class_name": "",
        "package": "",
        "endpoints": [],
        "dto_methods": [],
        "is_controller": False,
        "is_dto": False,
    }

    # Extract package
    package_match = re.search(r"package\s+([\w.]+);", source_code)
    if package_match:
        info["package"] = package_match.group(1)

    # Extract class name
    class_match = re.search(r"class\s+(\w+)", source_code)
    if class_match:
        info["class_name"] = class_match.group(1)

    # Check if controller
    if "@RestController" in source_code or "@Controller" in source_code:
        info["is_controller"] = True

        # Extract endpoints
        endpoint_pattern = re.compile(
            r'@(GetMapping|PostMapping|PutMapping|DeleteMapping)\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']',
            re.MULTILINE,
        )
        for match in endpoint_pattern.finditer(source_code):
            info["endpoints"].append(
                {"method": match.group(1).replace("Mapping", "").upper(), "path": match.group(2)}
            )

    # Check if DTO/model
    if any(ann in source_code for ann in ["@Data", "@Value", "@Builder", "record "]):
        info["is_dto"] = True

        # Extract methods that return something
        method_pattern = re.compile(
            r"public\s+(\w+(?:<[^>]+>)?)\s+(\w+)\s*\([^)]*\)\s*\{", re.MULTILINE
        )
        for match in method_pattern.finditer(source_code):
            return_type = match.group(1)
            method_name = match.group(2)
            if return_type not in ["void", "boolean"]:
                info["dto_methods"].append({"name": method_name, "return_type": return_type})

    return info


def _get_snapshot_test_path(project_dir: Path, source_path: Path) -> Path:
    """Generate snapshot test file path."""
    relative = source_path.relative_to(project_dir)
    parts = list(relative.parts)

    if "main" in parts:
        idx = parts.index("main")
        parts[idx] = "test"

    filename = parts[-1]
    if filename.endswith(".java"):
        parts[-1] = filename.replace(".java", "SnapshotTest.java")

    return project_dir / Path(*parts)


def _generate_snapshot_code(class_info: dict, snapshot_format: str) -> str:
    """Generate snapshot test code."""
    class_name = class_info["class_name"]
    package = class_info["package"]

    # Build imports
    imports = [
        f"package {package};",
        "",
        "import org.junit.jupiter.api.Test;",
        "import org.junit.jupiter.api.DisplayName;",
    ]

    if class_info["is_controller"]:
        imports.extend(
            [
                "import org.springframework.beans.factory.annotation.Autowired;",
                "import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;",
                "import org.springframework.boot.test.mock.mockito.MockBean;",
                "import org.springframework.test.web.servlet.MockMvc;",
                "import org.springframework.test.web.servlet.MvcResult;",
                "import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;",
                "import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;",
            ]
        )

    imports.extend(
        [
            "import com.fasterxml.jackson.databind.ObjectMapper;",
            "import com.fasterxml.jackson.databind.SerializationFeature;",
            "import static org.assertj.core.api.Assertions.*;",
            "",
            "import java.nio.file.Files;",
            "import java.nio.file.Path;",
            "import java.nio.file.Paths;",
            "",
        ]
    )

    # Build test class
    test_class_name = f"{class_name}SnapshotTest"

    class_body = []

    if class_info["is_controller"]:
        class_body.append(f"@WebMvcTest({class_name}.class)")

    class_body.extend(
        [
            f'@DisplayName("{class_name} Snapshot Tests")',
            f"class {test_class_name} {{",
            "",
            "    private final ObjectMapper objectMapper = new ObjectMapper()",
            "            .enable(SerializationFeature.INDENT_OUTPUT);",
            "",
            '    private static final String SNAPSHOTS_DIR = "src/test/resources/snapshots";',
            "",
        ]
    )

    if class_info["is_controller"]:
        class_body.extend(["    @Autowired", "    private MockMvc mockMvc;", ""])

    # Add snapshot helper methods
    class_body.extend(
        [
            "    private void assertMatchesSnapshot(String actual, String snapshotName) throws Exception {",
            "        Path snapshotPath = Paths.get(SNAPSHOTS_DIR, snapshotName);",
            "",
            "        if (!Files.exists(snapshotPath)) {",
            "            // Create snapshot on first run",
            "            Files.createDirectories(snapshotPath.getParent());",
            "            Files.writeString(snapshotPath, actual);",
            "            return;",
            "        }",
            "",
            "        String expected = Files.readString(snapshotPath);",
            "        assertThat(actual).isEqualToIgnoringWhitespace(expected);",
            "    }",
            "",
        ]
    )

    # Generate test methods
    if class_info["is_controller"] and class_info["endpoints"]:
        for endpoint in class_info["endpoints"][:5]:
            tests = _generate_endpoint_snapshot_test(endpoint, class_name, snapshot_format)
            class_body.extend(tests)
    elif class_info["is_dto"]:
        class_body.extend(_generate_dto_snapshot_tests(class_name, snapshot_format))
    else:
        class_body.extend(_generate_generic_snapshot_tests(class_name, snapshot_format))

    class_body.append("}")

    return "\n".join(imports + class_body)


def _generate_endpoint_snapshot_test(
    endpoint: dict, class_name: str, snapshot_format: str
) -> list[str]:
    """Generate snapshot test for an endpoint."""
    method = endpoint["method"]
    path = endpoint["path"]
    method_lower = method.lower()
    snapshot_name = f"{class_name.lower()}_{_path_to_filename(path)}.{snapshot_format}"

    return [
        "    @Test",
        f'    @DisplayName("Snapshot: {method} {path}")',
        f"    void snapshot{method.title()}{_path_to_method_name(path)}() throws Exception {{",
        f'        MvcResult result = mockMvc.perform({method_lower}("{path}")',
        '                .contentType("application/json"))',
        "                .andExpect(status().isOk())",
        "                .andReturn();",
        "",
        "        String response = result.getResponse().getContentAsString();",
        f'        assertMatchesSnapshot(response, "{snapshot_name}");',
        "    }",
        "",
    ]


def _generate_dto_snapshot_tests(class_name: str, snapshot_format: str) -> list[str]:
    """Generate snapshot tests for DTO serialization."""
    instance = _to_camel_case(class_name)

    return [
        "    @Test",
        '    @DisplayName("Snapshot: JSON serialization")',
        "    void snapshotJsonSerialization() throws Exception {",
        f"        {class_name} {instance} = createSample{class_name}();",
        "",
        f"        String json = objectMapper.writeValueAsString({instance});",
        "",
        f'        assertMatchesSnapshot(json, "{class_name.lower()}_serialization.{snapshot_format}");',
        "    }",
        "",
        "    @Test",
        '    @DisplayName("Snapshot: JSON deserialization roundtrip")',
        "    void snapshotJsonRoundtrip() throws Exception {",
        f"        {class_name} original = createSample{class_name}();",
        "",
        "        String json = objectMapper.writeValueAsString(original);",
        f"        {class_name} deserialized = objectMapper.readValue(json, {class_name}.class);",
        "",
        "        assertThat(deserialized).usingRecursiveComparison().isEqualTo(original);",
        "    }",
        "",
        f"    private {class_name} createSample{class_name}() {{",
        f"        // TODO: Create sample {class_name} instance",
        f"        return new {class_name}();",
        "    }",
        "",
    ]


def _generate_generic_snapshot_tests(class_name: str, snapshot_format: str) -> list[str]:
    """Generate generic snapshot tests."""
    instance = _to_camel_case(class_name)

    return [
        "    @Test",
        '    @DisplayName("Snapshot: Output format")',
        "    void snapshotOutputFormat() throws Exception {",
        "        // Arrange",
        f"        {class_name} {instance} = new {class_name}();",
        "",
        "        // Act",
        f"        String output = objectMapper.writeValueAsString({instance});",
        "",
        "        // Assert",
        f'        assertMatchesSnapshot(output, "{class_name.lower()}_output.{snapshot_format}");',
        "    }",
        "",
    ]


def _to_camel_case(name: str) -> str:
    """Convert PascalCase to camelCase."""
    if not name:
        return name
    return name[0].lower() + name[1:]


def _path_to_method_name(path: str) -> str:
    """Convert URL path to method name."""
    parts = path.strip("/").split("/")
    result = ""
    for part in parts:
        if part and not part.startswith("{"):
            result += part.title().replace("-", "").replace("_", "")
    return result or "Root"


def _path_to_filename(path: str) -> str:
    """Convert URL path to filename."""
    return path.strip("/").replace("/", "_").replace("{", "").replace("}", "") or "root"
