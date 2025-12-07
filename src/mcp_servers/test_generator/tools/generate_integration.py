"""
Generate integration tests tool.

Generates integration tests for service interactions, database operations,
and component integration using Testcontainers and Spring test slices.
"""

import json
import re
from pathlib import Path
from typing import Any


async def generate_integration_tests(
    project_path: str, source_file: str, test_containers: bool = True, mock_external: bool = True
) -> str:
    """
    Generate integration tests for a source file.

    Args:
        project_path: Path to the Java project root directory
        source_file: Path to the source file to generate tests for
        test_containers: Use Testcontainers for database tests
        mock_external: Mock external service calls

    Returns:
        JSON string with generated integration test code
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
    class_info = _analyze_for_integration(source_code)

    # Determine integration test type
    test_type = _determine_integration_type(class_info)

    # Generate test file path
    test_file_path = _get_integration_test_path(project_dir, source_path)

    # Generate test code
    test_code = _generate_integration_code(class_info, test_type, test_containers, mock_external)

    results = {
        "success": True,
        "source_file": str(source_path),
        "test_file": str(test_file_path),
        "test_type": test_type,
        "test_code": test_code,
        "uses_testcontainers": test_containers and test_type in ["repository", "database"],
        "uses_wiremock": mock_external and test_type == "api_client",
        "test_count": test_code.count("@Test"),
    }

    return json.dumps(results, indent=2)


def _analyze_for_integration(source_code: str) -> dict[str, Any]:
    """Analyze source for integration test requirements."""
    annotations: list[str] = []
    endpoints: list[dict[str, str]] = []
    dependencies: list[dict[str, str]] = []
    info: dict[str, Any] = {
        "class_name": "",
        "package": "",
        "annotations": annotations,
        "has_repository": False,
        "has_rest_client": False,
        "has_database": False,
        "has_messaging": False,
        "endpoints": endpoints,
        "dependencies": dependencies,
    }

    # Extract package
    package_match = re.search(r"package\s+([\w.]+);", source_code)
    if package_match:
        info["package"] = package_match.group(1)

    # Extract class name
    class_match = re.search(r"class\s+(\w+)", source_code)
    if class_match:
        info["class_name"] = class_match.group(1)

    # Extract annotations
    found_annotations = re.findall(r"@(\w+)", source_code)
    annotations.extend(list(set(found_annotations)))

    # Check for repository usage
    if "Repository" in source_code or "JpaRepository" in source_code:
        info["has_repository"] = True

    # Check for REST client
    if "RestTemplate" in source_code or "WebClient" in source_code or "FeignClient" in annotations:
        info["has_rest_client"] = True

    # Check for database annotations
    if any(a in annotations for a in ["Entity", "Table", "Query", "Transactional"]):
        info["has_database"] = True

    # Check for messaging
    if any(a in annotations for a in ["KafkaListener", "RabbitListener", "JmsListener"]):
        info["has_messaging"] = True

    # Extract REST endpoints
    endpoint_pattern = re.compile(
        r'@(GetMapping|PostMapping|PutMapping|DeleteMapping|RequestMapping)\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']',
        re.MULTILINE,
    )
    for match in endpoint_pattern.finditer(source_code):
        endpoints.append(
            {"method": match.group(1).replace("Mapping", "").upper(), "path": match.group(2)}
        )

    return info


def _determine_integration_type(class_info: dict[str, Any]) -> str:
    """Determine the type of integration test needed."""
    annotations = class_info["annotations"]

    if "RestController" in annotations or "Controller" in annotations:
        return "web_mvc"
    elif "Repository" in annotations or class_info["has_repository"]:
        return "repository"
    elif class_info["has_rest_client"]:
        return "api_client"
    elif class_info["has_database"]:
        return "database"
    elif class_info["has_messaging"]:
        return "messaging"
    else:
        return "service"


def _get_integration_test_path(project_dir: Path, source_path: Path) -> Path:
    """Generate integration test file path."""
    relative = source_path.relative_to(project_dir)
    parts = list(relative.parts)

    if "main" in parts:
        idx = parts.index("main")
        parts[idx] = "test"

    filename = parts[-1]
    if filename.endswith(".java"):
        parts[-1] = filename.replace(".java", "IntegrationTest.java")

    return project_dir / Path(*parts)


def _generate_integration_code(
    class_info: dict[str, Any], test_type: str, test_containers: bool, mock_external: bool
) -> str:
    """Generate integration test code."""
    class_name = class_info["class_name"]
    package = class_info["package"]

    # Build imports based on test type
    imports = [
        f"package {package};",
        "",
        "import org.junit.jupiter.api.Test;",
        "import org.junit.jupiter.api.DisplayName;",
        "import org.springframework.beans.factory.annotation.Autowired;",
    ]

    # Add type-specific imports
    if test_type == "web_mvc":
        imports.extend(
            [
                "import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;",
                "import org.springframework.test.web.servlet.MockMvc;",
                "import org.springframework.boot.test.mock.mockito.MockBean;",
                "import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;",
                "import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;",
            ]
        )
    elif test_type == "repository":
        imports.extend(
            [
                "import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;",
                "import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;",
            ]
        )
        if test_containers:
            imports.extend(
                [
                    "import org.testcontainers.containers.PostgreSQLContainer;",
                    "import org.testcontainers.junit.jupiter.Container;",
                    "import org.testcontainers.junit.jupiter.Testcontainers;",
                    "import org.springframework.test.context.DynamicPropertyRegistry;",
                    "import org.springframework.test.context.DynamicPropertySource;",
                ]
            )
    elif test_type == "service":
        imports.extend(
            [
                "import org.springframework.boot.test.context.SpringBootTest;",
                "import org.springframework.boot.test.mock.mockito.MockBean;",
            ]
        )
    elif test_type == "api_client":
        if mock_external:
            imports.extend(
                [
                    "import org.springframework.boot.test.context.SpringBootTest;",
                    "import com.github.tomakehurst.wiremock.junit5.WireMockTest;",
                    "import static com.github.tomakehurst.wiremock.client.WireMock.*;",
                ]
            )

    imports.extend(["import static org.assertj.core.api.Assertions.*;", ""])

    # Build test class
    test_class_name = f"{class_name}IntegrationTest"
    class_body = []

    # Add class annotations
    if test_type == "web_mvc":
        class_body.append(f"@WebMvcTest({class_name}.class)")
    elif test_type == "repository":
        if test_containers:
            class_body.append("@Testcontainers")
        class_body.append("@DataJpaTest")
    elif test_type in ["service", "api_client"]:
        class_body.append("@SpringBootTest")

    if test_type == "api_client" and mock_external:
        class_body.append("@WireMockTest(httpPort = 8089)")

    class_body.extend(
        [f'@DisplayName("{class_name} Integration Tests")', f"class {test_class_name} {{", ""]
    )

    # Add testcontainers if needed
    if test_type == "repository" and test_containers:
        class_body.extend(
            [
                "    @Container",
                '    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15")',
                '            .withDatabaseName("testdb")',
                '            .withUsername("test")',
                '            .withPassword("test");',
                "",
                "    @DynamicPropertySource",
                "    static void configureProperties(DynamicPropertyRegistry registry) {",
                '        registry.add("spring.datasource.url", postgres::getJdbcUrl);',
                '        registry.add("spring.datasource.username", postgres::getUsername);',
                '        registry.add("spring.datasource.password", postgres::getPassword);',
                "    }",
                "",
            ]
        )

    # Add autowired fields
    if test_type == "web_mvc":
        class_body.extend(["    @Autowired", "    private MockMvc mockMvc;", ""])
    elif test_type == "repository":
        class_body.extend(
            [
                "    @Autowired",
                "    private TestEntityManager entityManager;",
                "",
                "    @Autowired",
                f"    private {class_name} {_to_camel_case(class_name)};",
                "",
            ]
        )
    else:
        class_body.extend(
            ["    @Autowired", f"    private {class_name} {_to_camel_case(class_name)};", ""]
        )

    # Generate test methods based on type
    if test_type == "web_mvc" and class_info["endpoints"]:
        for endpoint in class_info["endpoints"][:3]:  # Limit to 3 endpoints
            tests = _generate_mvc_test(endpoint, class_name)
            class_body.extend(tests)
    elif test_type == "repository":
        class_body.extend(_generate_repository_tests(class_name))
    elif test_type == "api_client" and mock_external:
        class_body.extend(_generate_api_client_tests(class_name))
    else:
        class_body.extend(_generate_service_integration_tests(class_name))

    class_body.append("}")

    return "\n".join(imports + class_body)


def _generate_mvc_test(endpoint: dict[str, str], class_name: str) -> list[str]:
    """Generate MockMvc test for an endpoint."""
    method = endpoint["method"]
    path = endpoint["path"]
    method_name = method.lower()

    return [
        "    @Test",
        f'    @DisplayName("Should handle {method} {path}")',
        f"    void should{method.title()}{_path_to_method_name(path)}() throws Exception {{",
        f'        mockMvc.perform({method_name}("{path}"))',
        "                .andExpect(status().isOk());",
        "    }",
        "",
    ]


def _generate_repository_tests(class_name: str) -> list[str]:
    """Generate repository integration tests."""
    _ = _to_camel_case(class_name)  # Reserved for future entity instance naming
    return [
        "    @Test",
        '    @DisplayName("Should save and retrieve entity")',
        "    void shouldSaveAndRetrieveEntity() {",
        "        // Arrange - create test entity",
        "",
        "        // Act - save and retrieve",
        "",
        "        // Assert",
        "        assertThat(result).isNotNull();",
        "    }",
        "",
        "    @Test",
        '    @DisplayName("Should find by criteria")',
        "    void shouldFindByCriteria() {",
        "        // Arrange - persist test data",
        "",
        "        // Act - query with criteria",
        "",
        "        // Assert",
        "        assertThat(results).isNotEmpty();",
        "    }",
        "",
    ]


def _generate_api_client_tests(class_name: str) -> list[str]:
    """Generate API client integration tests with WireMock."""
    instance = _to_camel_case(class_name)
    return [
        "    @Test",
        '    @DisplayName("Should call external API successfully")',
        "    void shouldCallExternalApiSuccessfully() {",
        "        // Arrange - stub external API",
        '        stubFor(get(urlEqualTo("/api/resource"))',
        "                .willReturn(aResponse()",
        "                        .withStatus(200)",
        '                        .withHeader("Content-Type", "application/json")',
        '                        .withBody("{\\"status\\": \\"ok\\"}")));',
        "",
        "        // Act",
        f"        var result = {instance}.callExternalApi();",
        "",
        "        // Assert",
        "        assertThat(result).isNotNull();",
        '        verify(getRequestedFor(urlEqualTo("/api/resource")));',
        "    }",
        "",
        "    @Test",
        '    @DisplayName("Should handle external API error")',
        "    void shouldHandleExternalApiError() {",
        "        // Arrange - stub error response",
        '        stubFor(get(urlEqualTo("/api/resource"))',
        "                .willReturn(aResponse().withStatus(500)));",
        "",
        "        // Act & Assert",
        f"        assertThatThrownBy(() -> {instance}.callExternalApi())",
        "                .isInstanceOf(RuntimeException.class);",
        "    }",
        "",
    ]


def _generate_service_integration_tests(class_name: str) -> list[str]:
    """Generate service integration tests."""
    instance = _to_camel_case(class_name)
    return [
        "    @Test",
        '    @DisplayName("Should integrate with dependencies")',
        "    void shouldIntegrateWithDependencies() {",
        "        // Arrange",
        "",
        "        // Act",
        f"        var result = {instance}.performOperation();",
        "",
        "        // Assert",
        "        assertThat(result).isNotNull();",
        "    }",
        "",
        "    @Test",
        '    @DisplayName("Should handle transactional operations")',
        "    void shouldHandleTransactionalOperations() {",
        "        // Arrange",
        "",
        "        // Act",
        "",
        "        // Assert - verify data persistence",
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
    # Remove leading slash and convert to PascalCase
    parts = path.strip("/").split("/")
    result = ""
    for part in parts:
        if part and not part.startswith("{"):
            result += part.title().replace("-", "").replace("_", "")
    return result or "Root"
