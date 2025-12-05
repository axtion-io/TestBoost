"""
Docker Deployment Workflow using LangGraph.

Implements a full workflow for deploying Java applications with Docker,
including project analysis, Dockerfile generation, container deployment,
health checking, and endpoint validation.
"""

import json
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class DockerDeploymentState(BaseModel):
    """State for the Docker deployment workflow."""

    # Session tracking
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    project_path: str = ""
    project_name: str = ""

    # Project analysis
    java_version: str = ""
    artifact_type: str = ""  # jar or war
    is_spring_boot: bool = False
    build_tool: str = ""  # maven or gradle

    # Docker configuration
    dockerfile_path: str = ""
    compose_path: str = ""
    image_name: str = ""
    container_name: str = ""

    # Dependencies
    detected_dependencies: list[str] = Field(default_factory=list)
    service_dependencies: list[str] = Field(default_factory=list)

    # Deployment state
    containers: list[dict[str, Any]] = Field(default_factory=list)
    build_logs: str = ""
    deploy_logs: str = ""

    # Health status
    health_status: dict[str, Any] = Field(default_factory=dict)
    endpoint_results: list[dict[str, Any]] = Field(default_factory=list)

    # Validation endpoints
    health_endpoints: list[dict[str, Any]] = Field(default_factory=list)

    # Workflow state
    current_step: str = ""
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    completed: bool = False

    # Final report
    deployment_report: dict[str, Any] = Field(default_factory=dict)

    # Messages for chat interface
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True


async def analyze_project(state: DockerDeploymentState) -> dict[str, Any]:
    """
    Analyze the Java project to detect JAR/WAR, Java version, and build tool.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    import xml.etree.ElementTree as ET
    from pathlib import Path

    project_dir = Path(state.project_path)

    if not project_dir.exists():
        return {
            "errors": state.errors + [f"Project path does not exist: {state.project_path}"],
            "current_step": "analyze_project",
        }

    # Initialize detection values
    java_version = "17"
    artifact_type = "jar"
    build_tool = ""
    is_spring_boot = False
    project_name = project_dir.name
    detected_deps: list[str] = []

    # Check for pom.xml (Maven)
    pom_file = project_dir / "pom.xml"
    if pom_file.exists():
        build_tool = "maven"

        try:
            tree = ET.parse(pom_file)
            root = tree.getroot()
            ns = {"maven": "http://maven.apache.org/POM/4.0.0"}

            # Detect Java version
            for prop_path in [
                ".//maven:properties/maven:java.version",
                ".//maven:properties/maven:maven.compiler.source",
                ".//properties/java.version",
                ".//properties/maven.compiler.source",
            ]:
                prop = root.find(prop_path, ns)
                if prop is not None and prop.text:
                    java_version = prop.text.strip()
                    break

            # Detect artifact ID for project name
            artifact_id = root.find("maven:artifactId", ns) or root.find("artifactId")
            if artifact_id is not None and artifact_id.text:
                project_name = artifact_id.text

            # Detect packaging type
            packaging = root.find("maven:packaging", ns) or root.find("packaging")
            if packaging is not None and packaging.text:
                artifact_type = packaging.text.lower()

            # Analyze dependencies
            for dep in root.findall(".//maven:dependency", ns) + root.findall(".//dependency"):
                group_id_elem = dep.find("maven:groupId", ns) or dep.find("groupId")
                artifact_id_elem = dep.find("maven:artifactId", ns) or dep.find("artifactId")

                if group_id_elem is not None and group_id_elem.text:
                    group_id = group_id_elem.text

                    # Check for Spring Boot
                    if "spring-boot" in group_id:
                        is_spring_boot = True

                    # Detect database dependencies
                    if artifact_id_elem is not None and artifact_id_elem.text:
                        artifact = artifact_id_elem.text.lower()

                        if "postgresql" in artifact or "postgres" in group_id:
                            if "postgres" not in detected_deps:
                                detected_deps.append("postgres")
                        elif "mysql" in artifact:
                            if "mysql" not in detected_deps:
                                detected_deps.append("mysql")
                        elif "mongodb" in artifact or "mongo" in artifact:
                            if "mongodb" not in detected_deps:
                                detected_deps.append("mongodb")
                        elif "redis" in artifact:
                            if "redis" not in detected_deps:
                                detected_deps.append("redis")
                        elif "rabbitmq" in artifact or "amqp" in artifact:
                            if "rabbitmq" not in detected_deps:
                                detected_deps.append("rabbitmq")
                        elif "kafka" in artifact:
                            if "kafka" not in detected_deps:
                                detected_deps.append("kafka")

        except ET.ParseError as e:
            return {
                "errors": state.errors + [f"Failed to parse pom.xml: {e}"],
                "current_step": "analyze_project",
            }

    # Check for build.gradle (Gradle)
    gradle_file = project_dir / "build.gradle"
    if gradle_file.exists():
        build_tool = "gradle"

        try:
            with open(gradle_file) as f:
                content = f.read()

            # Simple detection of Java version
            import re

            match = re.search(r"sourceCompatibility\s*=\s*['\"]?(\d+)['\"]?", content)
            if match:
                java_version = match.group(1)

            # Check for Spring Boot plugin
            if "org.springframework.boot" in content:
                is_spring_boot = True

        except Exception as e:
            return {
                "warnings": state.warnings + [f"Error reading build.gradle: {e}"],
                "current_step": "analyze_project",
            }

    if not build_tool:
        return {
            "errors": state.errors + ["No pom.xml or build.gradle found"],
            "current_step": "analyze_project",
        }

    message = (
        f"Project Analysis Complete:\n"
        f"- Name: {project_name}\n"
        f"- Build Tool: {build_tool}\n"
        f"- Java Version: {java_version}\n"
        f"- Artifact Type: {artifact_type}\n"
        f"- Spring Boot: {is_spring_boot}\n"
        f"- Detected Dependencies: {', '.join(detected_deps) if detected_deps else 'None'}"
    )

    return {
        "project_name": project_name,
        "java_version": java_version,
        "artifact_type": artifact_type,
        "build_tool": build_tool,
        "is_spring_boot": is_spring_boot,
        "detected_dependencies": detected_deps,
        "current_step": "analyze_project",
        "messages": [AIMessage(content=message)],
    }


async def generate_dockerfile(state: DockerDeploymentState) -> dict[str, Any]:
    """
    Generate a Dockerfile for the project.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from src.mcp_servers.docker.tools.dockerfile import create_dockerfile

    result = await create_dockerfile(state.project_path, java_version=state.java_version)

    dockerfile_result = json.loads(result)

    if not dockerfile_result.get("success"):
        return {
            "errors": state.errors
            + [f"Dockerfile generation failed: {dockerfile_result.get('error', 'Unknown error')}"],
            "current_step": "generate_dockerfile",
        }

    return {
        "dockerfile_path": dockerfile_result.get("dockerfile_path", ""),
        "current_step": "generate_dockerfile",
        "messages": [
            AIMessage(
                content=f"Generated Dockerfile at {dockerfile_result.get('dockerfile_path', '')}"
            )
        ],
    }


async def generate_docker_compose(state: DockerDeploymentState) -> dict[str, Any]:
    """
    Generate docker-compose.yml with detected dependencies.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from src.mcp_servers.docker.tools.compose import create_compose

    # Use detected dependencies or provided service dependencies
    dependencies = (
        state.service_dependencies if state.service_dependencies else state.detected_dependencies
    )

    result = await create_compose(
        state.project_path, service_name=state.project_name or "app", dependencies=dependencies
    )

    compose_result = json.loads(result)

    if not compose_result.get("success"):
        return {
            "errors": state.errors
            + [f"docker-compose generation failed: {compose_result.get('error', 'Unknown error')}"],
            "current_step": "generate_docker_compose",
        }

    services = compose_result.get("services", [])
    message = f"Generated docker-compose.yml with services: {', '.join(services)}"

    return {
        "compose_path": compose_result.get("compose_path", ""),
        "current_step": "generate_docker_compose",
        "messages": [AIMessage(content=message)],
    }


async def build_image(state: DockerDeploymentState) -> dict[str, Any]:
    """
    Build the Docker image.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from src.mcp_servers.docker.tools.deploy import deploy_compose

    # First, just build the images
    result = await deploy_compose(
        state.compose_path, project_name=state.project_name, build=True, detach=False
    )

    build_result = json.loads(result)

    # Even if deployment fails here, we want to capture build logs
    build_logs = build_result.get("build_output", "")

    if "error" in build_result and "build failed" in build_result.get("error", "").lower():
        return {
            "build_logs": build_logs,
            "errors": state.errors
            + [f"Docker build failed: {build_result.get('error', 'Unknown error')}"],
            "current_step": "build_image",
        }

    return {
        "build_logs": build_logs,
        "image_name": f"{state.project_name}:latest",
        "current_step": "build_image",
        "messages": [AIMessage(content="Docker image built successfully")],
    }


async def run_container(state: DockerDeploymentState) -> dict[str, Any]:
    """
    Deploy and run the containers.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from src.mcp_servers.docker.tools.deploy import deploy_compose

    result = await deploy_compose(
        state.compose_path,
        project_name=state.project_name,
        build=False,  # Already built
        detach=True,
    )

    deploy_result = json.loads(result)

    if not deploy_result.get("success"):
        return {
            "deploy_logs": deploy_result.get("deploy_output", ""),
            "errors": state.errors
            + [f"Container deployment failed: {deploy_result.get('error', 'Unknown error')}"],
            "current_step": "run_container",
        }

    containers = deploy_result.get("containers", [])
    container_names = [c.get("name", "") for c in containers]

    return {
        "containers": containers,
        "deploy_logs": deploy_result.get("deploy_output", ""),
        "container_name": container_names[0] if container_names else "",
        "current_step": "run_container",
        "messages": [
            AIMessage(
                content=f"Deployed {len(containers)} container(s): {', '.join(container_names)}"
            )
        ],
    }


async def check_health(state: DockerDeploymentState) -> dict[str, Any]:
    """
    Check container health with wait logic.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from src.mcp_servers.docker.tools.health import health_check

    # Build default health endpoints for Spring Boot
    endpoints = state.health_endpoints
    if not endpoints and state.is_spring_boot:
        endpoints = [
            {
                "url": "http://localhost:8080/actuator/health",
                "method": "GET",
                "expected_status": 200,
            }
        ]

    result = await health_check(
        state.compose_path,
        project_name=state.project_name,
        timeout=120,
        check_interval=5,
        endpoints=endpoints,
    )

    health_result = json.loads(result)

    health_status = {
        "containers": health_result.get("containers", []),
        "overall_healthy": health_result.get("overall_healthy", False),
        "elapsed_time": health_result.get("elapsed_time", 0),
    }

    if health_result.get("warning"):
        return {
            "health_status": health_status,
            "warnings": state.warnings + [health_result.get("warning", "")],
            "current_step": "check_health",
        }

    if health_result.get("success"):
        message = f"Health check passed in {health_result.get('elapsed_time', 0)}s"
    else:
        message = "Health check completed with issues"

    return {
        "health_status": health_status,
        "current_step": "check_health",
        "messages": [AIMessage(content=message)],
    }


async def validate_endpoints(state: DockerDeploymentState) -> dict[str, Any]:
    """
    Validate specific application endpoints.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    import httpx

    if not state.health_endpoints:
        # No custom endpoints to validate
        return {
            "endpoint_results": [],
            "current_step": "validate_endpoints",
            "messages": [AIMessage(content="No custom endpoints to validate")],
        }

    results = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for endpoint in state.health_endpoints:
            url = endpoint.get("url", "")
            method = endpoint.get("method", "GET")
            expected_status = endpoint.get("expected_status", 200)

            result = {
                "url": url,
                "method": method,
                "expected_status": expected_status,
                "passed": False,
                "actual_status": None,
                "error": None,
            }

            try:
                response = await client.request(method, url)
                result["actual_status"] = response.status_code
                result["passed"] = response.status_code == expected_status

            except httpx.ConnectError as e:
                result["error"] = f"Connection failed: {str(e)}"
            except httpx.TimeoutException:
                result["error"] = "Request timed out"
            except Exception as e:
                result["error"] = str(e)

            results.append(result)

    passed_count = sum(1 for r in results if r["passed"])
    message = f"Endpoint validation: {passed_count}/{len(results)} passed"

    return {
        "endpoint_results": results,
        "current_step": "validate_endpoints",
        "messages": [AIMessage(content=message)],
    }


async def finalize(state: DockerDeploymentState) -> dict[str, Any]:
    """
    Finalize deployment and generate report.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    # Determine overall success
    is_healthy = state.health_status.get("overall_healthy", False)
    endpoint_pass_rate = (
        sum(1 for r in state.endpoint_results if r.get("passed", False))
        / len(state.endpoint_results)
        if state.endpoint_results
        else 1.0
    )

    success = is_healthy and endpoint_pass_rate >= 0.8 and len(state.errors) == 0

    # Build deployment report
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "project": state.project_name,
        "project_path": state.project_path,
        "success": success,
        "configuration": {
            "java_version": state.java_version,
            "artifact_type": state.artifact_type,
            "build_tool": state.build_tool,
            "is_spring_boot": state.is_spring_boot,
        },
        "artifacts": {
            "dockerfile": state.dockerfile_path,
            "compose_file": state.compose_path,
            "image": state.image_name,
        },
        "containers": state.containers,
        "health": {
            "overall_healthy": is_healthy,
            "container_status": state.health_status.get("containers", []),
            "check_duration": state.health_status.get("elapsed_time", 0),
        },
        "endpoint_validation": {
            "total": len(state.endpoint_results),
            "passed": sum(1 for r in state.endpoint_results if r.get("passed", False)),
            "results": state.endpoint_results,
        },
        "errors": state.errors,
        "warnings": state.warnings,
    }

    # Generate summary message
    summary_lines = [
        "## Deployment Complete",
        "",
        f"**Project:** {state.project_name}",
        f"**Status:** {'Success' if success else 'Failed'}",
        "",
        "### Configuration",
        f"- Java Version: {state.java_version}",
        f"- Build Tool: {state.build_tool}",
        f"- Artifact Type: {state.artifact_type}",
        "",
        "### Containers",
    ]

    for container in state.containers:
        summary_lines.append(
            f"- {container.get('name', 'unknown')}: {container.get('state', 'unknown')}"
        )

    if state.errors:
        summary_lines.extend(["", "### Errors"])
        for error in state.errors:
            summary_lines.append(f"- {error}")

    if state.warnings:
        summary_lines.extend(["", "### Warnings"])
        for warning in state.warnings:
            summary_lines.append(f"- {warning}")

    summary_lines.extend(
        [
            "",
            "### Next Steps",
            "1. Access application at http://localhost:8080",
            f"2. View logs: docker compose -f {state.compose_path} logs",
            f"3. Stop deployment: docker compose -f {state.compose_path} down",
        ]
    )

    return {
        "deployment_report": report,
        "completed": True,
        "current_step": "finalize",
        "messages": [AIMessage(content="\n".join(summary_lines))],
    }


def should_continue(state: DockerDeploymentState) -> Literal["continue", "error", "end"]:
    """Determine if workflow should continue."""
    if state.errors:
        return "error"
    if state.completed:
        return "end"
    return "continue"


def create_docker_deployment_workflow() -> StateGraph[Any]:
    """
    Create the Docker deployment workflow graph.

    Returns:
        Configured StateGraph for Docker deployment
    """
    # Create the graph
    workflow = StateGraph(DockerDeploymentState)

    # Add nodes
    workflow.add_node("analyze_project", analyze_project)
    workflow.add_node("generate_dockerfile", generate_dockerfile)
    workflow.add_node("generate_docker_compose", generate_docker_compose)
    workflow.add_node("build_image", build_image)
    workflow.add_node("run_container", run_container)
    workflow.add_node("check_health", check_health)
    workflow.add_node("validate_endpoints", validate_endpoints)
    workflow.add_node("finalize", finalize)

    # Set entry point
    workflow.set_entry_point("analyze_project")

    # Add edges
    workflow.add_edge("analyze_project", "generate_dockerfile")
    workflow.add_edge("generate_dockerfile", "generate_docker_compose")
    workflow.add_edge("generate_docker_compose", "build_image")
    workflow.add_edge("build_image", "run_container")
    workflow.add_edge("run_container", "check_health")
    workflow.add_edge("check_health", "validate_endpoints")
    workflow.add_edge("validate_endpoints", "finalize")
    workflow.add_edge("finalize", END)

    return workflow


# Compiled workflow for execution
docker_deployment_graph = create_docker_deployment_workflow().compile()


async def run_docker_deployment(
    project_path: str,
    service_dependencies: list[str] | None = None,
    health_endpoints: list[dict[str, Any]] | None = None,
) -> DockerDeploymentState:
    """
    Run the Docker deployment workflow.

    Args:
        project_path: Path to the Java project
        service_dependencies: Override detected dependencies
        health_endpoints: Custom endpoints to validate

    Returns:
        Final workflow state
    """
    initial_state = DockerDeploymentState(
        project_path=project_path,
        service_dependencies=service_dependencies or [],
        health_endpoints=health_endpoints or [],
    )

    final_state = await docker_deployment_graph.ainvoke(initial_state)  # type: ignore[arg-type]

    return final_state
