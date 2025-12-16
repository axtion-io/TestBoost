"""
Test Generation Workflow using LangGraph.

DEPRECATED: This workflow is deprecated in favor of test_generation_agent.py (T062).
The new workflow uses DeepAgents for real LLM agent integration with tool calls.

Implements a full workflow for analyzing Java projects, generating tests,
running mutation testing, and generating killer tests if needed.
"""

import json
import warnings
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

warnings.warn(
    "test_generation.py workflow is deprecated. "
    "Use test_generation_agent.py with DeepAgents LLM integration instead. "
    "See 002-deepagents-integration spec for details.",
    DeprecationWarning,
    stacklevel=2,
)


class TestGenerationState(BaseModel):
    """State for the test generation workflow."""

    # Session tracking
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    project_path: str = ""
    project_name: str = ""

    # Project analysis
    project_context: dict[str, Any] = Field(default_factory=dict)
    test_conventions: dict[str, Any] = Field(default_factory=dict)
    source_files: list[dict[str, Any]] = Field(default_factory=list)
    classified_classes: list[dict[str, Any]] = Field(default_factory=list)

    # Test generation tracking
    generated_unit_tests: list[dict[str, Any]] = Field(default_factory=list)
    generated_integration_tests: list[dict[str, Any]] = Field(default_factory=list)
    generated_snapshot_tests: list[dict[str, Any]] = Field(default_factory=list)
    generated_e2e_tests: list[dict[str, Any]] = Field(default_factory=list)

    # Compilation results
    compilation_results: dict[str, Any] = Field(default_factory=dict)
    compilation_retries: int = 0
    max_retries: int = 3

    # Docker/E2E state
    docker_deployed: bool = False
    app_health: dict[str, Any] = Field(default_factory=dict)

    # Mutation testing
    mutation_results: dict[str, Any] = Field(default_factory=dict)
    mutation_score: float = 0.0
    target_mutation_score: float = 80.0
    surviving_mutants: list[dict[str, Any]] = Field(default_factory=list)

    # Killer tests
    killer_tests_generated: list[dict[str, Any]] = Field(default_factory=list)

    # Quality report
    quality_report: dict[str, Any] = Field(default_factory=dict)

    # Workflow state
    current_step: str = ""
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    completed: bool = False

    # Messages for chat interface
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True


async def analyze_project_structure(state: TestGenerationState) -> dict[str, Any]:
    """
    Analyze the project structure and context.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from pathlib import Path

    from src.mcp_servers.test_generator.tools.analyze import analyze_project_context

    result = await analyze_project_context(state.project_path)
    context = json.loads(result)

    if not context.get("success"):
        return {
            "errors": state.errors
            + [f"Project analysis failed: {context.get('error', 'Unknown')}"],
            "current_step": "analyze_project_structure",
        }

    # Extract project name
    module_info = context.get("module_info", {})
    project_name = module_info.get("artifactId") or Path(state.project_path).name

    # Find source files to test
    source_files = []
    src_dir = Path(state.project_path) / "src" / "main" / "java"
    if src_dir.exists():
        for java_file in src_dir.rglob("*.java"):
            source_files.append(
                {
                    "path": str(java_file),
                    "name": java_file.stem,
                    "package": _extract_package(java_file),
                }
            )

    message = (
        f"Analyzed project {project_name}: "
        f"{context.get('project_type', 'java')} project with "
        f"{len(source_files)} source files"
    )

    return {
        "project_name": project_name,
        "project_context": context,
        "source_files": source_files[:100],  # Limit for performance
        "current_step": "analyze_project_structure",
        "messages": [AIMessage(content=message)],
    }


async def detect_conventions(state: TestGenerationState) -> dict[str, Any]:
    """
    Detect test conventions used in the project.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from src.mcp_servers.test_generator.tools.conventions import detect_test_conventions

    result = await detect_test_conventions(state.project_path)
    conventions = json.loads(result)

    if not conventions.get("success"):
        # Not a fatal error - use defaults
        conventions = {
            "naming": {"dominant_pattern": "should_when"},
            "assertions": {"dominant_style": "assertj"},
            "mocking": {"uses_mockito": True},
        }

    message = (
        f"Detected conventions: {conventions.get('naming', {}).get('dominant_pattern', 'default')}"
    )

    return {
        "test_conventions": conventions,
        "current_step": "detect_conventions",
        "messages": [AIMessage(content=message)],
    }


async def classify_classes(state: TestGenerationState) -> dict[str, Any]:
    """
    Classify source classes by type (Controller, Service, Repository, etc.).

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from pathlib import Path

    classified = []

    for source in state.source_files:
        file_path = Path(source["path"])
        if not file_path.exists():
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            class_type = _classify_java_class(content, source["name"])

            classified.append({**source, "class_type": class_type})
        except Exception:
            classified.append({**source, "class_type": "utility"})

    # Count by type
    type_counts: dict[str, int] = {}
    for item in classified:
        t = item["class_type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    message = f"Classified {len(classified)} classes: " + ", ".join(
        f"{count} {t}" for t, count in type_counts.items()
    )

    return {
        "classified_classes": classified,
        "current_step": "classify_classes",
        "messages": [AIMessage(content=message)],
    }


async def generate_unit_tests(state: TestGenerationState) -> dict[str, Any]:
    """
    Generate unit tests for classified classes.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from src.mcp_servers.test_generator.tools.generate_unit import generate_adaptive_tests

    generated = []

    # Prioritize by class type
    priority_order = ["service", "controller", "repository", "utility", "model"]
    sorted_classes = sorted(
        state.classified_classes,
        key=lambda x: (
            priority_order.index(x["class_type"]) if x["class_type"] in priority_order else 99
        ),
    )

    for source in sorted_classes[:20]:  # Limit for initial run
        result = await generate_adaptive_tests(
            state.project_path,
            source["path"],
            class_type=source["class_type"],
            conventions=state.test_conventions,
            coverage_target=80,
        )

        test_result = json.loads(result)
        if test_result.get("success"):
            generated.append(test_result)

    message = f"Generated {len(generated)} unit test files"

    return {
        "generated_unit_tests": generated,
        "current_step": "generate_unit_tests",
        "messages": [AIMessage(content=message)],
    }


async def compile_and_fix_unit(state: TestGenerationState) -> dict[str, Any]:
    """
    Compile unit tests and fix errors with retries.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from src.mcp_servers.maven_maintenance.tools.compile import compile_tests

    result = await compile_tests(state.project_path)
    compile_result = json.loads(result)

    if compile_result.get("success"):
        return {
            "compilation_results": compile_result,
            "compilation_retries": 0,
            "current_step": "compile_and_fix_unit",
            "messages": [AIMessage(content="Unit tests compiled successfully")],
        }

    # Compilation failed
    retries = state.compilation_retries + 1

    if retries >= state.max_retries:
        return {
            "compilation_results": compile_result,
            "compilation_retries": retries,
            "warnings": state.warnings + ["Unit test compilation failed after max retries"],
            "current_step": "compile_and_fix_unit",
        }

    return {
        "compilation_results": compile_result,
        "compilation_retries": retries,
        "current_step": "compile_and_fix_unit",
        "messages": [AIMessage(content=f"Compilation failed, retry {retries}/{state.max_retries}")],
    }


async def generate_integration_tests(state: TestGenerationState) -> dict[str, Any]:
    """
    Generate integration tests for services and repositories.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from src.mcp_servers.test_generator.tools.generate_integration import generate_integration_tests

    generated = []

    # Only generate for services and repositories
    targets = [
        c
        for c in state.classified_classes
        if c["class_type"] in ["service", "repository", "controller"]
    ]

    for source in targets[:10]:
        result = await generate_integration_tests(
            state.project_path, source["path"], test_containers=True, mock_external=True
        )

        test_result = json.loads(result)
        if test_result.get("success"):
            generated.append(test_result)

    message = f"Generated {len(generated)} integration test files"

    return {
        "generated_integration_tests": generated,
        "current_step": "generate_integration_tests",
        "messages": [AIMessage(content=message)],
    }


async def compile_and_fix_integration(state: TestGenerationState) -> dict[str, Any]:
    """
    Compile integration tests and fix errors.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from src.mcp_servers.maven_maintenance.tools.compile import compile_tests

    result = await compile_tests(state.project_path)
    compile_result = json.loads(result)

    status = "succeeded" if compile_result.get("success") else "failed"

    return {
        "compilation_results": compile_result,
        "current_step": "compile_and_fix_integration",
        "messages": [AIMessage(content=f"Integration test compilation {status}")],
    }


async def generate_snapshot_tests(state: TestGenerationState) -> dict[str, Any]:
    """
    Generate snapshot tests for API responses.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from src.mcp_servers.test_generator.tools.generate_snapshot import generate_snapshot_tests

    generated = []

    # Only generate for controllers and DTOs
    targets = [c for c in state.classified_classes if c["class_type"] in ["controller", "model"]]

    for source in targets[:5]:
        result = await generate_snapshot_tests(
            state.project_path, source["path"], snapshot_format="json"
        )

        test_result = json.loads(result)
        if test_result.get("success"):
            generated.append(test_result)

    message = f"Generated {len(generated)} snapshot test files"

    return {
        "generated_snapshot_tests": generated,
        "current_step": "generate_snapshot_tests",
        "messages": [AIMessage(content=message)],
    }


async def compile_and_fix_snapshot(state: TestGenerationState) -> dict[str, Any]:
    """
    Compile snapshot tests.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from src.mcp_servers.maven_maintenance.tools.compile import compile_tests

    result = await compile_tests(state.project_path)
    compile_result = json.loads(result)

    status = "succeeded" if compile_result.get("success") else "failed"

    return {
        "compilation_results": compile_result,
        "current_step": "compile_and_fix_snapshot",
        "messages": [AIMessage(content=f"Snapshot test compilation {status}")],
    }


async def deploy_docker(state: TestGenerationState) -> dict[str, Any]:
    """
    Deploy application to Docker for E2E testing.

    Uses the docker MCP tools to deploy the application via docker-compose.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from pathlib import Path

    from src.mcp_servers.docker.tools.compose import create_compose
    from src.mcp_servers.docker.tools.deploy import deploy_compose
    from src.mcp_servers.docker.tools.dockerfile import create_dockerfile

    project_path = Path(state.project_path)
    compose_path = project_path / "docker-compose.yml"
    dockerfile_path = project_path / "Dockerfile"

    try:
        # Generate Dockerfile if not exists
        if not dockerfile_path.exists():
            dockerfile_result = await create_dockerfile(
                project_path=str(project_path),
                java_version="17",
                build_tool="maven",
            )
            dockerfile_data = json.loads(dockerfile_result)
            if not dockerfile_data.get("success"):
                return {
                    "docker_deployed": False,
                    "errors": state.errors + [f"Dockerfile generation failed: {dockerfile_data.get('error', 'Unknown')}"],
                    "current_step": "deploy_docker",
                    "messages": [AIMessage(content="Docker deployment failed - could not create Dockerfile")],
                }

        # Generate docker-compose.yml if not exists
        if not compose_path.exists():
            compose_result = await create_compose(
                project_path=str(project_path),
                service_name=state.project_name or project_path.name,
                port=8080,
                include_database=True,
            )
            compose_data = json.loads(compose_result)
            if not compose_data.get("success"):
                return {
                    "docker_deployed": False,
                    "errors": state.errors + [f"Compose file generation failed: {compose_data.get('error', 'Unknown')}"],
                    "current_step": "deploy_docker",
                    "messages": [AIMessage(content="Docker deployment failed - could not create docker-compose.yml")],
                }

        # Deploy using docker-compose
        deploy_result = await deploy_compose(
            compose_path=str(compose_path),
            project_name=state.project_name or project_path.name,
            build=True,
            detach=True,
        )
        deploy_data = json.loads(deploy_result)

        if deploy_data.get("success"):
            return {
                "docker_deployed": True,
                "current_step": "deploy_docker",
                "messages": [AIMessage(content=f"Docker deployment successful: {len(deploy_data.get('containers', []))} containers")],
            }
        else:
            return {
                "docker_deployed": False,
                "errors": state.errors + [f"Docker deployment failed: {deploy_data.get('error', 'Unknown')}"],
                "current_step": "deploy_docker",
                "messages": [AIMessage(content="Docker deployment failed")],
            }

    except Exception as e:
        return {
            "docker_deployed": False,
            "errors": state.errors + [f"Docker deployment error: {str(e)}"],
            "current_step": "deploy_docker",
            "messages": [AIMessage(content=f"Docker deployment error: {str(e)}")],
        }


async def check_app_health(state: TestGenerationState) -> dict[str, Any]:
    """
    Check application health after Docker deployment.

    Uses the docker health MCP tool to verify container health.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from pathlib import Path

    from src.mcp_servers.docker.tools.health import health_check

    project_path = Path(state.project_path)
    compose_path = project_path / "docker-compose.yml"

    # Skip health check if Docker deployment failed
    if not state.docker_deployed:
        return {
            "app_health": {"status": "skipped", "reason": "Docker not deployed"},
            "current_step": "check_app_health",
            "messages": [AIMessage(content="Health check skipped - Docker not deployed")],
        }

    try:
        # Define health check endpoints (common Spring Boot endpoints)
        health_endpoints = [
            {"url": "http://localhost:8080/actuator/health", "method": "GET", "expected_status": 200},
            {"url": "http://localhost:8080/health", "method": "GET", "expected_status": 200},
        ]

        health_result = await health_check(
            compose_path=str(compose_path),
            project_name=state.project_name or project_path.name,
            timeout=120,
            check_interval=5,
            endpoints=health_endpoints,
        )
        health_data = json.loads(health_result)

        if health_data.get("overall_healthy"):
            health_status = {
                "status": "healthy",
                "containers": health_data.get("containers", []),
                "endpoint_checks": health_data.get("endpoint_checks", []),
                "elapsed_time": health_data.get("elapsed_time", 0),
            }
            message = f"Health check passed in {health_data.get('elapsed_time', 0):.1f}s"
        else:
            health_status = {
                "status": "unhealthy",
                "containers": health_data.get("containers", []),
                "endpoint_checks": health_data.get("endpoint_checks", []),
                "error": health_data.get("error", "Health check failed"),
            }
            message = f"Health check failed: {health_data.get('error', 'Unknown')}"

        return {
            "app_health": health_status,
            "current_step": "check_app_health",
            "messages": [AIMessage(content=message)],
        }

    except Exception as e:
        return {
            "app_health": {"status": "error", "error": str(e)},
            "current_step": "check_app_health",
            "messages": [AIMessage(content=f"Health check error: {str(e)}")],
        }


async def generate_e2e_tests(state: TestGenerationState) -> dict[str, Any]:
    """
    Generate E2E tests based on API endpoints discovered in controllers.

    Analyzes controller classes to extract endpoints and generates
    REST-assured or WebTestClient tests for end-to-end validation.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from pathlib import Path
    import re

    # Skip E2E generation if app is not healthy
    if state.app_health.get("status") not in ["healthy", "skipped"]:
        return {
            "generated_e2e_tests": [],
            "warnings": state.warnings + ["E2E test generation skipped - app not healthy"],
            "current_step": "generate_e2e_tests",
            "messages": [AIMessage(content="E2E test generation skipped - application not healthy")],
        }

    generated_tests = []
    project_path = Path(state.project_path)
    test_dir = project_path / "src" / "test" / "java"

    # Find controller classes
    controllers = [c for c in state.classified_classes if c["class_type"] == "controller"]

    for controller in controllers[:5]:  # Limit to 5 controllers
        try:
            controller_path = Path(controller["path"])
            if not controller_path.exists():
                continue

            content = controller_path.read_text(encoding="utf-8", errors="replace")

            # Extract endpoints from controller
            endpoints = _extract_endpoints_from_controller(content)

            if not endpoints:
                continue

            # Generate E2E test class
            class_name = controller["name"]
            test_class_name = f"{class_name}E2ETest"
            package = controller.get("package", "")

            test_code = _generate_e2e_test_class(
                test_class_name=test_class_name,
                package=package,
                endpoints=endpoints,
                base_url="http://localhost:8080",
            )

            # Determine test file path
            if package:
                package_path = package.replace(".", "/")
                test_file = test_dir / package_path / f"{test_class_name}.java"
            else:
                test_file = test_dir / f"{test_class_name}.java"

            # Write test file
            test_file.parent.mkdir(parents=True, exist_ok=True)
            test_file.write_text(test_code, encoding="utf-8")

            generated_tests.append({
                "class_name": test_class_name,
                "file_path": str(test_file),
                "endpoints_tested": len(endpoints),
                "controller": class_name,
            })

        except Exception as e:
            state.warnings.append(f"E2E generation failed for {controller['name']}: {str(e)}")

    message = f"Generated {len(generated_tests)} E2E test files covering {sum(t['endpoints_tested'] for t in generated_tests)} endpoints"

    return {
        "generated_e2e_tests": generated_tests,
        "current_step": "generate_e2e_tests",
        "messages": [AIMessage(content=message)],
    }


def _extract_endpoints_from_controller(content: str) -> list[dict[str, Any]]:
    """Extract REST endpoints from a Spring controller."""
    import re

    endpoints = []

    # Patterns for Spring MVC annotations
    mapping_patterns = [
        (r'@GetMapping\s*\(\s*["\']([^"\']+)["\']', "GET"),
        (r'@PostMapping\s*\(\s*["\']([^"\']+)["\']', "POST"),
        (r'@PutMapping\s*\(\s*["\']([^"\']+)["\']', "PUT"),
        (r'@DeleteMapping\s*\(\s*["\']([^"\']+)["\']', "DELETE"),
        (r'@PatchMapping\s*\(\s*["\']([^"\']+)["\']', "PATCH"),
        (r'@GetMapping\s*$', "GET"),  # No path = root
        (r'@PostMapping\s*$', "POST"),
    ]

    # Get base path from @RequestMapping
    base_path_match = re.search(r'@RequestMapping\s*\(\s*["\']([^"\']+)["\']', content)
    base_path = base_path_match.group(1) if base_path_match else ""

    for pattern, method in mapping_patterns:
        for match in re.finditer(pattern, content):
            path = match.group(1) if match.lastindex else ""
            full_path = f"{base_path}{path}".replace("//", "/")
            if not full_path:
                full_path = "/"

            endpoints.append({
                "path": full_path,
                "method": method,
                "has_path_variable": "{" in full_path,
            })

    return endpoints


def _generate_e2e_test_class(
    test_class_name: str,
    package: str,
    endpoints: list[dict[str, Any]],
    base_url: str,
) -> str:
    """Generate E2E test class using REST-assured."""
    lines = []

    # Package declaration
    if package:
        lines.append(f"package {package};")
        lines.append("")

    # Imports
    lines.extend([
        "import io.restassured.RestAssured;",
        "import io.restassured.http.ContentType;",
        "import org.junit.jupiter.api.BeforeAll;",
        "import org.junit.jupiter.api.Test;",
        "import static io.restassured.RestAssured.*;",
        "import static org.hamcrest.Matchers.*;",
        "",
    ])

    # Class declaration
    lines.extend([
        "/**",
        " * E2E tests generated by TestBoost.",
        " * Tests real API endpoints against running application.",
        " */",
        f"class {test_class_name} {{",
        "",
        "    @BeforeAll",
        "    static void setup() {",
        f'        RestAssured.baseURI = "{base_url}";',
        "    }",
        "",
    ])

    # Generate test methods for each endpoint
    for i, endpoint in enumerate(endpoints):
        method = endpoint["method"].lower()
        path = endpoint["path"]
        test_name = f"test{method.capitalize()}{_path_to_method_name(path)}"

        # Replace path variables with sample values
        test_path = re.sub(r"\{[^}]+\}", "1", path)

        lines.extend([
            "    @Test",
            f"    void {test_name}() {{",
            f'        {method}("{test_path}")',
            "            .then()",
            "            .statusCode(anyOf(is(200), is(201), is(204), is(401), is(404)));",
            "    }",
            "",
        ])

    lines.append("}")

    return "\n".join(lines)


async def run_mutation_testing(state: TestGenerationState) -> dict[str, Any]:
    """
    Run mutation testing to measure test effectiveness.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from src.mcp_servers.test_generator.tools.mutation import run_mutation_testing

    result = await run_mutation_testing(state.project_path)
    mutation_result = json.loads(result)

    if not mutation_result.get("success"):
        return {
            "warnings": state.warnings + ["Mutation testing failed"],
            "mutation_results": mutation_result,
            "current_step": "run_mutation_testing",
        }

    score = mutation_result.get("mutation_score", 0)
    surviving = mutation_result.get("surviving_mutants", [])

    message = f"Mutation score: {score}% ({len(surviving)} surviving mutants)"

    return {
        "mutation_results": mutation_result,
        "mutation_score": score,
        "surviving_mutants": surviving,
        "current_step": "run_mutation_testing",
        "messages": [AIMessage(content=message)],
    }


async def generate_killer_tests(state: TestGenerationState) -> dict[str, Any]:
    """
    Generate tests to kill surviving mutants if score is below target.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    if state.mutation_score >= state.target_mutation_score:
        return {
            "current_step": "generate_killer_tests",
            "messages": [AIMessage(content="Mutation score meets target, no killer tests needed")],
        }

    from src.mcp_servers.test_generator.tools.killer_tests import generate_killer_tests

    result = await generate_killer_tests(state.project_path, state.surviving_mutants, max_tests=10)

    killer_result = json.loads(result)

    if killer_result.get("success"):
        generated = killer_result.get("generated_tests", [])
        message = f"Generated {len(generated)} killer test files"
    else:
        generated = []
        message = "Killer test generation failed"

    return {
        "killer_tests_generated": generated,
        "current_step": "generate_killer_tests",
        "messages": [AIMessage(content=message)],
    }


async def finalize(state: TestGenerationState) -> dict[str, Any]:
    """
    Finalize workflow and generate quality report.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    # Build quality report
    report = {
        "timestamp": datetime.now().isoformat(),
        "project": state.project_name,
        "summary": {
            "classes_analyzed": len(state.classified_classes),
            "unit_tests_generated": len(state.generated_unit_tests),
            "integration_tests_generated": len(state.generated_integration_tests),
            "snapshot_tests_generated": len(state.generated_snapshot_tests),
            "killer_tests_generated": len(state.killer_tests_generated),
        },
        "mutation_testing": {
            "score": state.mutation_score,
            "target": state.target_mutation_score,
            "meets_target": state.mutation_score >= state.target_mutation_score,
            "surviving_mutants": len(state.surviving_mutants),
        },
        "errors": state.errors,
        "warnings": state.warnings,
    }

    summary = [
        "## Test Generation Complete",
        "",
        f"**Project:** {state.project_name}",
        f"**Mutation Score:** {state.mutation_score}%",
        "",
        "### Generated Tests:",
        f"- Unit tests: {len(state.generated_unit_tests)}",
        f"- Integration tests: {len(state.generated_integration_tests)}",
        f"- Snapshot tests: {len(state.generated_snapshot_tests)}",
        f"- Killer tests: {len(state.killer_tests_generated)}",
        "",
        "### Next Steps:",
        "1. Review generated tests",
        "2. Run test suite",
        "3. Commit passing tests",
    ]

    return {
        "quality_report": report,
        "completed": True,
        "current_step": "finalize",
        "messages": [AIMessage(content="\n".join(summary))],
    }


def should_retry_compilation(state: TestGenerationState) -> Literal["retry", "continue"]:
    """Determine if compilation should be retried."""
    if state.compilation_results.get("success", False):
        return "continue"
    if state.compilation_retries < state.max_retries:
        return "retry"
    return "continue"


def should_generate_killer(state: TestGenerationState) -> Literal["generate", "skip"]:
    """Determine if killer tests should be generated."""
    if state.mutation_score < state.target_mutation_score:
        return "generate"
    return "skip"


def create_test_generation_workflow() -> StateGraph[Any]:
    """
    Create the test generation workflow graph.

    Returns:
        Configured StateGraph for test generation
    """
    workflow = StateGraph(TestGenerationState)

    # Add nodes
    workflow.add_node("analyze_project_structure", analyze_project_structure)
    workflow.add_node("detect_conventions", detect_conventions)
    workflow.add_node("classify_classes", classify_classes)
    workflow.add_node("generate_unit_tests", generate_unit_tests)
    workflow.add_node("compile_and_fix_unit", compile_and_fix_unit)
    workflow.add_node("generate_integration_tests", generate_integration_tests)
    workflow.add_node("compile_and_fix_integration", compile_and_fix_integration)
    workflow.add_node("generate_snapshot_tests", generate_snapshot_tests)
    workflow.add_node("compile_and_fix_snapshot", compile_and_fix_snapshot)
    workflow.add_node("deploy_docker", deploy_docker)
    workflow.add_node("check_app_health", check_app_health)
    workflow.add_node("generate_e2e_tests", generate_e2e_tests)
    workflow.add_node("run_mutation_testing", run_mutation_testing)
    workflow.add_node("generate_killer_tests", generate_killer_tests)
    workflow.add_node("finalize", finalize)

    # Set entry point
    workflow.set_entry_point("analyze_project_structure")

    # Add edges
    workflow.add_edge("analyze_project_structure", "detect_conventions")
    workflow.add_edge("detect_conventions", "classify_classes")
    workflow.add_edge("classify_classes", "generate_unit_tests")
    workflow.add_edge("generate_unit_tests", "compile_and_fix_unit")

    # Conditional edge for compilation retry
    workflow.add_conditional_edges(
        "compile_and_fix_unit",
        should_retry_compilation,
        {"retry": "generate_unit_tests", "continue": "generate_integration_tests"},
    )

    workflow.add_edge("generate_integration_tests", "compile_and_fix_integration")
    workflow.add_edge("compile_and_fix_integration", "generate_snapshot_tests")
    workflow.add_edge("generate_snapshot_tests", "compile_and_fix_snapshot")
    workflow.add_edge("compile_and_fix_snapshot", "deploy_docker")
    workflow.add_edge("deploy_docker", "check_app_health")
    workflow.add_edge("check_app_health", "generate_e2e_tests")
    workflow.add_edge("generate_e2e_tests", "run_mutation_testing")

    # Conditional edge for killer tests
    workflow.add_conditional_edges(
        "run_mutation_testing",
        should_generate_killer,
        {"generate": "generate_killer_tests", "skip": "finalize"},
    )

    workflow.add_edge("generate_killer_tests", "finalize")
    workflow.add_edge("finalize", END)

    return workflow


# Compiled workflow for execution
test_generation_graph = create_test_generation_workflow().compile()


async def run_test_generation(project_path: str, target_mutation_score: float = 80.0) -> dict[str, Any]:
    """
    Run the test generation workflow.

    Args:
        project_path: Path to the Java project
        target_mutation_score: Target mutation score percentage

    Returns:
        Final workflow state
    """
    initial_state = TestGenerationState(
        project_path=project_path, target_mutation_score=target_mutation_score
    )

    final_state = await test_generation_graph.ainvoke(initial_state)  # type: ignore

    return final_state


def _extract_package(file_path: Any) -> str:
    """Extract package from Java file path."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        import re

        match = re.search(r"package\s+([\w.]+);", content)
        return match.group(1) if match else ""
    except Exception:
        return ""


def _classify_java_class(content: str, class_name: str) -> str:
    """Classify a Java class by its type."""
    class_name_lower = class_name.lower()

    # Check annotations
    if "@RestController" in content or "@Controller" in content:
        return "controller"
    elif "@Service" in content:
        return "service"
    elif "@Repository" in content:
        return "repository"
    elif "@Entity" in content or "@Table" in content:
        return "model"

    # Check naming conventions
    if "controller" in class_name_lower:
        return "controller"
    elif "service" in class_name_lower:
        return "service"
    elif "repository" in class_name_lower or "dao" in class_name_lower:
        return "repository"
    elif any(x in class_name_lower for x in ["dto", "model", "entity", "request", "response"]):
        return "model"

    return "utility"


def _path_to_method_name(path: str) -> str:
    """Convert a URL path to a valid Java method name suffix."""
    import re

    # Remove leading/trailing slashes
    clean_path = path.strip("/")

    if not clean_path:
        return "Root"

    # Replace path variables with descriptive names
    clean_path = re.sub(r"\{(\w+)\}", r"By\1", clean_path)

    # Split by / and capitalize each part
    parts = clean_path.split("/")
    method_name = "".join(part.capitalize() for part in parts if part)

    # Remove non-alphanumeric characters
    method_name = re.sub(r"[^a-zA-Z0-9]", "", method_name)

    return method_name or "Path"
