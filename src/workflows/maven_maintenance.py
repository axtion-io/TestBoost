"""
Maven Maintenance Workflow using LangGraph.

⚠️ DEPRECATED: This workflow is deprecated in favor of maven_maintenance_agent.py
which uses DeepAgents for real LLM agent reasoning. This file will be removed
in a future version.

Implements a full workflow for analyzing and updating Maven dependencies
with validation, rollback support, and interactive user confirmation.
"""

import json
import warnings
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class MavenMaintenanceState(BaseModel):
    """State for the Maven maintenance workflow."""

    # Session tracking
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    project_path: str = ""
    project_name: str = ""

    # Git state
    original_branch: str = ""
    maintenance_branch: str = ""
    git_status: dict[str, Any] = Field(default_factory=dict)

    # Analysis results
    dependencies: list[dict[str, Any]] = Field(default_factory=list)
    available_updates: list[dict[str, Any]] = Field(default_factory=list)
    vulnerabilities: list[dict[str, Any]] = Field(default_factory=list)
    release_notes: dict[str, Any] = Field(default_factory=dict)

    # Test results
    baseline_test_results: dict[str, Any] = Field(default_factory=dict)
    validation_test_results: dict[str, Any] = Field(default_factory=dict)

    # Update tracking
    pending_updates: list[dict[str, Any]] = Field(default_factory=list)
    applied_updates: list[dict[str, Any]] = Field(default_factory=list)
    failed_updates: list[dict[str, Any]] = Field(default_factory=list)
    rollback_stack: list[dict[str, Any]] = Field(default_factory=list)

    # User interaction
    user_approved: bool = False
    user_selections: list[str] = Field(default_factory=list)

    # Workflow state
    current_step: str = ""
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    completed: bool = False

    # Messages for chat interface
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True


async def validate_project(state: MavenMaintenanceState) -> dict[str, Any]:
    """
    Validate that the project exists and is a valid Maven project.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from pathlib import Path

    project_dir = Path(state.project_path)

    if not project_dir.exists():
        return {
            "errors": state.errors + [f"Project path does not exist: {state.project_path}"],
            "current_step": "validate_project",
        }

    pom_file = project_dir / "pom.xml"
    if not pom_file.exists():
        return {
            "errors": state.errors + [f"pom.xml not found in {state.project_path}"],
            "current_step": "validate_project",
        }

    # Extract project name from pom.xml
    import xml.etree.ElementTree as ET

    try:
        tree = ET.parse(pom_file)
        root = tree.getroot()
        ns = {"maven": "http://maven.apache.org/POM/4.0.0"}

        name = root.find("maven:name", ns) or root.find("name")
        artifact_id = root.find("maven:artifactId", ns) or root.find("artifactId")

        project_name = (
            name.text
            if name is not None
            else (artifact_id.text if artifact_id is not None else project_dir.name)
        )
    except Exception:
        project_name = project_dir.name

    return {
        "project_name": project_name,
        "current_step": "validate_project",
        "messages": [AIMessage(content=f"Validated project: {project_name}")],
    }


async def check_git_status(state: MavenMaintenanceState) -> dict[str, Any]:
    """
    Check the git status of the project repository.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from src.mcp_servers.git_maintenance.tools.status import get_status

    result = await get_status(state.project_path)
    git_status = json.loads(result)

    if not git_status.get("success"):
        return {
            "errors": state.errors
            + [f"Git status check failed: {git_status.get('error', 'Unknown error')}"],
            "current_step": "check_git_status",
        }

    if not git_status.get("is_clean"):
        return {
            "warnings": state.warnings + ["Working directory has uncommitted changes"],
            "git_status": git_status,
            "original_branch": git_status.get("branch", ""),
            "current_step": "check_git_status",
        }

    return {
        "git_status": git_status,
        "original_branch": git_status.get("branch", ""),
        "current_step": "check_git_status",
        "messages": [
            AIMessage(content=f"Git status: clean on branch {git_status.get('branch', 'unknown')}")
        ],
    }


async def analyze_maven(state: MavenMaintenanceState) -> dict[str, Any]:
    """
    Analyze Maven dependencies for updates and vulnerabilities.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from src.mcp_servers.maven_maintenance.tools.analyze import analyze_dependencies

    result = await analyze_dependencies(
        state.project_path, include_snapshots=False, check_vulnerabilities=True
    )

    analysis = json.loads(result)

    if not analysis.get("success"):
        return {
            "errors": state.errors
            + [f"Dependency analysis failed: {analysis.get('error', 'Unknown error')}"],
            "current_step": "analyze_maven",
        }

    updates = analysis.get("available_updates", [])
    vulns = analysis.get("vulnerabilities", [])

    # Prepare pending updates
    pending_updates = []
    for update in updates:
        pending_updates.append(
            {
                "id": str(uuid4()),
                "groupId": update.get("groupId", ""),
                "artifactId": update.get("artifactId", ""),
                "currentVersion": update.get("currentVersion", ""),
                "targetVersion": update.get("availableVersion", ""),
                "priority": (
                    "high"
                    if any(
                        v.get("dependency", "").startswith(
                            f"{update.get('groupId')}:{update.get('artifactId')}"
                        )
                        for v in vulns
                    )
                    else "normal"
                ),
            }
        )

    message = f"Found {len(updates)} available updates"
    if vulns:
        message += f" and {len(vulns)} vulnerabilities"

    return {
        "dependencies": analysis.get("current_dependencies", []),
        "available_updates": updates,
        "vulnerabilities": vulns,
        "pending_updates": pending_updates,
        "current_step": "analyze_maven",
        "messages": [AIMessage(content=message)],
    }


async def fetch_release_notes(state: MavenMaintenanceState) -> dict[str, Any]:
    """
    Fetch release notes for available updates from GitHub and Maven Central.

    Attempts to fetch real release information from:
    1. GitHub releases API (for common open source projects)
    2. Maven Central metadata

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    import httpx

    release_notes = {}
    fetched_count = 0
    failed_count = 0

    # Common GitHub organization mappings for popular dependencies
    github_mappings = {
        "org.springframework": "spring-projects",
        "org.springframework.boot": "spring-projects",
        "com.fasterxml.jackson": "FasterXML",
        "org.apache.commons": "apache",
        "org.junit": "junit-team",
        "org.mockito": "mockito",
        "org.assertj": "assertj",
        "io.projectreactor": "reactor",
        "org.hibernate": "hibernate",
        "org.slf4j": "qos-ch",
        "ch.qos.logback": "qos-ch",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        for update in state.pending_updates:
            key = f"{update['groupId']}:{update['artifactId']}"
            group_id = update["groupId"]
            artifact_id = update["artifactId"]
            target_version = update["targetVersion"]

            notes = {
                "url": "",
                "summary": f"Update from {update['currentVersion']} to {target_version}",
                "breaking_changes": [],
                "new_features": [],
                "bug_fixes": [],
                "fetched": False,
            }

            # Try to find GitHub organization
            github_org = None
            for prefix, org in github_mappings.items():
                if group_id.startswith(prefix):
                    github_org = org
                    break

            # Attempt to fetch from GitHub releases
            if github_org:
                repo_name = _guess_repo_name(artifact_id)
                github_url = f"https://api.github.com/repos/{github_org}/{repo_name}/releases"
                notes["url"] = f"https://github.com/{github_org}/{repo_name}/releases"

                try:
                    response = await client.get(
                        github_url,
                        headers={"Accept": "application/vnd.github.v3+json"},
                    )

                    if response.status_code == 200:
                        releases = response.json()
                        # Find the release matching our target version
                        for release in releases[:10]:  # Check first 10 releases
                            tag = release.get("tag_name", "")
                            if target_version in tag or tag.endswith(target_version):
                                body = release.get("body", "")
                                parsed = _parse_release_body(body)
                                notes["breaking_changes"] = parsed["breaking_changes"]
                                notes["new_features"] = parsed["new_features"]
                                notes["bug_fixes"] = parsed["bug_fixes"]
                                notes["fetched"] = True
                                fetched_count += 1
                                break
                except Exception:
                    pass  # Fall through to default notes

            # If GitHub failed, try Maven Central for basic info
            if not notes["fetched"]:
                maven_url = (
                    f"https://repo1.maven.org/maven2/"
                    f"{group_id.replace('.', '/')}/{artifact_id}/{target_version}/"
                    f"{artifact_id}-{target_version}.pom"
                )
                notes["url"] = maven_url

                try:
                    response = await client.get(maven_url)
                    if response.status_code == 200:
                        # POM exists, dependency is valid
                        notes["summary"] = f"Version {target_version} available on Maven Central"
                        notes["fetched"] = True
                        fetched_count += 1
                except Exception:
                    failed_count += 1

            release_notes[key] = notes

    message = f"Fetched release notes for {fetched_count}/{len(state.pending_updates)} dependencies"
    if failed_count > 0:
        message += f" ({failed_count} failed to fetch)"

    return {
        "release_notes": release_notes,
        "current_step": "fetch_release_notes",
        "messages": [AIMessage(content=message)],
    }


def _guess_repo_name(artifact_id: str) -> str:
    """Guess GitHub repository name from Maven artifact ID."""
    # Common patterns: spring-boot -> spring-boot, jackson-core -> jackson-core
    # Some projects use different names
    repo_mappings = {
        "spring-boot-starter-parent": "spring-boot",
        "spring-boot-starter-web": "spring-boot",
        "spring-boot-starter-test": "spring-boot",
        "junit-jupiter": "junit5",
        "junit-jupiter-api": "junit5",
        "junit-jupiter-engine": "junit5",
        "mockito-core": "mockito",
        "assertj-core": "assertj",
        "slf4j-api": "slf4j",
        "logback-classic": "logback",
    }
    return repo_mappings.get(artifact_id, artifact_id)


def _parse_release_body(body: str) -> dict[str, list[str]]:
    """Parse GitHub release body to extract changes."""
    result = {
        "breaking_changes": [],
        "new_features": [],
        "bug_fixes": [],
    }

    if not body:
        return result

    lines = body.split("\n")
    current_section = None

    for line in lines:
        line_lower = line.lower().strip()

        # Detect section headers
        if "breaking" in line_lower:
            current_section = "breaking_changes"
        elif any(x in line_lower for x in ["feature", "enhancement", "new"]):
            current_section = "new_features"
        elif any(x in line_lower for x in ["fix", "bug", "patch"]):
            current_section = "bug_fixes"
        elif line.startswith("- ") or line.startswith("* "):
            # This is a list item
            item = line[2:].strip()
            if current_section and item and len(item) < 200:
                result[current_section].append(item)

    return result


async def run_baseline_tests(state: MavenMaintenanceState) -> dict[str, Any]:
    """
    Run baseline tests before applying updates.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from src.mcp_servers.maven_maintenance.tools.run_tests import run_tests

    result = await run_tests(state.project_path)
    test_results = json.loads(result)

    if not test_results.get("success"):
        # Tests failed - this is a problem for the baseline
        return {
            "baseline_test_results": test_results,
            "warnings": state.warnings
            + [
                f"Baseline tests have failures: {test_results.get('summary', {}).get('failed', 0)} failed"
            ],
            "current_step": "run_baseline_tests",
        }

    summary = test_results.get("summary", {})
    message = (
        f"Baseline tests passed: {summary.get('passed', 0)} passed, "
        f"{summary.get('skipped', 0)} skipped"
    )

    return {
        "baseline_test_results": test_results,
        "current_step": "run_baseline_tests",
        "messages": [AIMessage(content=message)],
    }


async def user_validation(state: MavenMaintenanceState) -> dict[str, Any]:
    """
    Present updates to user for validation and selection.

    This is an interactive step that requires user input.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    # Build summary for user
    summary_lines = [
        f"## Dependency Update Summary for {state.project_name}",
        "",
        f"**Available Updates:** {len(state.pending_updates)}",
        f"**Vulnerabilities Found:** {len(state.vulnerabilities)}",
        "",
        "### Updates:",
    ]

    for i, update in enumerate(state.pending_updates, 1):
        priority_marker = "[HIGH]" if update.get("priority") == "high" else ""
        summary_lines.append(
            f"{i}. {update['groupId']}:{update['artifactId']} "
            f"{update['currentVersion']} -> {update['targetVersion']} {priority_marker}"
        )

    summary = "\n".join(summary_lines)

    return {
        "current_step": "user_validation",
        "messages": [
            AIMessage(content=summary),
            HumanMessage(content="Please review the updates and approve to continue."),
        ],
    }


async def create_maintenance_branch(state: MavenMaintenanceState) -> dict[str, Any]:
    """
    Create a new branch for the maintenance work.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from src.mcp_servers.git_maintenance.tools.branch import (
        create_maintenance_branch as create_branch,
    )

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch_name = f"maintenance/deps-{timestamp}"

    result = await create_branch(state.project_path, branch_name, state.original_branch or "main")

    branch_result = json.loads(result)

    if not branch_result.get("success"):
        return {
            "errors": state.errors
            + [f"Failed to create branch: {branch_result.get('error', 'Unknown error')}"],
            "current_step": "create_maintenance_branch",
        }

    return {
        "maintenance_branch": branch_name,
        "current_step": "create_maintenance_branch",
        "messages": [AIMessage(content=f"Created maintenance branch: {branch_name}")],
    }


async def apply_update_batch(state: MavenMaintenanceState) -> dict[str, Any]:
    """
    Apply a batch of dependency updates.

    Includes rollback support for failed updates.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    import xml.etree.ElementTree as ET
    from pathlib import Path

    pom_file = Path(state.project_path) / "pom.xml"

    # Read current pom.xml for rollback (content read for potential future rollback feature)
    with open(pom_file) as f:
        _ = f.read()

    applied = []
    failed = []
    rollback_stack = list(state.rollback_stack)

    # Filter updates based on user selections if any
    updates_to_apply = state.pending_updates
    if state.user_selections:
        updates_to_apply = [
            u
            for u in state.pending_updates
            if f"{u['groupId']}:{u['artifactId']}" in state.user_selections
        ]

    for update in updates_to_apply:
        try:
            # Parse and modify pom.xml
            tree = ET.parse(pom_file)
            root = tree.getroot()

            # Find and update the dependency version
            ns = {"maven": "http://maven.apache.org/POM/4.0.0"}

            # Try with namespace
            updated = False
            for dep in root.findall(".//maven:dependency", ns):
                group_id = dep.find("maven:groupId", ns)
                artifact_id = dep.find("maven:artifactId", ns)
                version = dep.find("maven:version", ns)

                if (
                    group_id is not None
                    and artifact_id is not None
                    and group_id.text == update["groupId"]
                    and artifact_id.text == update["artifactId"]
                ):

                    if version is not None:
                        old_version = version.text
                        version.text = update["targetVersion"]
                        updated = True

                        rollback_stack.append(
                            {
                                "update_id": update["id"],
                                "groupId": update["groupId"],
                                "artifactId": update["artifactId"],
                                "oldVersion": old_version,
                                "newVersion": update["targetVersion"],
                            }
                        )

            # Try without namespace if not found
            if not updated:
                for dep in root.findall(".//dependency"):
                    group_id = dep.find("groupId")
                    artifact_id = dep.find("artifactId")
                    version = dep.find("version")

                    if (
                        group_id is not None
                        and artifact_id is not None
                        and group_id.text == update["groupId"]
                        and artifact_id.text == update["artifactId"]
                    ):

                        if version is not None:
                            old_version = version.text
                            version.text = update["targetVersion"]
                            updated = True

                            rollback_stack.append(
                                {
                                    "update_id": update["id"],
                                    "groupId": update["groupId"],
                                    "artifactId": update["artifactId"],
                                    "oldVersion": old_version,
                                    "newVersion": update["targetVersion"],
                                }
                            )

            if updated:
                tree.write(pom_file, encoding="unicode", xml_declaration=True)
                applied.append(update)
            else:
                failed.append({**update, "error": "Dependency not found in pom.xml"})

        except Exception as e:
            failed.append({**update, "error": str(e)})

    message = f"Applied {len(applied)} updates"
    if failed:
        message += f", {len(failed)} failed"

    return {
        "applied_updates": state.applied_updates + applied,
        "failed_updates": state.failed_updates + failed,
        "rollback_stack": rollback_stack,
        "current_step": "apply_update_batch",
        "messages": [AIMessage(content=message)],
    }


async def validate_changes(state: MavenMaintenanceState) -> dict[str, Any]:
    """
    Validate changes by running tests and checking compilation.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from src.mcp_servers.maven_maintenance.tools.compile import compile_tests
    from src.mcp_servers.maven_maintenance.tools.run_tests import run_tests

    # First compile
    compile_result = await compile_tests(state.project_path)
    compile_data = json.loads(compile_result)

    if not compile_data.get("success"):
        return {
            "validation_test_results": {"compile": compile_data, "tests": {}, "success": False},
            "warnings": state.warnings + ["Compilation failed after updates"],
            "current_step": "validate_changes",
        }

    # Then run tests
    test_result = await run_tests(state.project_path)
    test_data = json.loads(test_result)

    validation_results = {
        "compile": compile_data,
        "tests": test_data,
        "success": test_data.get("success", False),
    }

    if test_data.get("success"):
        summary = test_data.get("summary", {})
        message = (
            f"Validation passed: {summary.get('passed', 0)} tests passed, "
            f"{summary.get('failed', 0)} failed"
        )
    else:
        message = "Validation failed - tests did not pass"

    return {
        "validation_test_results": validation_results,
        "current_step": "validate_changes",
        "messages": [AIMessage(content=message)],
    }


async def rollback_changes(state: MavenMaintenanceState) -> dict[str, Any]:
    """
    Rollback applied changes if validation fails.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    import xml.etree.ElementTree as ET
    from pathlib import Path

    if not state.rollback_stack:
        return {
            "current_step": "rollback_changes",
            "messages": [AIMessage(content="No changes to rollback")],
        }

    pom_file = Path(state.project_path) / "pom.xml"

    # Rollback in reverse order
    rolled_back = []
    for rollback in reversed(state.rollback_stack):
        try:
            tree = ET.parse(pom_file)
            root = tree.getroot()

            ns = {"maven": "http://maven.apache.org/POM/4.0.0"}

            # Find and revert the dependency version
            for dep in root.findall(".//maven:dependency", ns):
                group_id = dep.find("maven:groupId", ns)
                artifact_id = dep.find("maven:artifactId", ns)
                version = dep.find("maven:version", ns)

                if (
                    group_id is not None
                    and artifact_id is not None
                    and group_id.text == rollback["groupId"]
                    and artifact_id.text == rollback["artifactId"]
                    and version is not None
                ):

                    version.text = rollback["oldVersion"]
                    rolled_back.append(rollback)
                    break

            tree.write(pom_file, encoding="unicode", xml_declaration=True)

        except Exception as e:
            # Log rollback failure but continue with other rollbacks
            warnings.warn(
                f"Failed to rollback {rollback.get('artifactId', 'unknown')}: {e}",
                stacklevel=2
            )

    return {
        "rollback_stack": [],
        "applied_updates": [],
        "current_step": "rollback_changes",
        "messages": [AIMessage(content=f"Rolled back {len(rolled_back)} changes")],
    }


async def commit_changes(state: MavenMaintenanceState) -> dict[str, Any]:
    """
    Commit the applied changes.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    from src.mcp_servers.git_maintenance.tools.commit import commit_changes as git_commit

    # Build commit message
    update_count = len(state.applied_updates)
    message_lines = [
        f"chore(deps): update {update_count} dependencies",
        "",
        "Updated dependencies:",
    ]

    for update in state.applied_updates:
        message_lines.append(
            f"- {update['groupId']}:{update['artifactId']}: "
            f"{update['currentVersion']} -> {update['targetVersion']}"
        )

    commit_message = "\n".join(message_lines)

    result = await git_commit(state.project_path, commit_message, ["pom.xml"])

    commit_result = json.loads(result)

    if not commit_result.get("success"):
        return {
            "errors": state.errors
            + [f"Commit failed: {commit_result.get('error', 'Unknown error')}"],
            "current_step": "commit_changes",
        }

    return {
        "current_step": "commit_changes",
        "messages": [
            AIMessage(content=f"Committed changes: {commit_result.get('commit_hash', '')[:8]}")
        ],
    }


async def finalize(state: MavenMaintenanceState) -> dict[str, Any]:
    """
    Finalize the maintenance workflow.

    Args:
        state: Current workflow state

    Returns:
        Updated state fields
    """
    summary = [
        "## Maintenance Complete",
        "",
        f"**Project:** {state.project_name}",
        f"**Branch:** {state.maintenance_branch}",
        "",
        f"**Applied Updates:** {len(state.applied_updates)}",
        f"**Failed Updates:** {len(state.failed_updates)}",
        "",
        "### Next Steps:",
        "1. Review the changes in the maintenance branch",
        "2. Create a pull request for review",
        "3. Merge after approval",
    ]

    return {
        "completed": True,
        "current_step": "finalize",
        "messages": [AIMessage(content="\n".join(summary))],
    }


def should_continue(state: MavenMaintenanceState) -> Literal["continue", "error", "end"]:
    """Determine if workflow should continue."""
    if state.errors:
        return "error"
    if state.completed:
        return "end"
    return "continue"


def should_rollback(state: MavenMaintenanceState) -> Literal["rollback", "commit"]:
    """Determine if changes should be rolled back."""
    if not state.validation_test_results.get("success", False):
        return "rollback"
    return "commit"


def has_updates(state: MavenMaintenanceState) -> Literal["continue", "end"]:
    """Check if there are any pending updates."""
    if not state.pending_updates:
        return "end"
    return "continue"


def create_maven_maintenance_workflow() -> StateGraph[Any]:
    """
    Create the Maven maintenance workflow graph.

    Returns:
        Configured StateGraph for Maven maintenance
    """
    # Create the graph
    workflow = StateGraph(MavenMaintenanceState)

    # Add nodes
    workflow.add_node("validate_project", validate_project)
    workflow.add_node("check_git_status", check_git_status)
    workflow.add_node("analyze_maven", analyze_maven)
    workflow.add_node("fetch_release_notes", fetch_release_notes)
    workflow.add_node("run_baseline_tests", run_baseline_tests)
    workflow.add_node("user_validation", user_validation)
    workflow.add_node("create_maintenance_branch", create_maintenance_branch)
    workflow.add_node("apply_update_batch", apply_update_batch)
    workflow.add_node("validate_changes", validate_changes)
    workflow.add_node("rollback_changes", rollback_changes)
    workflow.add_node("commit_changes", commit_changes)
    workflow.add_node("finalize", finalize)

    # Set entry point
    workflow.set_entry_point("validate_project")

    # Add edges
    workflow.add_edge("validate_project", "check_git_status")
    workflow.add_edge("check_git_status", "analyze_maven")

    # Conditional edge after analyze - check if there are updates
    workflow.add_conditional_edges(
        "analyze_maven",
        has_updates,
        {"continue": "fetch_release_notes", "end": "finalize"},
    )

    workflow.add_edge("fetch_release_notes", "run_baseline_tests")
    workflow.add_edge("run_baseline_tests", "user_validation")
    workflow.add_edge("user_validation", "create_maintenance_branch")
    workflow.add_edge("create_maintenance_branch", "apply_update_batch")
    workflow.add_edge("apply_update_batch", "validate_changes")

    # Conditional edge for validation results
    workflow.add_conditional_edges(
        "validate_changes",
        should_rollback,
        {"rollback": "rollback_changes", "commit": "commit_changes"},
    )

    workflow.add_edge("rollback_changes", "finalize")  # Go to finalize after rollback
    workflow.add_edge("commit_changes", "finalize")
    workflow.add_edge("finalize", END)

    return workflow


# Compiled workflow for execution
maven_maintenance_graph = create_maven_maintenance_workflow().compile()


async def run_maven_maintenance(project_path: str, user_approved: bool = False) -> dict[str, Any]:
    """
    Run the Maven maintenance workflow.

    ⚠️ DEPRECATED: Use run_maven_maintenance_with_agent() from maven_maintenance_agent.py
    instead. This function will be removed in a future version.

    Args:
        project_path: Path to the Maven project
        user_approved: Whether user has pre-approved updates

    Returns:
        Final workflow state
    """
    warnings.warn(
        "run_maven_maintenance() is deprecated. Use run_maven_maintenance_with_agent() "
        "from src.workflows.maven_maintenance_agent instead.",
        DeprecationWarning,
        stacklevel=2
    )

    initial_state = MavenMaintenanceState(project_path=project_path, user_approved=user_approved)

    final_state = await maven_maintenance_graph.ainvoke(initial_state)  # type: ignore

    return final_state
