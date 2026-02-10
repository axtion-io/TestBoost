# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 TestBoost Contributors

"""Integration tests for step output flow and previous_outputs passing."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.session import SessionService
from src.core.step_executor import StepExecutor
from src.db.models.step import StepStatus


@pytest.mark.integration
class TestStepOutputFlow:
    """Integration tests for step-to-step output passing."""

    @pytest.mark.asyncio
    async def test_execute_analyze_identify_sequence_passes_outputs(self, db_session):
        """Test that analyze_project → identify_coverage_gaps passes previous_outputs correctly."""
        # Create executor
        executor = StepExecutor(db_session)

        # Mock session and steps
        mock_session_id = uuid.uuid4()
        mock_session = MagicMock()
        mock_session.id = mock_session_id
        mock_session.project_path = "/test/project"
        mock_session.session_type = "test_generation"

        # Mock analyze_project step
        mock_step1 = MagicMock()
        mock_step1.id = uuid.uuid4()
        mock_step1.code = "analyze_project"
        mock_step1.status = StepStatus.COMPLETED.value
        mock_step1.outputs = {
            "source_files": ["file1.py", "file2.py", "file3.py"],
            "source_files_count": 3,
            "project_path": "/test/project"
        }

        # Mock identify_coverage_gaps step (pending)
        mock_step2 = MagicMock()
        mock_step2.id = uuid.uuid4()
        mock_step2.code = "identify_coverage_gaps"
        mock_step2.name = "Identify Coverage Gaps"
        mock_step2.status = StepStatus.PENDING.value

        # Setup mocks on executor's session_service
        executor.session_service.get_session = AsyncMock(return_value=mock_session)
        executor.session_service.get_step_by_code = AsyncMock(return_value=mock_step2)
        executor.session_service.get_steps = AsyncMock(return_value=[mock_step1])  # Return completed step
        executor.session_service.update_step_status = AsyncMock()

        # Track what previous_outputs was passed to workflow function
        captured_previous_outputs = {}

        async def mock_workflow_fn(session_id, project_path, db_session, inputs, previous_outputs):
            """Capture previous_outputs for verification."""
            nonlocal captured_previous_outputs
            captured_previous_outputs = previous_outputs
            return {
                "files_needing_tests": 2,
                "coverage_gaps": ["file1.py", "file2.py"]
            }

        # Patch workflow function lookup
        with patch.object(executor, '_get_workflow_function', return_value=mock_workflow_fn):
            # Execute identify_coverage_gaps step
            result = await executor._execute_step_async(
                mock_session_id,
                "identify_coverage_gaps",
                "test_generation",
                {}
            )

        # Verify previous_outputs was built and passed correctly
        assert "analyze_project" in captured_previous_outputs
        assert captured_previous_outputs["analyze_project"]["source_files"] == [
            "file1.py", "file2.py", "file3.py"
        ]
        assert captured_previous_outputs["analyze_project"]["source_files_count"] == 3

        # Verify step completed successfully
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_identify_coverage_gaps_reuses_source_files(self, db_session):
        """Test that _identify_coverage_gaps() reuses source_files from previous_outputs."""
        executor = StepExecutor(db_session)

        # Setup mocks
        mock_session_id = uuid.uuid4()
        mock_session = MagicMock()
        mock_session.id = mock_session_id
        mock_session.project_path = "/test/project"

        # Mock previous outputs with source_files
        previous_outputs = {
            "analyze_project": {
                "source_files": ["file1.py", "file2.py"],
                "source_files_count": 2
            }
        }

        # Track if _find_source_files was called (shouldn't be if reusing)
        find_source_files_called = []

        def mock_find_source_files(project_path):
            """Track if this fallback was called."""
            find_source_files_called.append(True)
            return ["fallback_file.py"]

        # Patch _find_source_files to detect if it's called
        with patch('src.workflows.test_generation_agent._find_source_files', side_effect=mock_find_source_files):
            # Call _identify_coverage_gaps directly
            result = await executor._identify_coverage_gaps(
                session_id=mock_session_id,
                project_path="/test/project",
                db_session=db_session,
                inputs={},
                previous_outputs=previous_outputs
            )

        # Verify source_files were reused (not re-scanned)
        assert len(find_source_files_called) == 0, "_find_source_files should not be called when reusing"
        assert result["files_needing_tests"] == 2
        assert result["coverage_gaps"] == ["file1.py", "file2.py"]

    @pytest.mark.asyncio
    async def test_identify_coverage_gaps_fallback_when_no_previous_outputs(self, db_session):
        """Test that _identify_coverage_gaps() falls back to re-analysis when no previous outputs."""
        executor = StepExecutor(db_session)

        # Setup mocks
        mock_session_id = uuid.uuid4()

        # Empty previous outputs
        previous_outputs = {}

        # Track if _find_source_files was called (should be for fallback)
        find_source_files_called = []

        def mock_find_source_files(project_path):
            """Return mock files for fallback."""
            find_source_files_called.append(True)
            return ["file1.py", "file2.py", "file3.py"]

        # Patch _find_source_files to detect if it's called
        with patch('src.workflows.test_generation_agent._find_source_files', side_effect=mock_find_source_files):
            # Call _identify_coverage_gaps directly
            result = await executor._identify_coverage_gaps(
                session_id=mock_session_id,
                project_path="/test/project",
                db_session=db_session,
                inputs={},
                previous_outputs=previous_outputs
            )

        # Verify fallback was triggered
        assert len(find_source_files_called) == 1, "_find_source_files should be called for fallback"
        assert result["files_needing_tests"] == 3
        assert result["coverage_gaps"] == ["file1.py", "file2.py", "file3.py"]

    @pytest.mark.asyncio
    async def test_multiple_steps_accumulate_previous_outputs(self, db_session):
        """Test that previous_outputs accumulates all prior step outputs."""
        session_service = SessionService(db_session)
        executor = StepExecutor(db_session)

        mock_session_id = uuid.uuid4()

        # Mock multiple completed steps
        mock_step1 = MagicMock()
        mock_step1.code = "analyze_project"
        mock_step1.outputs = {"source_files": ["file1.py"], "count": 1}

        mock_step2 = MagicMock()
        mock_step2.code = "identify_coverage_gaps"
        mock_step2.outputs = {"files_needing_tests": 1, "gaps": ["file1.py"]}

        mock_step3 = MagicMock()
        mock_step3.code = "generate_tests"
        mock_step3.outputs = {"tests_generated": 5}

        # Mock get_steps to return all completed steps
        session_service.get_steps = AsyncMock(return_value=[mock_step1, mock_step2, mock_step3])
        executor.session_service = session_service

        # Build previous outputs
        previous_outputs = await executor._build_previous_outputs(mock_session_id)

        # Verify all steps are included
        assert len(previous_outputs) == 3
        assert "analyze_project" in previous_outputs
        assert "identify_coverage_gaps" in previous_outputs
        assert "generate_tests" in previous_outputs

        # Verify content
        assert previous_outputs["analyze_project"]["count"] == 1
        assert previous_outputs["identify_coverage_gaps"]["files_needing_tests"] == 1
        assert previous_outputs["generate_tests"]["tests_generated"] == 5
