"""Workflow executor for LangGraph state machines."""

import uuid
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.events import EventService
from src.db.models.session import SessionStatus
from src.db.repository import SessionRepository, StepRepository
from src.lib.logging import get_logger
from src.workflows.state import WorkflowState

logger = get_logger(__name__)


class WorkflowExecutor:
    """Execute LangGraph workflows with event tracking and checkpointing."""

    def __init__(
        self,
        session: AsyncSession,
        graph: StateGraph[Any],
        checkpointer: BaseCheckpointSaver[Any] | None = None,
    ):
        """Initialize workflow executor.

        Args:
            session: Database session
            graph: Compiled LangGraph StateGraph
            checkpointer: Optional checkpoint saver for persistence
        """
        self.db_session = session
        self.graph = graph
        self.checkpointer = checkpointer
        self.session_repo = SessionRepository(session)
        self.step_repo = StepRepository(session)
        self.event_service = EventService(session)

    async def execute(
        self,
        session_id: uuid.UUID,
        initial_state: WorkflowState,
        config: dict[str, Any] | None = None,
    ) -> WorkflowState:
        """Execute workflow from initial state.

        Args:
            session_id: Session identifier
            initial_state: Starting workflow state
            config: Optional LangGraph config

        Returns:
            Final workflow state
        """
        logger.info(
            "workflow_execution_started",
            session_id=str(session_id),
            initial_step=initial_state.get("current_step"),
        )

        # Update session status
        await self.session_repo.update(
            session_id,
            status=SessionStatus.IN_PROGRESS.value,
        )

        # Emit start event
        await self.event_service.emit(
            session_id=session_id,
            event_type="workflow_started",
            event_data={"initial_step": initial_state.get("current_step")},
        )

        try:
            # Compile graph with checkpointer if provided
            compiled = self.graph.compile(checkpointer=self.checkpointer)

            # Build config
            run_config = config or {}
            if self.checkpointer:
                run_config["configurable"] = {
                    "thread_id": str(session_id),
                    **run_config.get("configurable", {}),
                }

            # Execute workflow
            final_state = await compiled.ainvoke(
                initial_state, run_config  # type: ignore[arg-type]
            )

            # Handle completion
            await self._handle_completion(session_id, final_state)  # type: ignore[arg-type]
            return final_state  # type: ignore[return-value]

        except Exception as e:
            await self._handle_error(session_id, dict(initial_state), e)
            raise

    async def resume(
        self,
        session_id: uuid.UUID,
        checkpoint_id: str,
        updated_state: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
    ) -> WorkflowState:
        """Resume workflow from checkpoint.

        Args:
            session_id: Session identifier
            checkpoint_id: Checkpoint to resume from
            updated_state: Optional state updates
            config: Optional LangGraph config

        Returns:
            Final workflow state
        """
        if not self.checkpointer:
            raise ValueError("Checkpointer required for resume")

        logger.info(
            "workflow_resume_started",
            session_id=str(session_id),
            checkpoint_id=checkpoint_id,
        )

        # Update session status
        await self.session_repo.update(
            session_id,
            status=SessionStatus.IN_PROGRESS.value,
        )

        # Emit resume event
        await self.event_service.emit(
            session_id=session_id,
            event_type="workflow_resumed",
            event_data={
                "checkpoint_id": checkpoint_id,
                "updated_state": updated_state,
            },
        )

        try:
            # Compile graph with checkpointer
            compiled = self.graph.compile(checkpointer=self.checkpointer)

            # Build config
            run_config = config or {}
            run_config["configurable"] = {
                "thread_id": str(session_id),
                "checkpoint_id": checkpoint_id,
                **run_config.get("configurable", {}),
            }

            # Resume execution
            final_state = await compiled.ainvoke(
                updated_state, run_config  # type: ignore[arg-type]
            )

            # Handle completion
            await self._handle_completion(session_id, final_state)  # type: ignore[arg-type]
            return final_state  # type: ignore[return-value]

        except Exception as e:
            await self._handle_error(session_id, {}, e)
            raise

    async def pause(
        self,
        session_id: uuid.UUID,
        state: WorkflowState,
        reason: str | None = None,
    ) -> str:
        """Pause workflow and save checkpoint.

        Args:
            session_id: Session identifier
            state: Current workflow state
            reason: Optional pause reason

        Returns:
            Checkpoint ID
        """
        if not self.checkpointer:
            raise ValueError("Checkpointer required for pause")

        logger.info(
            "workflow_paused",
            session_id=str(session_id),
            current_step=state.get("current_step"),
            reason=reason,
        )

        # Update session status
        await self.session_repo.update(
            session_id,
            status=SessionStatus.PAUSED.value,
        )

        # Emit pause event
        await self.event_service.emit(
            session_id=session_id,
            event_type="workflow_paused",
            event_data={
                "current_step": state.get("current_step"),
                "reason": reason,
            },
        )

        # Return checkpoint ID (would be set by checkpointer)
        checkpoint_id = state.get("checkpoint_id")
        return checkpoint_id if checkpoint_id is not None else str(uuid.uuid4())

    async def _handle_completion(
        self,
        session_id: uuid.UUID,
        final_state: WorkflowState,
    ) -> None:
        """Handle workflow completion."""
        error = final_state.get("error")

        if error:
            status = SessionStatus.FAILED.value
            event_type = "workflow_failed"
        else:
            status = SessionStatus.COMPLETED.value
            event_type = "workflow_completed"

        # Update session
        await self.session_repo.update(
            session_id,
            status=status,
            result=final_state.get("output_data"),
            error_message=error,
        )

        # Emit completion event
        await self.event_service.emit(
            session_id=session_id,
            event_type=event_type,
            event_data={
                "final_step": final_state.get("current_step"),
                "results_count": len(final_state.get("results", [])),
                "artifacts_count": len(final_state.get("artifacts", [])),
            },
        )

        logger.info(
            event_type,
            session_id=str(session_id),
            final_step=final_state.get("current_step"),
        )

    async def _handle_error(
        self,
        session_id: uuid.UUID,
        state: dict[str, Any],
        error: Exception,
    ) -> None:
        """Handle workflow error."""
        error_message = str(error)

        # Update session
        await self.session_repo.update(
            session_id,
            status=SessionStatus.FAILED.value,
            error_message=error_message,
        )

        # Emit error event
        await self.event_service.emit(
            session_id=session_id,
            event_type="workflow_error",
            event_data={
                "error": error_message,
                "current_step": state.get("current_step"),
            },
        )

        logger.error(
            "workflow_error",
            session_id=str(session_id),
            error=error_message,
            current_step=state.get("current_step"),
        )


__all__ = ["WorkflowExecutor"]
