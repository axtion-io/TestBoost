"""Base workflow state definitions."""

import uuid
from typing import Any, TypedDict

from src.db.models.session import SessionMode
from src.lib.logging import get_logger

logger = get_logger(__name__)


class WorkflowState(TypedDict, total=False):
    """Base workflow state for LangGraph StateGraph.

    This TypedDict defines the shared state structure used by all
    TestBoost workflows. It provides the common fields needed for
    session tracking, execution control, and step management.
    """

    # Session identification
    session_id: uuid.UUID
    project_path: str
    mode: str  # SessionMode value

    # Execution state
    current_step: str
    previous_step: str | None
    step_sequence: int

    # Workflow control
    should_pause: bool
    is_paused: bool
    checkpoint_id: str | None
    pause_reason: str | None

    # Data passing between nodes
    input_data: dict[str, Any]
    output_data: dict[str, Any]

    # Error handling
    error: str | None
    error_step: str | None

    # Approval workflow (for interactive mode)
    pending_approval: bool
    approval_request: dict[str, Any] | None
    approval_response: dict[str, Any] | None

    # Results accumulation
    results: list[dict[str, Any]]
    artifacts: list[dict[str, Any]]

    # Debug mode tracking
    debug_logs: list[dict[str, Any]]


class MavenMaintenanceState(WorkflowState, total=False):
    """State for Maven maintenance workflow."""

    # Analysis results
    pom_analysis: dict[str, Any]
    dependency_updates: list[dict[str, Any]]
    build_result: dict[str, Any]

    # Maven-specific
    maven_version: str
    java_version: str


class TestGenerationState(WorkflowState, total=False):
    """State for test generation workflow."""

    # Source analysis
    source_files: list[str]
    test_files: list[str]
    coverage_report: dict[str, Any]

    # Generation results
    generated_tests: list[dict[str, Any]]
    mutation_results: dict[str, Any]

    # Configuration
    target_coverage: float
    test_framework: str


class DockerDeploymentState(WorkflowState, total=False):
    """State for Docker deployment workflow."""

    # Container info
    container_id: str | None
    image_name: str
    container_status: str

    # Deployment results
    build_logs: list[str]
    test_results: dict[str, Any]


def create_initial_state(
    session_id: uuid.UUID,
    project_path: str,
    mode: str = SessionMode.INTERACTIVE.value,
    initial_step: str = "start",
    **kwargs: Any,
) -> WorkflowState:
    """Create initial workflow state."""
    state: WorkflowState = {
        "session_id": session_id,
        "project_path": project_path,
        "mode": mode,
        "current_step": initial_step,
        "previous_step": None,
        "step_sequence": 0,
        "should_pause": False,
        "is_paused": False,
        "checkpoint_id": None,
        "pause_reason": None,
        "input_data": {},
        "output_data": {},
        "error": None,
        "error_step": None,
        "pending_approval": False,
        "approval_request": None,
        "approval_response": None,
        "results": [],
        "artifacts": [],
        "debug_logs": [],
    }
    state.update(kwargs)  # type: ignore
    return state


def is_interactive_mode(state: WorkflowState) -> bool:
    """Check if workflow is in interactive mode."""
    return state.get("mode") == SessionMode.INTERACTIVE.value


def is_autonomous_mode(state: WorkflowState) -> bool:
    """Check if workflow is in autonomous mode."""
    return state.get("mode") == SessionMode.AUTONOMOUS.value


def is_analysis_only_mode(state: WorkflowState) -> bool:
    """Check if workflow is in analysis-only mode."""
    return state.get("mode") == SessionMode.ANALYSIS_ONLY.value


def is_debug_mode(state: WorkflowState) -> bool:
    """Check if workflow is in debug mode."""
    return state.get("mode") == SessionMode.DEBUG.value


def requires_approval(state: WorkflowState, action: str) -> bool:
    """Check if action requires user approval based on mode."""
    mode = state.get("mode")
    if mode == SessionMode.AUTONOMOUS.value:
        return False
    if mode == SessionMode.ANALYSIS_ONLY.value:
        return False
    modification_actions = ["modify", "delete", "create", "update", "apply"]
    return action.lower() in modification_actions


def can_modify(state: WorkflowState) -> bool:
    """Check if workflow can make modifications."""
    return state.get("mode") != SessionMode.ANALYSIS_ONLY.value


def add_debug_log(
    state: WorkflowState, message: str, level: str = "info", data: dict[str, Any] | None = None
) -> None:
    """Add a debug log entry to state (only in debug mode)."""
    if not is_debug_mode(state):
        return
    import time

    log_entry = {
        "timestamp": time.time(),
        "level": level,
        "message": message,
        "step": state.get("current_step"),
        "data": data or {},
    }
    debug_logs = state.get("debug_logs", [])
    debug_logs.append(log_entry)
    state["debug_logs"] = debug_logs
    logger.debug(
        "workflow_debug",
        session_id=str(state.get("session_id")),
        step=state.get("current_step"),
        message=message,
        data=data,
    )


def get_auto_decision(state: WorkflowState, decision_type: str) -> bool:
    """Get automatic decision for autonomous mode."""
    if not is_autonomous_mode(state):
        return False
    auto_decisions = {
        "approve": True,
        "continue": True,
        "retry": True,
        "skip": False,
        "abort": False,
    }
    return auto_decisions.get(decision_type, True)


def request_confirmation(
    state: WorkflowState, action: str, description: str, details: dict[str, Any] | None = None
) -> bool:
    """Request confirmation from user or auto-decide based on mode."""
    mode = state.get("mode")
    if is_debug_mode(state):
        add_debug_log(
            state,
            f"Confirmation requested for: {action}",
            "info",
            {"description": description, "details": details},
        )
    if mode == SessionMode.AUTONOMOUS.value:
        logger.info(
            "auto_approved",
            session_id=str(state.get("session_id")),
            action=action,
            description=description,
        )
        return True
    if mode == SessionMode.ANALYSIS_ONLY.value:
        logger.info(
            "modification_blocked",
            session_id=str(state.get("session_id")),
            action=action,
            description=description,
        )
        return False
    state["pending_approval"] = True
    state["approval_request"] = {
        "action": action,
        "description": description,
        "details": details or {},
    }
    logger.info(
        "approval_requested",
        session_id=str(state.get("session_id")),
        action=action,
        description=description,
    )
    return False


__all__ = [
    "WorkflowState",
    "MavenMaintenanceState",
    "TestGenerationState",
    "DockerDeploymentState",
    "create_initial_state",
    "is_interactive_mode",
    "is_autonomous_mode",
    "is_analysis_only_mode",
    "is_debug_mode",
    "requires_approval",
    "can_modify",
    "add_debug_log",
    "get_auto_decision",
    "request_confirmation",
]
