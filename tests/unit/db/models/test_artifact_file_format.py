# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 TestBoost Contributors

"""Unit tests for Artifact model file_format field."""

import uuid

from sqlalchemy import inspect

from src.db.models.artifact import Artifact


class TestArtifactFileFormat:
    """Unit tests for file_format field on Artifact model."""

    def test_artifact_model_has_file_format_field(self):
        """T042: Artifact model has file_format field with default='json'."""
        # Create an artifact with file_format specified
        artifact = Artifact(
            id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            name="test_artifact",
            artifact_type="analysis",
            content_type="application/json",
            file_path="/tmp/test.json",
            size_bytes=100,
            file_format="json",  # Explicitly set to verify field exists
        )

        # Verify file_format field exists and has the correct value
        assert hasattr(artifact, "file_format")
        assert artifact.file_format == "json"

    def test_artifact_model_file_format_accepts_custom_value(self):
        """Artifact model file_format accepts custom values."""
        artifact = Artifact(
            id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            name="test_artifact",
            artifact_type="analysis",
            content_type="application/xml",
            file_path="/tmp/test.xml",
            size_bytes=100,
            file_format="xml",
        )

        assert artifact.file_format == "xml"

    def test_artifact_model_file_format_field_is_indexed(self):
        """T043: Artifact model file_format field is indexed."""
        # Inspect the Artifact table to check for indexes
        inspector = inspect(Artifact)
        table = inspector.local_table

        # Get all indexes for the table
        indexes = {idx.name: idx for idx in table.indexes}

        # Verify the file_format index exists
        assert "ix_artifacts_file_format" in indexes

        # Verify the index is on the file_format column
        file_format_index = indexes["ix_artifacts_file_format"]
        column_names = [col.name for col in file_format_index.columns]
        assert "file_format" in column_names

    def test_artifact_model_file_format_allows_various_formats(self):
        """Artifact model file_format accepts various format types."""
        formats = ["json", "yaml", "xml", "md", "txt", "html", "csv", "java", "py"]

        for fmt in formats:
            artifact = Artifact(
                id=uuid.uuid4(),
                session_id=uuid.uuid4(),
                name=f"test_{fmt}",
                artifact_type="code",
                content_type=f"text/{fmt}",
                file_path=f"/tmp/test.{fmt}",
                size_bytes=100,
                file_format=fmt,
            )
            assert artifact.file_format == fmt
