"""Tests for database CRUD operations using Repository pattern."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import uuid


class TestSessionRepository:
    """Tests for SessionRepository CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_session(self):
        """Should create a new session using repository."""
        from src.db.repository import SessionRepository

        # Mock the async session
        mock_db_session = AsyncMock()
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()

        repo = SessionRepository(mock_db_session)

        # Create session
        result = await repo.create(
            project_path="/test/project",
            status="pending",
            session_type="maven_maintenance"
        )

        assert result is not None
        assert result.project_path == "/test/project"
        mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_session_by_id(self):
        """Should retrieve session by ID using repository."""
        from src.db.repository import SessionRepository
        from src.db.models import Session

        mock_db_session = AsyncMock()
        mock_session = Session(
            project_path="/test/project",
            status="pending",
            session_type="maven_maintenance"
        )
        mock_session.id = uuid.uuid4()
        mock_db_session.get = AsyncMock(return_value=mock_session)

        repo = SessionRepository(mock_db_session)
        result = await repo.get(mock_session.id)

        assert result is not None
        assert result.id == mock_session.id

    @pytest.mark.asyncio
    async def test_get_nonexistent_session_returns_none(self):
        """Should return None for nonexistent session."""
        from src.db.repository import SessionRepository

        mock_db_session = AsyncMock()
        mock_db_session.get = AsyncMock(return_value=None)

        repo = SessionRepository(mock_db_session)
        fake_id = uuid.uuid4()
        result = await repo.get(fake_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_update_session_status(self):
        """Should update session status using repository."""
        from src.db.repository import SessionRepository
        from src.db.models import Session

        mock_db_session = AsyncMock()
        mock_session = Session(
            project_path="/test/project",
            status="pending",
            session_type="maven_maintenance"
        )
        mock_session.id = uuid.uuid4()
        mock_db_session.get = AsyncMock(return_value=mock_session)
        mock_db_session.flush = AsyncMock()

        repo = SessionRepository(mock_db_session)
        result = await repo.update(mock_session.id, status="in_progress")

        assert result is not None
        assert result.status == "in_progress"

    @pytest.mark.asyncio
    async def test_delete_session(self):
        """Should delete session using repository."""
        from src.db.repository import SessionRepository
        from src.db.models import Session

        mock_db_session = AsyncMock()
        mock_session = Session(
            project_path="/test/project",
            status="pending",
            session_type="maven_maintenance"
        )
        mock_session.id = uuid.uuid4()
        mock_db_session.get = AsyncMock(return_value=mock_session)
        mock_db_session.delete = AsyncMock()
        mock_db_session.flush = AsyncMock()

        repo = SessionRepository(mock_db_session)
        result = await repo.delete(mock_session.id)

        assert result is True
        mock_db_session.delete.assert_called_once()


class TestStepRepository:
    """Tests for StepRepository CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_step_for_session(self):
        """Should create step linked to session."""
        from src.db.repository import StepRepository

        mock_db_session = AsyncMock()
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()

        session_id = uuid.uuid4()
        repo = StepRepository(mock_db_session)

        result = await repo.create(
            session_id=session_id,
            name="analyze",
            status="pending",
            sequence=1
        )

        assert result is not None
        assert result.session_id == session_id
        assert result.name == "analyze"

    @pytest.mark.asyncio
    async def test_get_steps_by_session(self):
        """Should list all steps for a session."""
        from src.db.repository import StepRepository
        from src.db.models import Step

        mock_db_session = AsyncMock()
        session_id = uuid.uuid4()

        # Mock query result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [
            Step(session_id=session_id, name="step1", status="pending", sequence=1),
            Step(session_id=session_id, name="step2", status="pending", sequence=2),
        ]
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        repo = StepRepository(mock_db_session)
        result = await repo.get_by_session(session_id)

        assert len(result) == 2
        assert result[0].name == "step1"
        assert result[1].name == "step2"
