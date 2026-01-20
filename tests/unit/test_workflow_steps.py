"""Unit tests for workflow step initialization.

Tests verify that sessions are created with the correct workflow steps
based on their session type.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.session import WORKFLOW_STEPS, SessionService


class TestWorkflowStepDefinitions:
    """Tests for WORKFLOW_STEPS constant."""

    def test_maven_maintenance_steps_defined(self):
        """Should have step definitions for maven_maintenance."""
        assert "maven_maintenance" in WORKFLOW_STEPS
        steps = WORKFLOW_STEPS["maven_maintenance"]
        assert len(steps) == 5

        step_codes = [s["code"] for s in steps]
        assert "analyze_dependencies" in step_codes
        assert "identify_vulnerabilities" in step_codes
        assert "plan_updates" in step_codes
        assert "apply_updates" in step_codes
        assert "validate_changes" in step_codes

    def test_test_generation_steps_defined(self):
        """Should have step definitions for test_generation."""
        assert "test_generation" in WORKFLOW_STEPS
        steps = WORKFLOW_STEPS["test_generation"]
        assert len(steps) == 4

        step_codes = [s["code"] for s in steps]
        assert "analyze_project" in step_codes
        assert "identify_coverage_gaps" in step_codes
        assert "generate_tests" in step_codes
        assert "validate_tests" in step_codes

    def test_docker_deployment_steps_defined(self):
        """Should have step definitions for docker_deployment."""
        assert "docker_deployment" in WORKFLOW_STEPS
        steps = WORKFLOW_STEPS["docker_deployment"]
        assert len(steps) == 4

        step_codes = [s["code"] for s in steps]
        assert "analyze_dockerfile" in step_codes
        assert "optimize_image" in step_codes
        assert "generate_compose" in step_codes
        assert "validate_deployment" in step_codes

    def test_step_definitions_have_required_fields(self):
        """All steps should have code, name, and description."""
        for session_type, steps in WORKFLOW_STEPS.items():
            for step in steps:
                assert "code" in step, f"Missing code in {session_type}"
                assert "name" in step, f"Missing name in {session_type}"
                assert "description" in step, f"Missing description in {session_type}"
                assert step["code"], f"Empty code in {session_type}"
                assert step["name"], f"Empty name in {session_type}"


@pytest.mark.asyncio
class TestStepInitialization:
    """Tests for step initialization during session creation."""

    async def test_maven_maintenance_creates_five_steps(self):
        """Creating maven_maintenance session should initialize 5 steps."""
        mock_db = AsyncMock()

        # Track created steps
        created_steps = []

        async def mock_create(**kwargs):
            step = MagicMock()
            step.id = uuid.uuid4()
            step.session_id = kwargs.get("session_id")
            step.code = kwargs.get("code")
            step.name = kwargs.get("name")
            step.sequence = kwargs.get("sequence")
            step.status = kwargs.get("status", "pending")
            created_steps.append(step)
            return step

        with patch("src.core.session.SessionRepository") as MockSessionRepo, \
             patch("src.core.session.StepRepository") as MockStepRepo, \
             patch("src.core.session.EventRepository") as MockEventRepo, \
             patch("src.core.session.ArtifactRepository"):

            # Setup mock session
            mock_session = MagicMock()
            mock_session.id = uuid.uuid4()
            mock_session.project_path = "/test/project"
            MockSessionRepo.return_value.create = AsyncMock(return_value=mock_session)

            # Setup mock step repo
            MockStepRepo.return_value.create = mock_create

            # Setup mock event repo
            MockEventRepo.return_value.create = AsyncMock()

            service = SessionService(mock_db)
            session = await service.create_session(
                session_type="maven_maintenance",
                project_path="/test/project",
                mode="interactive"
            )

            assert session.id == mock_session.id
            assert len(created_steps) == 5

            # Verify step codes
            step_codes = [s.code for s in created_steps]
            assert "analyze_dependencies" in step_codes
            assert "identify_vulnerabilities" in step_codes

            # Verify sequence ordering
            sequences = [s.sequence for s in created_steps]
            assert sequences == [1, 2, 3, 4, 5]

    async def test_test_generation_creates_four_steps(self):
        """Creating test_generation session should initialize 4 steps."""
        mock_db = AsyncMock()
        created_steps = []

        async def mock_create(**kwargs):
            step = MagicMock()
            step.id = uuid.uuid4()
            step.session_id = kwargs.get("session_id")
            step.code = kwargs.get("code")
            step.name = kwargs.get("name")
            step.sequence = kwargs.get("sequence")
            step.status = kwargs.get("status", "pending")
            created_steps.append(step)
            return step

        with patch("src.core.session.SessionRepository") as MockSessionRepo, \
             patch("src.core.session.StepRepository") as MockStepRepo, \
             patch("src.core.session.EventRepository") as MockEventRepo, \
             patch("src.core.session.ArtifactRepository"):

            mock_session = MagicMock()
            mock_session.id = uuid.uuid4()
            mock_session.project_path = "/test/project"
            MockSessionRepo.return_value.create = AsyncMock(return_value=mock_session)
            MockStepRepo.return_value.create = mock_create
            MockEventRepo.return_value.create = AsyncMock()

            service = SessionService(mock_db)
            await service.create_session(
                session_type="test_generation",
                project_path="/test/project",
                mode="interactive"
            )

            assert len(created_steps) == 4
            step_codes = [s.code for s in created_steps]
            assert "analyze_project" in step_codes
            assert "generate_tests" in step_codes

    async def test_unknown_session_type_creates_no_steps(self):
        """Unknown session type should create no steps but not fail."""
        mock_db = AsyncMock()
        created_steps = []

        async def mock_create(**kwargs):
            step = MagicMock()
            step.id = uuid.uuid4()
            created_steps.append(step)
            return step

        with patch("src.core.session.SessionRepository") as MockSessionRepo, \
             patch("src.core.session.StepRepository") as MockStepRepo, \
             patch("src.core.session.EventRepository") as MockEventRepo, \
             patch("src.core.session.ArtifactRepository"):

            mock_session = MagicMock()
            mock_session.id = uuid.uuid4()
            mock_session.project_path = "/test/project"
            MockSessionRepo.return_value.create = AsyncMock(return_value=mock_session)
            MockStepRepo.return_value.create = mock_create
            MockEventRepo.return_value.create = AsyncMock()

            service = SessionService(mock_db)
            session = await service.create_session(
                session_type="unknown_type",
                project_path="/test/project",
                mode="interactive"
            )

            # Should complete without error
            assert session is not None
            # No steps should be created for unknown type
            assert len(created_steps) == 0

    async def test_steps_created_with_pending_status(self):
        """All initialized steps should have 'pending' status."""
        mock_db = AsyncMock()
        created_steps = []

        async def mock_create(**kwargs):
            step = MagicMock()
            step.id = uuid.uuid4()
            step.status = kwargs.get("status")
            created_steps.append(step)
            return step

        with patch("src.core.session.SessionRepository") as MockSessionRepo, \
             patch("src.core.session.StepRepository") as MockStepRepo, \
             patch("src.core.session.EventRepository") as MockEventRepo, \
             patch("src.core.session.ArtifactRepository"):

            mock_session = MagicMock()
            mock_session.id = uuid.uuid4()
            mock_session.project_path = "/test/project"
            MockSessionRepo.return_value.create = AsyncMock(return_value=mock_session)
            MockStepRepo.return_value.create = mock_create
            MockEventRepo.return_value.create = AsyncMock()

            service = SessionService(mock_db)
            await service.create_session(
                session_type="docker_deployment",
                project_path="/test/project",
                mode="interactive"
            )

            for step in created_steps:
                assert step.status == "pending"

    async def test_steps_have_description_in_inputs(self):
        """Steps should include description in their inputs."""
        mock_db = AsyncMock()
        created_steps = []

        async def mock_create(**kwargs):
            step = MagicMock()
            step.id = uuid.uuid4()
            step.inputs = kwargs.get("inputs", {})
            created_steps.append(step)
            return step

        with patch("src.core.session.SessionRepository") as MockSessionRepo, \
             patch("src.core.session.StepRepository") as MockStepRepo, \
             patch("src.core.session.EventRepository") as MockEventRepo, \
             patch("src.core.session.ArtifactRepository"):

            mock_session = MagicMock()
            mock_session.id = uuid.uuid4()
            mock_session.project_path = "/test/project"
            MockSessionRepo.return_value.create = AsyncMock(return_value=mock_session)
            MockStepRepo.return_value.create = mock_create
            MockEventRepo.return_value.create = AsyncMock()

            service = SessionService(mock_db)
            await service.create_session(
                session_type="maven_maintenance",
                project_path="/test/project",
                mode="interactive"
            )

            for step in created_steps:
                assert "description" in step.inputs
                assert step.inputs["description"]  # Should not be empty
