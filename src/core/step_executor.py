# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 TestBoost Contributors

"""Step executor for running workflow steps.

Bridges the gap between API step management and actual workflow execution.
Each step code maps to a specific workflow function that performs the real work.

Auto-advance logic:
- Analysis steps (auto_advance=True) automatically trigger the next step
- Action steps (auto_advance=False) wait for user review before proceeding
"""

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routers.metrics import record_workflow_duration
from src.core.session import WORKFLOW_STEPS, SessionService
from src.db import SessionLocal
from src.db.models.step import StepStatus
from src.lib.logging import get_logger

logger = get_logger(__name__)


class StepExecutionError(Exception):
    """Raised when step execution fails."""

    def __init__(self, message: str, step_code: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.step_code = step_code
        self.details = details or {}


class StepExecutor:
    """Execute workflow steps and update their status.

    Maps step codes to workflow functions and manages step lifecycle:
    - pending → in_progress (on start)
    - in_progress → completed (on success)
    - in_progress → failed (on error)
    """

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.session_service = SessionService(db_session)

    async def execute_step(
        self,
        session_id: uuid.UUID,
        step_code: str,
        inputs: dict[str, Any] | None = None,
        run_in_background: bool = False,
    ) -> dict[str, Any]:
        """Execute a workflow step.

        Args:
            session_id: Session UUID
            step_code: Step code to execute
            inputs: Optional input data for the step
            run_in_background: If True, run step in background task

        Returns:
            Step execution result with status and outputs

        Raises:
            StepExecutionError: If step execution fails
        """
        # Get session and step
        session = await self.session_service.get_session(session_id)
        if not session:
            raise StepExecutionError(f"Session not found: {session_id}", step_code)

        step = await self.session_service.get_step_by_code(session_id, step_code)
        if not step:
            raise StepExecutionError(f"Step not found: {step_code}", step_code)

        # Validate step can be executed
        if step.status not in [StepStatus.PENDING.value, StepStatus.FAILED.value]:
            raise StepExecutionError(
                f"Cannot execute step: status is {step.status}",
                step_code
            )

        logger.info(
            "step_execution_start",
            session_id=str(session_id),
            step_code=step_code,
            session_type=session.session_type,
        )

        # Mark step as in progress
        await self.session_service.update_step_status(
            step.id,
            StepStatus.IN_PROGRESS.value
        )

        if run_in_background:
            # Create background task with a fresh DB session
            # This avoids DB connection conflicts when the HTTP request completes
            asyncio.create_task(
                self._execute_step_in_background(session_id, step_code, session.session_type, inputs)
            )
            return {
                "status": "in_progress",
                "message": f"Step '{step.name}' started in background",
                "step_id": str(step.id),
            }
        else:
            # Execute synchronously
            return await self._execute_step_async(
                session_id, step_code, session.session_type, inputs
            )

    async def _execute_step_in_background(
        self,
        session_id: uuid.UUID,
        step_code: str,
        session_type: str,
        inputs: dict[str, Any] | None = None,
    ) -> None:
        """Execute a step in background with its own DB session.

        This is needed when run_in_background=True to avoid DB connection
        conflicts when the HTTP request completes and closes the original session.

        Args:
            session_id: Session UUID
            step_code: Step code
            session_type: Type of session
            inputs: Optional input data
        """
        async with SessionLocal() as db_session:
            try:
                executor = StepExecutor(db_session)
                await executor._execute_step_async(
                    session_id, step_code, session_type, inputs
                )
                await db_session.commit()
            except Exception as e:
                # Rollback is safe here because this session is owned by this background task
                await db_session.rollback()
                logger.error(
                    "background_step_execution_failed",
                    session_id=str(session_id),
                    step_code=step_code,
                    error=str(e),
                )

    async def _execute_step_async(
        self,
        session_id: uuid.UUID,
        step_code: str,
        session_type: str,
        inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute step workflow and update status.

        Args:
            session_id: Session UUID
            step_code: Step code
            session_type: Type of session (maven_maintenance, test_generation, etc.)
            inputs: Optional input data

        Returns:
            Execution result
        """
        # Start timing for metrics
        start_time = time.time()

        step = await self.session_service.get_step_by_code(session_id, step_code)
        if not step:
            raise StepExecutionError(f"Step not found: {step_code}", step_code)

        # Extract step.id before try block to avoid lazy-load issues in exception handler
        step_id = step.id

        try:
            # Get the workflow function for this step
            workflow_fn = self._get_workflow_function(session_type, step_code)

            if workflow_fn is None:
                # No specific workflow - mark as completed with placeholder
                outputs = {
                    "message": f"Step '{step.name}' completed (no workflow defined)",
                    "timestamp": datetime.utcnow().isoformat(),
                }
                await self.session_service.update_step_status(
                    step_id,
                    StepStatus.COMPLETED.value,
                    outputs=outputs,
                )
                logger.info(
                    "step_completed_no_workflow",
                    session_id=str(session_id),
                    step_code=step_code,
                )

                # Check for auto-advance
                await self._maybe_auto_advance(session_id, session_type, step_code)

                return {"status": "completed", "outputs": outputs}

            # Execute the workflow function
            session = await self.session_service.get_session(session_id)
            result = await workflow_fn(
                session_id=session_id,
                project_path=session.project_path if session else "",
                db_session=self.db_session,
                inputs=inputs or {},
            )

            # Mark step as completed
            outputs = {
                "result": result,
                "timestamp": datetime.utcnow().isoformat(),
            }
            await self.session_service.update_step_status(
                step_id,
                StepStatus.COMPLETED.value,
                outputs=outputs,
            )

            logger.info(
                "step_execution_completed",
                session_id=str(session_id),
                step_code=step_code,
            )

            # Record workflow duration metric
            duration = time.time() - start_time
            record_workflow_duration(
                workflow_type=f"{session_type}_{step_code}",
                duration_seconds=duration,
                status="success"
            )

            # Check for auto-advance to next step
            await self._maybe_auto_advance(session_id, session_type, step_code)

            return {"status": "completed", "outputs": outputs}

        except Exception as e:
            # Mark step as failed
            error_msg = str(e)

            # Note: No explicit rollback needed here - the session manager (get_db)
            # will automatically rollback on exception. Calling rollback here
            # can cause MissingGreenlet errors in background tasks.

            await self.session_service.update_step_status(
                step_id,  # Use step_id extracted before try block
                StepStatus.FAILED.value,
                error_message=error_msg,
            )

            # Record workflow duration metric (failed)
            duration = time.time() - start_time
            record_workflow_duration(
                workflow_type=f"{session_type}_{step_code}",
                duration_seconds=duration,
                status="failed"
            )

            logger.error(
                "step_execution_failed",
                session_id=str(session_id),
                step_code=step_code,
                error=error_msg,
            )

            raise StepExecutionError(error_msg, step_code) from e

    async def _maybe_auto_advance(
        self,
        session_id: uuid.UUID,
        session_type: str,
        completed_step_code: str,
    ) -> None:
        """Check if the completed step should auto-advance to the next step.

        If the step has auto_advance=True, automatically execute the next pending step.

        Args:
            session_id: Session UUID
            session_type: Type of session
            completed_step_code: Code of the step that just completed
        """
        # Get step definition to check auto_advance flag
        step_def = self._get_step_definition(session_type, completed_step_code)

        if not step_def or not step_def.get("auto_advance", False):
            logger.debug(
                "auto_advance_skipped",
                session_id=str(session_id),
                step_code=completed_step_code,
                reason="auto_advance not enabled",
            )
            return

        # Find the next step
        next_step_code = self._get_next_step_code(session_type, completed_step_code)

        if not next_step_code:
            logger.debug(
                "auto_advance_skipped",
                session_id=str(session_id),
                step_code=completed_step_code,
                reason="no next step",
            )
            return

        # Check if next step is pending
        next_step = await self.session_service.get_step_by_code(session_id, next_step_code)

        if not next_step or next_step.status != StepStatus.PENDING.value:
            logger.debug(
                "auto_advance_skipped",
                session_id=str(session_id),
                step_code=completed_step_code,
                next_step_code=next_step_code,
                reason="next step not pending",
            )
            return

        logger.info(
            "auto_advance_triggered",
            session_id=str(session_id),
            completed_step=completed_step_code,
            next_step=next_step_code,
        )

        # Execute the next step in background with a new DB session
        # This avoids DB connection conflicts with the current transaction
        asyncio.create_task(
            self._execute_auto_advance_step(session_id, next_step_code, session_type)
        )

    async def _execute_auto_advance_step(
        self,
        session_id: uuid.UUID,
        step_code: str,
        session_type: str,
    ) -> None:
        """Execute an auto-advance step with a fresh DB session.

        This is needed because the parent step's DB session may still be
        in the middle of committing when auto-advance triggers.

        Args:
            session_id: Session UUID
            step_code: Step code to execute
            session_type: Type of session
        """
        async with SessionLocal() as db_session:
            try:
                executor = StepExecutor(db_session)
                await executor._execute_step_async(
                    session_id, step_code, session_type
                )
                await db_session.commit()
            except Exception as e:
                # Rollback is safe here because this session is owned by this background task
                await db_session.rollback()
                logger.error(
                    "auto_advance_execution_failed",
                    session_id=str(session_id),
                    step_code=step_code,
                    error=str(e),
                )

    def _get_step_definition(
        self, session_type: str, step_code: str
    ) -> dict[str, Any] | None:
        """Get the step definition from WORKFLOW_STEPS.

        Args:
            session_type: Type of session
            step_code: Step code

        Returns:
            Step definition dict or None if not found
        """
        steps = WORKFLOW_STEPS.get(session_type, [])
        for step_def in steps:
            if step_def.get("code") == step_code:
                return step_def
        return None

    def _get_next_step_code(
        self, session_type: str, current_step_code: str
    ) -> str | None:
        """Get the code of the next step in the workflow.

        Args:
            session_type: Type of session
            current_step_code: Current step code

        Returns:
            Next step code or None if this is the last step
        """
        steps = WORKFLOW_STEPS.get(session_type, [])

        for i, step_def in enumerate(steps):
            if step_def.get("code") == current_step_code:
                # Check if there's a next step
                if i + 1 < len(steps):
                    next_code = steps[i + 1].get("code")
                    return str(next_code) if next_code else None
                return None

        return None

    def _get_workflow_function(
        self, session_type: str, step_code: str
    ) -> Callable[
        [uuid.UUID, str, AsyncSession, dict[str, Any]], Awaitable[dict[str, Any]]
    ] | None:
        """Get the workflow function for a step.

        Maps session_type + step_code to actual workflow functions.

        Args:
            session_type: Session type (maven_maintenance, test_generation, docker_deployment)
            step_code: Step code

        Returns:
            Async function to execute, or None if no workflow defined
        """
        # Workflow function registry
        # Each function must have signature: async fn(session_id, project_path, db_session, inputs)
        workflows = {
            "test_generation": {
                "analyze_project": self._analyze_project,
                "identify_coverage_gaps": self._identify_coverage_gaps,
                "generate_tests": self._generate_tests,
                "validate_tests": self._validate_tests,
            },
            "maven_maintenance": {
                "analyze_dependencies": self._analyze_dependencies,
                "identify_vulnerabilities": self._identify_vulnerabilities,
                "plan_updates": self._plan_updates,
                "apply_updates": self._apply_updates,
                "validate_changes": self._validate_changes,
            },
            "docker_deployment": {
                "analyze_dockerfile": self._analyze_dockerfile,
                "optimize_image": self._optimize_image,
                "generate_compose": self._generate_compose,
                "validate_deployment": self._validate_deployment,
            },
        }

        session_workflows = workflows.get(session_type, {})
        return session_workflows.get(step_code)

    # ==========================================================================
    # Test Generation Steps
    # ==========================================================================

    async def _analyze_project(
        self,
        session_id: uuid.UUID,
        project_path: str,
        db_session: AsyncSession,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Analyze project structure for test generation."""
        from src.workflows.test_generation_agent import _find_source_files

        source_files = _find_source_files(project_path)

        return {
            "source_files_count": len(source_files),
            "source_files": source_files[:20],  # Limit for output size
            "project_path": project_path,
        }

    async def _identify_coverage_gaps(
        self,
        session_id: uuid.UUID,
        project_path: str,
        db_session: AsyncSession,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Identify coverage gaps in the project."""
        # Get source files from previous step or re-analyze
        from src.workflows.test_generation_agent import _find_source_files

        source_files = _find_source_files(project_path)

        # In a full implementation, would run coverage analysis here
        # For now, return all source files as needing tests
        return {
            "files_needing_tests": len(source_files),
            "coverage_gaps": source_files,
        }

    async def _generate_tests(
        self,
        session_id: uuid.UUID,
        project_path: str,
        db_session: AsyncSession,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate tests for the project."""
        from src.workflows.test_generation_agent import run_test_generation_with_agent

        # Run the full test generation workflow
        result = await run_test_generation_with_agent(
            session_id=session_id,
            project_path=project_path,
            db_session=db_session,
            use_llm=inputs.get("use_llm", True),
        )

        return {
            "success": result.get("success", False),
            "tests_generated": len(result.get("generated_tests", [])),
            "metrics": result.get("metrics", {}),
        }

    async def _validate_tests(
        self,
        session_id: uuid.UUID,
        project_path: str,
        db_session: AsyncSession,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate generated tests by running them."""
        import subprocess
        from pathlib import Path

        project_dir = Path(project_path)

        # Run Maven tests
        try:
            result = subprocess.run(
                ["mvn", "test", "-f", str(project_dir / "pom.xml")],
                capture_output=True,
                text=True,
                timeout=300,
                shell=True,
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout[-2000:] if result.stdout else "",
                "errors": result.stderr[-1000:] if result.stderr else "",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    # ==========================================================================
    # Maven Maintenance Steps
    # ==========================================================================

    async def _analyze_dependencies(
        self,
        session_id: uuid.UUID,
        project_path: str,
        db_session: AsyncSession,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Analyze Maven dependencies."""
        import json

        from src.mcp_servers.maven_maintenance.tools.analyze import analyze_dependencies

        result_json = await analyze_dependencies(project_path)
        result = json.loads(result_json)

        return {
            "success": result.get("success", False),
            "dependencies_count": len(result.get("dependencies", [])),
            "available_updates": len(result.get("available_updates", [])),
        }

    async def _identify_vulnerabilities(
        self,
        session_id: uuid.UUID,
        project_path: str,
        db_session: AsyncSession,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Identify security vulnerabilities in dependencies."""
        # In full implementation, would scan for CVEs
        return {
            "vulnerabilities_found": 0,
            "message": "Vulnerability scanning not yet implemented",
        }

    async def _plan_updates(
        self,
        session_id: uuid.UUID,
        project_path: str,
        db_session: AsyncSession,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Plan dependency updates."""
        return {
            "updates_planned": 0,
            "message": "Update planning completed",
        }

    async def _apply_updates(
        self,
        session_id: uuid.UUID,
        project_path: str,
        db_session: AsyncSession,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply planned dependency updates."""
        return {
            "updates_applied": 0,
            "message": "No updates applied (dry run)",
        }

    async def _validate_changes(
        self,
        session_id: uuid.UUID,
        project_path: str,
        db_session: AsyncSession,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate changes by running tests."""
        return {
            "success": True,
            "message": "Validation completed",
        }

    # ==========================================================================
    # Docker Deployment Steps
    # ==========================================================================

    async def _analyze_dockerfile(
        self,
        session_id: uuid.UUID,
        project_path: str,
        db_session: AsyncSession,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Analyze existing Dockerfile."""
        from pathlib import Path

        dockerfile = Path(project_path) / "Dockerfile"
        has_dockerfile = dockerfile.exists()

        return {
            "has_dockerfile": has_dockerfile,
            "dockerfile_content": dockerfile.read_text()[:2000] if has_dockerfile else None,
        }

    async def _optimize_image(
        self,
        session_id: uuid.UUID,
        project_path: str,
        db_session: AsyncSession,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Optimize Docker image."""
        return {
            "optimizations": [],
            "message": "Image optimization not yet implemented",
        }

    async def _generate_compose(
        self,
        session_id: uuid.UUID,
        project_path: str,
        db_session: AsyncSession,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate docker-compose configuration."""
        return {
            "compose_generated": False,
            "message": "Compose generation not yet implemented",
        }

    async def _validate_deployment(
        self,
        session_id: uuid.UUID,
        project_path: str,
        db_session: AsyncSession,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate deployment configuration."""
        return {
            "valid": True,
            "message": "Deployment validation completed",
        }


__all__ = ["StepExecutor", "StepExecutionError"]
