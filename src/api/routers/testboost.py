"""
TestBoost API router for Maven maintenance and dependency analysis.

Provides endpoints for analyzing projects and running maintenance workflows.
"""

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from src.lib.logging import get_logger
from src.workflows.state import MavenMaintenanceState, TestGenerationStateModel

logger = get_logger(__name__)

router = APIRouter(prefix="/api/testboost", tags=["testboost"])


# Request/Response Models


class AnalyzeRequest(BaseModel):
    """Request model for project analysis."""

    project_path: str = Field(..., description="Path to the Maven project")
    include_snapshots: bool = Field(False, description="Include SNAPSHOT versions")
    check_vulnerabilities: bool = Field(True, description="Check for security vulnerabilities")


class AnalyzeResponse(BaseModel):
    """Response model for project analysis."""

    success: bool
    project_path: str
    dependencies: list[dict[str, Any]]
    available_updates: list[dict[str, Any]]
    vulnerabilities: list[dict[str, Any]]
    compatibility_issues: list[dict[str, Any]]
    error: str | None = None


class MaintenanceRequest(BaseModel):
    """Request model for Maven maintenance."""

    project_path: str = Field(..., description="Path to the Maven project")
    auto_approve: bool = Field(False, description="Auto-approve all updates")
    selected_updates: list[str] | None = Field(
        None, description="Specific updates to apply (format: groupId:artifactId)"
    )
    skip_tests: bool = Field(False, description="Skip test validation")
    dry_run: bool = Field(False, description="Analyze without applying changes")


class MaintenanceResponse(BaseModel):
    """Response model for Maven maintenance."""

    success: bool
    session_id: str
    status: str
    message: str
    applied_updates: list[dict[str, Any]] = []
    failed_updates: list[dict[str, Any]] = []
    test_results: dict[str, Any] | None = None
    branch: str | None = None
    error: str | None = None


class MaintenanceStatus(BaseModel):
    """Status model for maintenance session."""

    session_id: str
    status: str
    current_step: str
    progress: float
    applied_updates: int
    total_updates: int
    errors: list[str]
    warnings: list[str]


# ============================================================================
# Impact Analysis Models (T079)
# ============================================================================


class ImpactInfo(BaseModel):
    """Impact information from analysis."""

    id: str
    file_path: str
    change_category: str
    risk_level: str
    affected_methods: list[str] = []
    change_description: str = ""


class TestRequirementInfo(BaseModel):
    """Test requirement from impact analysis."""

    id: str
    impact_id: str
    test_type: str
    scenario: str
    priority: str
    suggested_assertions: list[str] = []


class ImpactAnalysisRequest(BaseModel):
    """Request model for impact analysis."""

    project_path: str = Field(..., description="Path to the project to analyze")
    verbose: bool = Field(False, description="Include detailed impact descriptions")


class ImpactAnalysisResponse(BaseModel):
    """Response model for impact analysis."""

    success: bool
    project_path: str
    git_ref: str
    total_lines_changed: int
    processing_time_seconds: float
    summary: dict[str, Any]
    impacts: list[ImpactInfo]
    test_requirements: list[TestRequirementInfo]
    error: str | None = None


# In-memory session storage (replace with database in production)
_sessions: dict[str, MavenMaintenanceState] = {}


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_project(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Analyze a Maven project for dependency updates and vulnerabilities.

    This endpoint performs a comprehensive analysis of the project's
    dependencies without making any changes.

    Args:
        request: Analysis request parameters

    Returns:
        Analysis results including updates and vulnerabilities
    """
    import json

    from src.mcp_servers.maven_maintenance.tools.analyze import analyze_dependencies

    logger.info(
        "analyze_project_start",
        project_path=request.project_path,
        include_snapshots=request.include_snapshots,
    )

    try:
        result = await analyze_dependencies(
            request.project_path,
            include_snapshots=request.include_snapshots,
            check_vulnerabilities=request.check_vulnerabilities,
        )

        analysis = json.loads(result)

        if not analysis.get("success"):
            raise HTTPException(status_code=400, detail=analysis.get("error", "Analysis failed"))

        logger.info(
            "analyze_project_complete",
            project_path=request.project_path,
            updates_found=len(analysis.get("available_updates", [])),
            vulnerabilities_found=len(analysis.get("vulnerabilities", [])),
        )

        return AnalyzeResponse(
            success=True,
            project_path=request.project_path,
            dependencies=analysis.get("current_dependencies", []),
            available_updates=analysis.get("available_updates", []),
            vulnerabilities=analysis.get("vulnerabilities", []),
            compatibility_issues=analysis.get("compatibility_issues", []),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("analyze_project_error", project_path=request.project_path, error=str(e))
        return AnalyzeResponse(
            success=False,
            project_path=request.project_path,
            dependencies=[],
            available_updates=[],
            vulnerabilities=[],
            compatibility_issues=[],
            error=str(e),
        )


async def _run_maintenance_task(session_id: str, request: MaintenanceRequest) -> None:
    """
    Background task to run the maintenance workflow.

    Args:
        session_id: Session identifier
        request: Maintenance request parameters
    """
    try:
        # Initialize state
        from uuid import UUID as UUIDType

        initial_state = MavenMaintenanceState(
            session_id=UUIDType(session_id),
            project_path=request.project_path,
            user_approved=request.auto_approve,
        )

        if request.selected_updates:
            initial_state.user_selections = request.selected_updates

        _sessions[session_id] = initial_state

        # Import and run workflow using the agent-based approach
        from src.workflows.maven_maintenance_agent import run_maven_maintenance_with_agent

        result_json = await run_maven_maintenance_with_agent(
            project_path=request.project_path,
            session_id=session_id,
            mode="autonomous" if request.auto_approve else "interactive",
        )

        # Parse result and update state
        import json as json_module

        result_data = json_module.loads(result_json)

        # Update state with results
        initial_state.completed = result_data.get("success", False)
        if result_data.get("agent_reasoning"):
            initial_state.output_data = result_data

        final_state = initial_state

        # Update session with final state
        _sessions[session_id] = final_state

        logger.info(
            "maintenance_complete",
            session_id=session_id,
            applied=len(final_state.applied_updates),
            failed=len(final_state.failed_updates),
        )

    except Exception as e:
        logger.error("maintenance_error", session_id=session_id, error=str(e))

        if session_id in _sessions:
            _sessions[session_id].errors.append(str(e))


@router.post("/maintenance/maven", response_model=MaintenanceResponse)
async def run_maintenance(
    request: MaintenanceRequest, background_tasks: BackgroundTasks
) -> MaintenanceResponse:
    """
    Start a Maven dependency maintenance workflow.

    This endpoint initiates a background task that:
    1. Analyzes the project for updates
    2. Creates a maintenance branch
    3. Applies selected updates
    4. Validates with tests
    5. Commits changes

    Args:
        request: Maintenance request parameters
        background_tasks: FastAPI background tasks

    Returns:
        Initial response with session ID for tracking
    """
    from pathlib import Path

    logger.info(
        "maintenance_start",
        project_path=request.project_path,
        auto_approve=request.auto_approve,
        dry_run=request.dry_run,
    )

    # Validate project path
    project_dir = Path(request.project_path)
    if not project_dir.exists():
        raise HTTPException(
            status_code=404, detail=f"Project path not found: {request.project_path}"
        )

    pom_file = project_dir / "pom.xml"
    if not pom_file.exists():
        raise HTTPException(status_code=400, detail="Not a Maven project: pom.xml not found")

    # Generate session ID
    session_id = str(uuid4())

    if request.dry_run:
        # For dry run, just do analysis
        import json

        from src.mcp_servers.maven_maintenance.tools.analyze import analyze_dependencies

        result = await analyze_dependencies(
            request.project_path, include_snapshots=False, check_vulnerabilities=True
        )

        analysis = json.loads(result)

        return MaintenanceResponse(
            success=True,
            session_id=session_id,
            status="dry_run_complete",
            message=f"Dry run complete. Found {len(analysis.get('available_updates', []))} updates.",
            applied_updates=[],
            failed_updates=[],
            test_results=None,
            branch=None,
        )

    # Start background maintenance task
    background_tasks.add_task(_run_maintenance_task, session_id, request)

    return MaintenanceResponse(
        success=True,
        session_id=session_id,
        status="started",
        message="Maintenance workflow started. Use the session ID to track progress.",
        applied_updates=[],
        failed_updates=[],
    )


@router.get("/maintenance/maven/{session_id}", response_model=MaintenanceStatus)
async def get_maintenance_status(session_id: str) -> MaintenanceStatus:
    """
    Get the status of a maintenance session.

    Args:
        session_id: Session identifier

    Returns:
        Current status of the maintenance workflow
    """
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    state = _sessions[session_id]

    # Calculate progress based on completed steps
    steps = [
        "validate_project",
        "check_git_status",
        "analyze_maven",
        "fetch_release_notes",
        "run_baseline_tests",
        "user_validation",
        "create_maintenance_branch",
        "apply_update_batch",
        "validate_changes",
        "commit_changes",
        "finalize",
    ]

    current_step = state.current_step
    if current_step in steps:
        progress = (steps.index(current_step) + 1) / len(steps)
    else:
        progress = 0.0

    # Determine status
    if state.completed:
        status = "completed"
    elif state.errors:
        status = "error"
    else:
        status = "in_progress"

    return MaintenanceStatus(
        session_id=session_id,
        status=status,
        current_step=current_step,
        progress=progress,
        applied_updates=len(state.applied_updates),
        total_updates=len(state.pending_updates),
        errors=state.errors,
        warnings=state.warnings,
    )


@router.get("/maintenance/maven/{session_id}/result", response_model=MaintenanceResponse)
async def get_maintenance_result(session_id: str) -> MaintenanceResponse:
    """
    Get the final result of a completed maintenance session.

    Args:
        session_id: Session identifier

    Returns:
        Final results of the maintenance workflow
    """
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    state = _sessions[session_id]

    if not state.completed and not state.errors:
        raise HTTPException(status_code=400, detail="Maintenance workflow is still in progress")

    return MaintenanceResponse(
        success=len(state.errors) == 0,
        session_id=session_id,
        status="completed" if state.completed else "error",
        message=(
            f"Applied {len(state.applied_updates)} updates"
            if state.completed
            else state.errors[0] if state.errors else "Unknown error"
        ),
        applied_updates=state.applied_updates,
        failed_updates=state.failed_updates,
        test_results=state.validation_test_results if state.validation_test_results else None,
        branch=state.maintenance_branch,
        error=state.errors[0] if state.errors else None,
    )


@router.delete("/maintenance/maven/{session_id}")
async def cancel_maintenance(session_id: str) -> dict[str, str]:
    """
    Cancel a running maintenance session.

    Args:
        session_id: Session identifier

    Returns:
        Confirmation of cancellation
    """
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    # Mark session as cancelled
    _sessions[session_id].errors.append("Cancelled by user")

    logger.info("maintenance_cancelled", session_id=session_id)

    return {"message": f"Maintenance session {session_id} cancelled"}


# Test Generation Models and Endpoints


class TestGenerateRequest(BaseModel):
    """Request model for test generation."""

    project_path: str = Field(..., description="Path to the Java project")
    target_mutation_score: float = Field(80.0, description="Target mutation score percentage")
    include_integration: bool = Field(True, description="Generate integration tests")
    include_snapshot: bool = Field(True, description="Generate snapshot tests")
    max_classes: int = Field(20, description="Maximum number of classes to process")


class TestGenerateResponse(BaseModel):
    """Response model for test generation."""

    success: bool
    session_id: str
    status: str
    message: str
    unit_tests_generated: int = 0
    integration_tests_generated: int = 0
    snapshot_tests_generated: int = 0
    mutation_score: float = 0.0
    quality_report: dict[str, Any] | None = None
    error: str | None = None


class TestGenerationStatus(BaseModel):
    """Status model for test generation session."""

    session_id: str
    status: str
    current_step: str
    progress: float
    unit_tests: int
    integration_tests: int
    mutation_score: float
    errors: list[str]
    warnings: list[str]


# Test generation session storage
_test_sessions: dict[str, TestGenerationStateModel] = {}


async def _run_test_generation_task(session_id: str, request: TestGenerateRequest) -> None:
    """Background task to run the test generation workflow."""
    try:
        from uuid import UUID as UUIDType

        from src.workflows.test_generation_agent import run_test_generation_with_agent

        session_uuid = UUIDType(session_id)
        initial_state = TestGenerationStateModel(
            session_id=session_uuid,
            project_path=request.project_path,
            target_mutation_score=request.target_mutation_score,
        )

        _test_sessions[session_id] = initial_state

        # Run test generation using agent-based approach
        # Note: run_test_generation_with_agent returns a dict, not JSON
        result_data = await run_test_generation_with_agent(
            session_id=session_uuid,
            project_path=request.project_path,
            db_session=None,  # No DB session in background task context
            coverage_target=request.target_mutation_score,
            use_llm=True,
        )

        # Update state with results
        initial_state.completed = True
        initial_state.generated_unit_tests = result_data.get("generated_tests", [])
        initial_state.mutation_score = result_data.get("mutation_score", 0.0)
        if result_data.get("quality_report"):
            initial_state.quality_report = result_data["quality_report"]

        final_state = initial_state
        _test_sessions[session_id] = final_state

        logger.info(
            "test_generation_complete",
            session_id=session_id,
            unit_tests=len(final_state.generated_unit_tests),
            mutation_score=final_state.mutation_score,
        )

    except Exception as e:
        logger.error("test_generation_error", session_id=session_id, error=str(e))
        if session_id in _test_sessions:
            _test_sessions[session_id].errors.append(str(e))


@router.post("/tests/generate", response_model=TestGenerateResponse)
async def generate_tests(
    request: TestGenerateRequest, background_tasks: BackgroundTasks
) -> TestGenerateResponse:
    """Start test generation workflow for a Java project."""
    from pathlib import Path

    logger.info(
        "test_generation_start",
        project_path=request.project_path,
        target_score=request.target_mutation_score,
    )

    project_dir = Path(request.project_path)
    if not project_dir.exists():
        raise HTTPException(
            status_code=404, detail=f"Project path not found: {request.project_path}"
        )

    src_dir = project_dir / "src" / "main" / "java"
    if not src_dir.exists():
        raise HTTPException(status_code=400, detail="Not a Java project: src/main/java not found")

    session_id = str(uuid4())
    background_tasks.add_task(_run_test_generation_task, session_id, request)

    return TestGenerateResponse(
        success=True,
        session_id=session_id,
        status="started",
        message="Test generation workflow started. Use the session ID to track progress.",
    )


@router.get("/tests/generate/{session_id}", response_model=TestGenerationStatus)
async def get_test_generation_status(session_id: str) -> TestGenerationStatus:
    """Get the status of a test generation session."""
    if session_id not in _test_sessions:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    state = _test_sessions[session_id]
    steps = [
        "analyze_project_structure",
        "detect_conventions",
        "classify_classes",
        "generate_unit_tests",
        "compile_and_fix_unit",
        "generate_integration_tests",
        "compile_and_fix_integration",
        "generate_snapshot_tests",
        "run_mutation_testing",
        "generate_killer_tests",
        "finalize",
    ]

    current_step = state.current_step
    progress = (steps.index(current_step) + 1) / len(steps) if current_step in steps else 0.0
    status = "completed" if state.completed else ("error" if state.errors else "in_progress")

    return TestGenerationStatus(
        session_id=session_id,
        status=status,
        current_step=current_step,
        progress=progress,
        unit_tests=len(state.generated_unit_tests),
        integration_tests=len(state.generated_integration_tests),
        mutation_score=state.mutation_score,
        errors=state.errors,
        warnings=state.warnings,
    )


@router.get("/tests/generate/{session_id}/result", response_model=TestGenerateResponse)
async def get_test_generation_result(session_id: str) -> TestGenerateResponse:
    """Get the final result of a completed test generation session."""
    if session_id not in _test_sessions:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    state = _test_sessions[session_id]
    if not state.completed and not state.errors:
        raise HTTPException(status_code=400, detail="Test generation workflow is still in progress")

    return TestGenerateResponse(
        success=len(state.errors) == 0,
        session_id=session_id,
        status="completed" if state.completed else "error",
        message=(
            f"Generated {len(state.generated_unit_tests)} unit tests, mutation score: {state.mutation_score}%"
            if state.completed
            else (state.errors[0] if state.errors else "Unknown error")
        ),
        unit_tests_generated=len(state.generated_unit_tests),
        integration_tests_generated=len(state.generated_integration_tests),
        snapshot_tests_generated=len(state.generated_snapshot_tests),
        mutation_score=state.mutation_score,
        quality_report=state.quality_report if state.quality_report else None,
        error=state.errors[0] if state.errors else None,
    )


# ============================================================================
# Impact Analysis Endpoint (T080)
# ============================================================================


@router.post("/tests/impact", response_model=ImpactAnalysisResponse)
async def analyze_impact(request: ImpactAnalysisRequest) -> ImpactAnalysisResponse:
    """
    Analyze code changes to identify impacts and generate test requirements.

    Uses git diff to analyze uncommitted changes and classifies them by:
    - Risk level (business_critical, non_critical)
    - Change category (logic_change, api_signature, security, etc.)
    - Test requirements (unit, integration, boundary, etc.)

    Args:
        request: Impact analysis request parameters

    Returns:
        Impact report with identified impacts and test requirements
    """
    from pathlib import Path

    from src.workflows.impact_analysis import run_impact_analysis

    logger.info("impact_analysis_start", project_path=request.project_path)

    # Validate project path
    project_dir = Path(request.project_path).resolve()
    if not project_dir.exists():
        raise HTTPException(
            status_code=404, detail=f"Project path not found: {request.project_path}"
        )

    try:
        # Run impact analysis
        report = await run_impact_analysis(str(project_dir))

        # Convert to response model
        impacts = [
            ImpactInfo(
                id=impact.id,
                file_path=impact.file_path,
                change_category=impact.category.value,
                risk_level=impact.risk_level.value,
                affected_methods=impact.affected_components,
                change_description=impact.change_summary if request.verbose else "",
            )
            for impact in report.impacts
        ]

        test_requirements = [
            TestRequirementInfo(
                id=req.id,
                impact_id=req.impact_id,
                test_type=req.test_type.value,
                scenario=req.scenario_type.value,
                priority=str(req.priority),
                suggested_assertions=[],
            )
            for req in report.test_requirements
        ]

        logger.info(
            "impact_analysis_complete",
            project_path=request.project_path,
            impacts_found=len(impacts),
            tests_required=len(test_requirements),
        )

        return ImpactAnalysisResponse(
            success=True,
            project_path=report.project_path,
            git_ref=report.git_ref,
            total_lines_changed=report.total_lines_changed,
            processing_time_seconds=report.processing_time_seconds,
            summary=report.summary,
            impacts=impacts,
            test_requirements=test_requirements,
        )

    except Exception as e:
        logger.error("impact_analysis_error", project_path=request.project_path, error=str(e))
        return ImpactAnalysisResponse(
            success=False,
            project_path=str(project_dir),
            git_ref="",
            total_lines_changed=0,
            processing_time_seconds=0.0,
            summary={},
            impacts=[],
            test_requirements=[],
            error=str(e),
        )
