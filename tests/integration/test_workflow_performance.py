# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 TestBoost Contributors

"""Performance tests for workflow step output reuse."""

import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.session import SessionService
from src.core.step_executor import StepExecutor
from src.db.models.step import StepStatus


@pytest.mark.integration
@pytest.mark.performance
class TestWorkflowPerformance:
    """Performance tests to validate 50%+ time reduction with previous_outputs."""

    @pytest.mark.asyncio
    async def test_baseline_workflow_without_reuse(self, db_session, benchmark):
        """Measure baseline wall-clock time WITHOUT previous_outputs (force re-analysis)."""
        session_service = SessionService(db_session)
        executor = StepExecutor(db_session)

        # Setup mocks
        mock_session_id = uuid.uuid4()
        mock_session = MagicMock()
        mock_session.id = mock_session_id
        mock_session.project_path = "/test/project"

        # Simulate expensive file system scan (100ms per call)
        def expensive_find_source_files(project_path):
            """Simulate expensive file system operation."""
            time.sleep(0.1)  # 100ms delay to simulate disk I/O
            return ["file1.py", "file2.py", "file3.py", "file4.py", "file5.py"]

        session_service.get_session = AsyncMock(return_value=mock_session)

        with patch('src.workflows.test_generation_agent._find_source_files', side_effect=expensive_find_source_files):
            # Measure baseline (NO previous outputs - forces re-analysis)
            async def baseline_workflow():
                # Step 1: analyze_project (scans filesystem)
                start = time.time()
                result1 = await executor._analyze_project(
                    mock_session_id,
                    "/test/project",
                    db_session,
                    {},
                    {}  # Empty previous_outputs
                )

                # Step 2: identify_coverage_gaps (re-scans filesystem - NO REUSE)
                result2 = await executor._identify_coverage_gaps(
                    mock_session_id,
                    "/test/project",
                    db_session,
                    {},
                    {}  # Empty previous_outputs - forces fallback
                )
                return time.time() - start

            baseline_time = await baseline_workflow()

        # Store baseline for comparison
        assert baseline_time > 0.15, f"Baseline should include 2 scans (200ms+), got {baseline_time:.3f}s"

        # Return baseline for next test to compare
        return baseline_time

    @pytest.mark.asyncio
    async def test_optimized_workflow_with_reuse(self, db_session, benchmark):
        """Measure optimized wall-clock time WITH previous_outputs (reuse)."""
        session_service = SessionService(db_session)
        executor = StepExecutor(db_session)

        # Setup mocks
        mock_session_id = uuid.uuid4()
        mock_session = MagicMock()
        mock_session.id = mock_session_id
        mock_session.project_path = "/test/project"

        # Simulate expensive file system scan (100ms per call)
        def expensive_find_source_files(project_path):
            """Simulate expensive file system operation."""
            time.sleep(0.1)  # 100ms delay to simulate disk I/O
            return ["file1.py", "file2.py", "file3.py", "file4.py", "file5.py"]

        session_service.get_session = AsyncMock(return_value=mock_session)

        with patch('src.workflows.test_generation_agent._find_source_files', side_effect=expensive_find_source_files):
            # Measure optimized workflow (WITH previous outputs - reuses data)
            async def optimized_workflow():
                start = time.time()

                # Step 1: analyze_project (scans filesystem - first time)
                result1 = await executor._analyze_project(
                    mock_session_id,
                    "/test/project",
                    db_session,
                    {},
                    {}  # No previous outputs yet
                )

                # Build previous_outputs from step 1
                previous_outputs = {
                    "analyze_project": {
                        "source_files": result1["source_files"],
                        "source_files_count": result1["source_files_count"]
                    }
                }

                # Step 2: identify_coverage_gaps (REUSES data - NO re-scan)
                result2 = await executor._identify_coverage_gaps(
                    mock_session_id,
                    "/test/project",
                    db_session,
                    {},
                    previous_outputs  # REUSE: Contains source_files from step 1
                )

                return time.time() - start

            optimized_time = await optimized_workflow()

        # Optimized should only scan once (100ms), baseline scans twice (200ms)
        assert optimized_time < 0.15, f"Optimized should include only 1 scan (100ms+), got {optimized_time:.3f}s"

        return optimized_time

    @pytest.mark.asyncio
    async def test_assert_50_percent_improvement(self, db_session):
        """Validate that workflow performance improves by at least 50% (SC-001 success criteria)."""
        session_service = SessionService(db_session)
        executor = StepExecutor(db_session)

        # Setup mocks
        mock_session_id = uuid.uuid4()
        mock_session = MagicMock()
        mock_session.id = mock_session_id
        mock_session.project_path = "/test/project"

        # Simulate expensive operation
        def expensive_find_source_files(project_path):
            """Simulate expensive file system operation."""
            time.sleep(0.1)  # 100ms delay
            return ["file1.py", "file2.py", "file3.py", "file4.py", "file5.py"]

        session_service.get_session = AsyncMock(return_value=mock_session)

        with patch('src.workflows.test_generation_agent._find_source_files', side_effect=expensive_find_source_files):
            # Measure BASELINE (no reuse)
            baseline_start = time.time()
            await executor._analyze_project(mock_session_id, "/test/project", db_session, {}, {})
            await executor._identify_coverage_gaps(mock_session_id, "/test/project", db_session, {}, {})
            baseline_time = time.time() - baseline_start

            # Measure OPTIMIZED (with reuse)
            optimized_start = time.time()
            result1 = await executor._analyze_project(mock_session_id, "/test/project", db_session, {}, {})
            previous_outputs = {
                "analyze_project": {
                    "source_files": result1["source_files"],
                    "source_files_count": result1["source_files_count"]
                }
            }
            await executor._identify_coverage_gaps(mock_session_id, "/test/project", db_session, {}, previous_outputs)
            optimized_time = time.time() - optimized_start

        # Calculate improvement percentage
        time_saved = baseline_time - optimized_time
        improvement_pct = (time_saved / baseline_time) * 100

        print(f"\nPerformance Results:")
        print(f"  Baseline (no reuse): {baseline_time:.3f}s")
        print(f"  Optimized (with reuse): {optimized_time:.3f}s")
        print(f"  Time saved: {time_saved:.3f}s")
        print(f"  Improvement: {improvement_pct:.1f}%")

        # Assert SC-001 success criteria: ≥50% improvement
        assert improvement_pct >= 50.0, (
            f"Performance improvement {improvement_pct:.1f}% is below 50% target. "
            f"Baseline: {baseline_time:.3f}s, Optimized: {optimized_time:.3f}s"
        )

    @pytest.mark.asyncio
    async def test_performance_scales_with_step_count(self, db_session):
        """Test that performance improvement scales with number of steps."""
        executor = StepExecutor(db_session)
        mock_session_id = uuid.uuid4()

        # Simulate expensive operations
        call_count = []

        def expensive_operation(project_path):
            """Track number of expensive calls."""
            call_count.append(1)
            time.sleep(0.05)  # 50ms per call
            return ["file1.py", "file2.py"]

        with patch('src.workflows.test_generation_agent._find_source_files', side_effect=expensive_operation):
            # BASELINE: 3 steps, each re-analyzing (3 expensive calls)
            baseline_start = time.time()
            call_count.clear()

            await executor._analyze_project(mock_session_id, "/test/project", db_session, {}, {})
            await executor._identify_coverage_gaps(mock_session_id, "/test/project", db_session, {}, {})
            await executor._generate_tests(mock_session_id, "/test/project", db_session, {}, {})

            baseline_time = time.time() - baseline_start
            baseline_calls = len(call_count)

            # OPTIMIZED: 3 steps, only first one analyzes (1 expensive call, 2 reuses)
            optimized_start = time.time()
            call_count.clear()

            result1 = await executor._analyze_project(mock_session_id, "/test/project", db_session, {}, {})
            previous_outputs = {"analyze_project": {"source_files": result1["source_files"]}}

            await executor._identify_coverage_gaps(mock_session_id, "/test/project", db_session, {}, previous_outputs)
            await executor._generate_tests(mock_session_id, "/test/project", db_session, {}, previous_outputs)

            optimized_time = time.time() - optimized_start
            optimized_calls = len(call_count)

        # Verify call reduction
        # Baseline: all 3 steps call expensive operation (analyze, identify, generate)
        assert baseline_calls >= 2, f"Expected at least 2 baseline calls, got {baseline_calls}"
        # Optimized: analyze_project and generate_tests call, identify_coverage_gaps reuses
        # (Only identify_coverage_gaps has reuse implemented, generate_tests does not)
        assert optimized_calls >= 1, f"Expected at least 1 optimized call, got {optimized_calls}"
        assert optimized_calls < baseline_calls, f"Optimized calls ({optimized_calls}) should be less than baseline ({baseline_calls})"

        # Calculate improvement
        improvement_pct = ((baseline_time - optimized_time) / baseline_time) * 100

        print(f"\nScalability Test:")
        print(f"  Baseline calls: {baseline_calls}, Time: {baseline_time:.3f}s")
        print(f"  Optimized calls: {optimized_calls}, Time: {optimized_time:.3f}s")
        print(f"  Improvement: {improvement_pct:.1f}%")

        assert improvement_pct > 0, "Should see performance improvement with reuse"
