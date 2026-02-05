# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 TestBoost Contributors

"""Integration tests for structured logging of data source decisions."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from src.core.step_executor import StepExecutor
from src.lib.logging import log_data_source_decision


@pytest.mark.integration
class TestStructuredLogging:
    """Integration tests for structured logging functionality."""

    @pytest.mark.asyncio
    async def test_log_emitted_for_reuse_case(self, db_session):
        """Test that structured log is emitted with data_source='previous_outputs' when reusing."""
        executor = StepExecutor(db_session)

        # Setup mocks
        mock_session_id = uuid.uuid4()
        previous_outputs = {
            "analyze_project": {
                "source_files": ["file1.py", "file2.py"],
                "source_files_count": 2
            }
        }

        # Capture log calls
        log_calls = []

        def capture_log_info(event, **kwargs):
            """Capture log.info calls."""
            log_calls.append({"event": event, "data": kwargs})

        # Patch logger to capture calls
        with patch('src.lib.logging.get_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_logger.info = capture_log_info
            mock_get_logger.return_value = mock_logger

            # Patch _find_source_files to avoid actual filesystem access
            with patch('src.workflows.test_generation_agent._find_source_files', return_value=[]):
                # Call _identify_coverage_gaps with previous outputs
                await executor._identify_coverage_gaps(
                    session_id=mock_session_id,
                    project_path="/test/project",
                    db_session=db_session,
                    inputs={},
                    previous_outputs=previous_outputs
                )

        # Verify log was emitted
        assert len(log_calls) > 0, "No logs were emitted"

        # Find data_source_decision log
        decision_logs = [call for call in log_calls if call["event"] == "data_source_decision"]
        assert len(decision_logs) == 1, f"Expected 1 data_source_decision log, got {len(decision_logs)}"

        log_data = decision_logs[0]["data"]

        # Verify log structure for reuse case
        assert log_data["step_code"] == "identify_coverage_gaps"
        assert log_data["data_source"] == "previous_outputs"
        assert "reused_from_step" in log_data
        assert log_data["reused_from_step"] == "analyze_project"
        assert "source_files found in previous step outputs" in log_data["reason"]

    @pytest.mark.asyncio
    async def test_log_emitted_for_fresh_compute_case(self, db_session):
        """Test that structured log is emitted with data_source='fresh_compute' when no reuse."""
        executor = StepExecutor(db_session)

        # Setup mocks
        mock_session_id = uuid.uuid4()
        previous_outputs = {}  # Empty - no previous outputs

        # Capture log calls
        log_calls = []

        def capture_log_info(event, **kwargs):
            """Capture log.info calls."""
            log_calls.append({"event": event, "data": kwargs})

        # Patch logger to capture calls
        with patch('src.lib.logging.get_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_logger.info = capture_log_info
            mock_get_logger.return_value = mock_logger

            # Patch _find_source_files to provide fallback data
            with patch('src.workflows.test_generation_agent._find_source_files', return_value=["file1.py"]):
                # Call _identify_coverage_gaps WITHOUT previous outputs
                await executor._identify_coverage_gaps(
                    session_id=mock_session_id,
                    project_path="/test/project",
                    db_session=db_session,
                    inputs={},
                    previous_outputs=previous_outputs
                )

        # Verify log was emitted
        assert len(log_calls) > 0, "No logs were emitted"

        # Find data_source_decision log
        decision_logs = [call for call in log_calls if call["event"] == "data_source_decision"]
        assert len(decision_logs) == 1, f"Expected 1 data_source_decision log, got {len(decision_logs)}"

        log_data = decision_logs[0]["data"]

        # Verify log structure for fresh compute case
        assert log_data["step_code"] == "identify_coverage_gaps"
        assert log_data["data_source"] == "fresh_compute"
        assert "reused_from_step" not in log_data  # Should not be present for fresh compute
        assert "not found in previous_outputs" in log_data["reason"]

    def test_log_data_source_decision_helper_format(self):
        """Test that log_data_source_decision() helper emits correct format."""
        log_calls = []

        def capture_log_info(event, **kwargs):
            """Capture log.info calls."""
            log_calls.append({"event": event, "data": kwargs})

        # Patch logger
        with patch('src.lib.logging.get_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_logger.info = capture_log_info
            mock_get_logger.return_value = mock_logger

            # Test with reuse
            log_data_source_decision(
                step_code="test_step",
                data_source="previous_outputs",
                reason="Test reuse reason",
                reused_from_step="previous_step",
                extra_key="extra_value"
            )

        # Verify log format
        assert len(log_calls) == 1
        log_data = log_calls[0]["data"]

        assert log_data["step_code"] == "test_step"
        assert log_data["data_source"] == "previous_outputs"
        assert log_data["reason"] == "Test reuse reason"
        assert log_data["reused_from_step"] == "previous_step"
        assert log_data["extra_key"] == "extra_value"

    def test_log_data_source_decision_without_reused_from_step(self):
        """Test that log_data_source_decision() works without reused_from_step."""
        log_calls = []

        def capture_log_info(event, **kwargs):
            """Capture log.info calls."""
            log_calls.append({"event": event, "data": kwargs})

        # Patch logger
        with patch('src.lib.logging.get_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_logger.info = capture_log_info
            mock_get_logger.return_value = mock_logger

            # Test without reused_from_step (fresh compute case)
            log_data_source_decision(
                step_code="test_step",
                data_source="fresh_compute",
                reason="No previous data available"
            )

        # Verify log format
        assert len(log_calls) == 1
        log_data = log_calls[0]["data"]

        assert log_data["step_code"] == "test_step"
        assert log_data["data_source"] == "fresh_compute"
        assert log_data["reason"] == "No previous data available"
        assert "reused_from_step" not in log_data  # Should not be present
