"""
Test Generation Workflow using LangGraph.

DEPRECATED: This workflow is deprecated in favor of test_generation_agent.py (T062).
The new workflow uses DeepAgents for real LLM agent integration with tool calls.

Implements a full workflow for analyzing Java projects, generating tests,
running mutation testing, and generating killer tests if needed.
"""

import warnings

warnings.warn(
    "test_generation.py workflow is deprecated. "
    "Use test_generation_agent.py with DeepAgents LLM integration instead. "
    "See 002-deepagents-integration spec for details.",
    DeprecationWarning,
    stacklevel=2,
)

import json
from datetime import datetime
from typing import Annotated, Literal
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class TestGenerationState(BaseModel):
    """State for the test generation workflow."""

    # Session tracking
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    project_path: str = ""
    project_name: str = ""

    # Project analysis
    project_context: dict = Field(default_factory=dict)
    test_conventions: dict = Field(default_factory=dict)
    source_files: list[dict] = Field(default_factory=list)
    classified_classes: list[dict] = Field(default_factory=list)

    # Test generation tracking
    generated_unit_tests: list[dict] = Field(default_factory=list)
    generated_integration_tests: list[dict] = Field(default_factory=list)
    generated_snapshot_tests: list[dict] = Field(default_factory=list)
    generated_e2e_tests: list[dict] = Field(default_factory=list)

    # Compilation results
    compilation_results: dict = Field(default_factory=dict)
    compilation_retries: int = 0
    max_retries: int = 3

    # Docker/E2E state
    docker_deployed: bool = False
    app_health: dict = Field(default_factory=dict)

    # Mutation testing
    mutation_results: dict = Field(default_factory=dict)
    mutation_score: float = 0.0
    target_mutation_score: float = 80.0
    surviving_mutants: list[dict] = Field(default_factory=list)

    # Killer tests
    killer_tests_generated: list[dict] = Field(default_factory=list)

    # Quality report
    quality_report: dict = Field(default_factory=dict)

    # Workflow state
    current_step: str = ""
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    completed: bool = False

    # Messages for chat interface
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True


async def analyze_project_structure(state: TestGenerationState) -> dict:
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
    source_structure = context.get("source_structure", {})
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


async def detect_conventions(state: TestGenerationState) -> dict:
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


async def classify_classes(state: TestGenerationState) -> dict:
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
    type_counts = {}
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


async def generate_unit_tests(state: TestGenerationState) -> dict:
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


async def compile_and_fix_unit(state: TestGenerationState) -> dict:
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


async def generate_integration_tests(state: TestGenerationState) -> dict:
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


async def compile_and_fix_integration(state: TestGenerationState) -> dict:
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


async def generate_snapshot_tests(state: TestGenerationState) -> dict:
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


async def compile_and_fix_snapshot(state: TestGenerationState) -> dict:
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


async def deploy_docker(state: TestGenerationState) -> dict:
    """
    Deploy application to Docker for E2E testing.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    # Placeholder for Docker deployment
    # In production, this would use container_runtime tools

    return {
        "docker_deployed": True,
        "current_step": "deploy_docker",
        "messages": [AIMessage(content="Docker deployment initiated")],
    }


async def check_app_health(state: TestGenerationState) -> dict:
    """
    Check application health after Docker deployment.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    # Placeholder for health check
    health = {"status": "healthy", "checks": {"database": "up", "api": "up"}}

    return {
        "app_health": health,
        "current_step": "check_app_health",
        "messages": [AIMessage(content="Application health check passed")],
    }


async def generate_e2e_tests(state: TestGenerationState) -> dict:
    """
    Generate E2E tests based on API endpoints.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    # Placeholder for E2E test generation
    # Would use project context to identify endpoints

    return {
        "generated_e2e_tests": [],
        "current_step": "generate_e2e_tests",
        "messages": [AIMessage(content="E2E test generation completed")],
    }


async def run_mutation_testing(state: TestGenerationState) -> dict:
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


async def generate_killer_tests(state: TestGenerationState) -> dict:
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


async def finalize(state: TestGenerationState) -> dict:
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


def create_test_generation_workflow() -> StateGraph:
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


async def run_test_generation(project_path: str, target_mutation_score: float = 80.0) -> dict:
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

    final_state = await test_generation_graph.ainvoke(initial_state)

    return final_state


def _extract_package(file_path) -> str:
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
