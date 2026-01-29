"""Base workflow state definitions.

Provides Pydantic models for workflow states with proper validation
and serialization support for LangGraph workflows.
"""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.db.models.session import SessionMode
from src.lib.logging import get_logger

logger = get_logger(__name__)


class WorkflowStateModel(BaseModel):
    """Base workflow state for LangGraph StateGraph.

    This Pydantic model defines the shared state structure used by all
    TestBoost workflows. It provides the common fields needed for
    session tracking, execution control, and step management.

    Supports dict-like access via get() and __getitem__ for backward
    compatibility with existing code using TypedDict patterns.
    """

    model_config = ConfigDict(
        extra="allow",  # Allow additional fields for flexibility
        validate_assignment=True,  # Validate on attribute assignment
    )

    def get(self, key: str, default: Any = None) -> Any:
        """Dict-like get access for backward compatibility."""
        try:
            return getattr(self, key, default)
        except AttributeError:
            return self.model_extra.get(key, default) if self.model_extra else default

    def __getitem__(self, key: str) -> Any:
        """Dict-like indexing for backward compatibility."""
        if hasattr(self, key):
            return getattr(self, key)
        if self.model_extra and key in self.model_extra:
            return self.model_extra[key]
        raise KeyError(key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Dict-like assignment for backward compatibility."""
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            # Store in model_extra for unknown keys
            if self.model_extra is None:
                object.__setattr__(self, "__pydantic_extra__", {})
            self.model_extra[key] = value  # type: ignore[index]

    def __contains__(self, key: str) -> bool:
        """Support 'in' operator for dict-like behavior."""
        return hasattr(self, key) or (self.model_extra is not None and key in self.model_extra)

    def keys(self) -> list[str]:
        """Return all field names for dict-like iteration."""
        base_keys = list(self.__class__.model_fields.keys())
        if self.model_extra:
            base_keys.extend(self.model_extra.keys())
        return base_keys

    def items(self) -> list[tuple[str, Any]]:
        """Return all field items for dict-like iteration."""
        return [(k, self.get(k)) for k in self.keys()]

    def update(self, other: dict[str, Any]) -> None:
        """Update fields from dict for backward compatibility."""
        for key, value in other.items():
            self[key] = value

    def values(self) -> list[Any]:
        """Return all field values for dict-like iteration."""
        return [self.get(k) for k in self.keys()]

    def __iter__(self) -> Any:
        """Iterate over keys for dict-like unpacking with **state."""
        return iter(self.keys())

    # Session identification
    session_id: uuid.UUID
    project_path: str
    mode: str = SessionMode.INTERACTIVE.value

    # Execution state
    current_step: str = "start"
    previous_step: str | None = None
    step_sequence: int = 0

    # Workflow control
    should_pause: bool = False
    is_paused: bool = False
    checkpoint_id: str | None = None
    pause_reason: str | None = None

    # Data passing between nodes
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)

    # Error handling
    error: str | None = None
    error_step: str | None = None

    # Approval workflow (for interactive mode)
    pending_approval: bool = False
    approval_request: dict[str, Any] | None = None
    approval_response: dict[str, Any] | None = None

    # Results accumulation
    results: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)

    # Debug mode tracking
    debug_logs: list[dict[str, Any]] = Field(default_factory=list)


class MavenMaintenanceState(WorkflowStateModel):
    """State for Maven maintenance workflow.

    Contains all fields needed by testboost.py router for session
    management, status tracking, and result reporting.
    """

    # Analysis results
    pom_analysis: dict[str, Any] = Field(default_factory=dict)
    dependency_updates: list[dict[str, Any]] = Field(default_factory=list)
    build_result: dict[str, Any] = Field(default_factory=dict)

    # Maven-specific
    maven_version: str = ""
    java_version: str = ""

    # User interaction (used by testboost.py)
    user_approved: bool = False
    user_selections: list[str] = Field(default_factory=list)

    # Update tracking (used by testboost.py router)
    applied_updates: list[dict[str, Any]] = Field(default_factory=list)
    failed_updates: list[dict[str, Any]] = Field(default_factory=list)
    pending_updates: list[dict[str, Any]] = Field(default_factory=list)

    # Status tracking (used by testboost.py router)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    completed: bool = False

    # Validation and branch (used by testboost.py router)
    validation_test_results: dict[str, Any] | None = None
    maintenance_branch: str | None = None


class GeneratedTestsStateModel(WorkflowStateModel):
    """State for test generation workflow."""

    # Source analysis
    source_files: list[str] = Field(default_factory=list)
    test_files: list[str] = Field(default_factory=list)
    coverage_report: dict[str, Any] = Field(default_factory=dict)

    # Generation results
    generated_tests: list[dict[str, Any]] = Field(default_factory=list)
    generated_unit_tests: list[dict[str, Any]] = Field(default_factory=list)
    generated_integration_tests: list[dict[str, Any]] = Field(default_factory=list)
    generated_snapshot_tests: list[dict[str, Any]] = Field(default_factory=list)
    mutation_results: dict[str, Any] = Field(default_factory=dict)

    # Status and quality
    mutation_score: float = 0.0
    quality_report: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    completed: bool = False

    # Configuration
    target_coverage: float = 80.0
    target_mutation_score: float = 80.0
    test_framework: str = "junit5"


class DockerDeploymentStateModel(WorkflowStateModel):
    """State for Docker deployment workflow."""

    # Container info
    container_id: str | None = None
    image_name: str = ""
    container_status: str = ""

    # Deployment results
    build_logs: list[str] = Field(default_factory=list)
    test_results: dict[str, Any] = Field(default_factory=dict)

    # Status
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    completed: bool = False


# Aliases for backward compatibility
WorkflowState = WorkflowStateModel
TestGenerationState = GeneratedTestsStateModel
DockerDeploymentState = DockerDeploymentStateModel


def create_initial_state(
    session_id: uuid.UUID,
    project_path: str,
    mode: str = SessionMode.INTERACTIVE.value,
    initial_step: str = "start",
    **kwargs: Any,
) -> WorkflowStateModel:
    """Create initial workflow state."""
    return WorkflowStateModel(
        session_id=session_id,
        project_path=project_path,
        mode=mode,
        current_step=initial_step,
        **kwargs,
    )


def create_maven_state(
    session_id: uuid.UUID,
    project_path: str,
    mode: str = SessionMode.INTERACTIVE.value,
    initial_step: str = "start",
    **kwargs: Any,
) -> MavenMaintenanceState:
    """Create initial Maven maintenance state."""
    return MavenMaintenanceState(
        session_id=session_id,
        project_path=project_path,
        mode=mode,
        current_step=initial_step,
        **kwargs,
    )


def is_interactive_mode(state: WorkflowStateModel) -> bool:
    """Check if workflow is in interactive mode."""
    return state.mode == SessionMode.INTERACTIVE.value


def is_autonomous_mode(state: WorkflowStateModel) -> bool:
    """Check if workflow is in autonomous mode."""
    return state.mode == SessionMode.AUTONOMOUS.value


def is_analysis_only_mode(state: WorkflowStateModel) -> bool:
    """Check if workflow is in analysis-only mode."""
    return state.mode == SessionMode.ANALYSIS_ONLY.value


def is_debug_mode(state: WorkflowStateModel) -> bool:
    """Check if workflow is in debug mode."""
    return state.mode == SessionMode.DEBUG.value


def requires_approval(state: WorkflowStateModel, action: str) -> bool:
    """Check if action requires user approval based on mode."""
    mode = state.mode
    if mode == SessionMode.AUTONOMOUS.value:
        return False
    if mode == SessionMode.ANALYSIS_ONLY.value:
        return False
    modification_actions = ["modify", "delete", "create", "update", "apply"]
    return action.lower() in modification_actions


def can_modify(state: WorkflowStateModel) -> bool:
    """Check if workflow can make modifications."""
    return state.mode != SessionMode.ANALYSIS_ONLY.value


def add_debug_log(
    state: WorkflowStateModel, message: str, level: str = "info", data: dict[str, Any] | None = None
) -> None:
    """Add a debug log entry to state (only in debug mode)."""
    if not is_debug_mode(state):
        return
    import time

    log_entry = {
        "timestamp": time.time(),
        "level": level,
        "message": message,
        "step": state.current_step,
        "data": data or {},
    }
    state.debug_logs.append(log_entry)
    logger.debug(
        "workflow_debug",
        session_id=str(state.session_id),
        step=state.current_step,
        message=message,
        data=data,
    )


def get_auto_decision(state: WorkflowStateModel, decision_type: str) -> bool:
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
    state: WorkflowStateModel, action: str, description: str, details: dict[str, Any] | None = None
) -> bool:
    """Request confirmation from user or auto-decide based on mode."""
    mode = state.mode
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
            session_id=str(state.session_id),
            action=action,
            description=description,
        )
        return True
    if mode == SessionMode.ANALYSIS_ONLY.value:
        logger.info(
            "modification_blocked",
            session_id=str(state.session_id),
            action=action,
            description=description,
        )
        return False
    state.pending_approval = True
    state.approval_request = {
        "action": action,
        "description": description,
        "details": details or {},
    }
    logger.info(
        "approval_requested",
        session_id=str(state.session_id),
        action=action,
        description=description,
    )
    return False


__all__ = [
    "WorkflowState",
    "WorkflowStateModel",
    "MavenMaintenanceState",
    "TestGenerationState",
    "GeneratedTestsStateModel",
    "DockerDeploymentState",
    "DockerDeploymentStateModel",
    "create_initial_state",
    "create_maven_state",
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
