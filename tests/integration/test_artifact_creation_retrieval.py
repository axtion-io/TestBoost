# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 TestBoost Contributors

"""Integration tests for artifact creation and retrieval with file_format filtering."""


import pytest

from src.core.session import SessionService


pytest_skip_reason = "Requires real database for integration testing. Mock db_session doesn't persist data."


@pytest.mark.integration
@pytest.mark.skip(reason=pytest_skip_reason)
class TestArtifactCreationRetrieval:
    """Integration tests for artifact file_format functionality."""

    @pytest.mark.asyncio
    async def test_create_artifacts_with_multiple_formats_and_filter(self, db_session):
        """T050: Create artifacts with multiple formats, query with file_format filter."""
        service = SessionService(db_session)

        # Create a test session
        session = await service.create_session(
            session_type="test_generation",
            project_path="/test/project",
        )

        # Create artifacts with different file formats
        await service.create_artifact(
            session_id=session.id,
            name="config.yaml",
            artifact_type="configuration",
            content="key: value\ntest: data\n",
            file_path=f"artifacts/{session.id}/config.yaml",
            file_format="yaml",
        )

        await service.create_artifact(
            session_id=session.id,
            name="data.json",
            artifact_type="data",
            content='{"key": "value", "test": "data"}',
            file_path=f"artifacts/{session.id}/data.json",
            file_format="json",
        )

        await service.create_artifact(
            session_id=session.id,
            name="pom.xml",
            artifact_type="build",
            content='<?xml version="1.0"?>\n<project>\n  <test>data</test>\n</project>\n',
            file_path=f"artifacts/{session.id}/pom.xml",
            file_format="xml",
        )

        await service.create_artifact(
            session_id=session.id,
            name="README.md",
            artifact_type="documentation",
            content="# Test\n\nThis is test documentation.\n",
            file_path=f"artifacts/{session.id}/README.md",
            file_format="md",
        )

        # Query all artifacts (no filter)
        all_artifacts = await service.get_artifacts(session.id)
        assert len(all_artifacts) == 4

        # Query only yaml artifacts
        yaml_artifacts = await service.get_artifacts(session.id, file_format="yaml")
        assert len(yaml_artifacts) == 1
        assert yaml_artifacts[0].file_format == "yaml"
        assert yaml_artifacts[0].name == "config.yaml"

        # Query only xml artifacts
        xml_artifacts = await service.get_artifacts(session.id, file_format="xml")
        assert len(xml_artifacts) == 1
        assert xml_artifacts[0].file_format == "xml"
        assert xml_artifacts[0].name == "pom.xml"

        # Query only json artifacts
        json_artifacts = await service.get_artifacts(session.id, file_format="json")
        assert len(json_artifacts) == 1
        assert json_artifacts[0].file_format == "json"

        # Query only md artifacts
        md_artifacts = await service.get_artifacts(session.id, file_format="md")
        assert len(md_artifacts) == 1
        assert md_artifacts[0].file_format == "md"

        # Query for a format that doesn't exist
        txt_artifacts = await service.get_artifacts(session.id, file_format="txt")
        assert len(txt_artifacts) == 0

    @pytest.mark.asyncio
    async def test_artifact_responses_include_file_format(self, db_session):
        """T051: Verify artifact responses include file_format field."""
        service = SessionService(db_session)

        # Create a test session
        session = await service.create_session(
            session_type="maven_maintenance",
            project_path="/test/project2",
        )

        # Create artifacts with explicit file_format
        await service.create_artifact(
            session_id=session.id,
            name="analysis.yaml",
            artifact_type="analysis",
            content="analysis: results\nstatus: complete\n",
            file_path=f"artifacts/{session.id}/analysis.yaml",
            file_format="yaml",
        )

        # Retrieve the artifact
        artifacts = await service.get_artifacts(session.id)
        assert len(artifacts) == 1

        retrieved = artifacts[0]

        # Verify file_format is present and correct
        assert hasattr(retrieved, "file_format")
        assert retrieved.file_format == "yaml"
        assert retrieved.name == "analysis.yaml"
        assert retrieved.artifact_type == "analysis"

    @pytest.mark.asyncio
    async def test_artifact_defaults_to_json_when_not_specified(self, db_session):
        """T052: Create artifact without file_format, verify defaults to 'json'."""
        service = SessionService(db_session)

        # Create a test session
        session = await service.create_session(
            session_type="docker_deployment",
            project_path="/test/project3",
        )

        # Create artifact without specifying file_format
        # (should default to 'json' at database level)
        await service.create_artifact(
            session_id=session.id,
            name="report",
            artifact_type="report",
            content='{"status": "ok", "count": 42}',
            file_path=f"artifacts/{session.id}/report.json",
            # file_format not specified - should default to "json"
        )

        # Retrieve the artifact
        artifacts = await service.get_artifacts(session.id)
        assert len(artifacts) == 1

        retrieved = artifacts[0]

        # Verify file_format defaults to "json"
        assert retrieved.file_format == "json"
        assert retrieved.name == "report"

    @pytest.mark.asyncio
    async def test_filter_by_both_artifact_type_and_file_format(self, db_session):
        """Test filtering by both artifact_type and file_format simultaneously."""
        service = SessionService(db_session)

        # Create a test session
        session = await service.create_session(
            session_type="test_generation",
            project_path="/test/project4",
        )

        # Create multiple artifacts with different types and formats
        await service.create_artifact(
            session_id=session.id,
            name="analysis1.yaml",
            artifact_type="analysis",
            content="results:\n  - test1: pass\n  - test2: fail\n",
            file_path=f"artifacts/{session.id}/analysis1.yaml",
            file_format="yaml",
        )

        await service.create_artifact(
            session_id=session.id,
            name="analysis2.json",
            artifact_type="analysis",
            content='{"results": ["test1", "test2"], "status": "complete"}',
            file_path=f"artifacts/{session.id}/analysis2.json",
            file_format="json",
        )

        await service.create_artifact(
            session_id=session.id,
            name="report.yaml",
            artifact_type="report",
            content="summary:\n  total: 100\n  passed: 95\n",
            file_path=f"artifacts/{session.id}/report.yaml",
            file_format="yaml",
        )

        # Filter by artifact_type="analysis" only
        analysis_artifacts = await service.get_artifacts(
            session.id,
            artifact_type="analysis",
        )
        assert len(analysis_artifacts) == 2

        # Filter by file_format="yaml" only
        yaml_artifacts = await service.get_artifacts(session.id, file_format="yaml")
        assert len(yaml_artifacts) == 2

        # Filter by both artifact_type="analysis" AND file_format="yaml"
        analysis_yaml = await service.get_artifacts(
            session.id,
            artifact_type="analysis",
            file_format="yaml",
        )
        assert len(analysis_yaml) == 1
        assert analysis_yaml[0].name == "analysis1.yaml"
        assert analysis_yaml[0].artifact_type == "analysis"
        assert analysis_yaml[0].file_format == "yaml"
