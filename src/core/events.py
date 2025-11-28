"""Event sourcing service for audit trail."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Event
from src.db.repository import EventRepository
from src.lib.logging import get_logger

logger = get_logger(__name__)


class EventService:
    """Service for managing workflow events."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = EventRepository(session)

    async def emit(
        self,
        session_id: uuid.UUID,
        event_type: str,
        event_data: dict[str, Any] | None = None,
        step_id: uuid.UUID | None = None,
        message: str | None = None,
    ) -> Event:
        """Emit a new event."""
        event = await self.repository.create(
            session_id=session_id,
            step_id=step_id,
            event_type=event_type,
            event_data=event_data or {},
            message=message,
            timestamp=datetime.utcnow(),
        )

        logger.info(
            "event_emitted",
            session_id=str(session_id),
            event_type=event_type,
            step_id=str(step_id) if step_id else None,
        )

        return event

    async def get_events(
        self,
        session_id: uuid.UUID,
        event_type: str | None = None,
    ) -> list[Event]:
        """Get events for a session, optionally filtered by type."""
        events = await self.repository.get_by_session(session_id)

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        return events

    async def get_latest(
        self,
        session_id: uuid.UUID,
        event_type: str | None = None,
    ) -> Event | None:
        """Get the most recent event for a session."""
        events = await self.get_events(session_id, event_type)
        return events[-1] if events else None
