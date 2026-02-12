"""Add file_format column to artifacts table

Revision ID: 007_add_artifact_file_format
Revises: 006_add_artifact_metadata
Create Date: 2026-02-04 21:45:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '007_add_artifact_file_format'
down_revision = '006_add_artifact_metadata'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add file_format column with default value and index.

    This migration adds the file_format field to support explicit format typing
    for artifacts (json, yaml, xml, java, txt, md, etc.) to enable:
    - API filtering by format
    - Proper artifact rendering in UIs
    - Format-aware artifact processing

    The column uses server_default to avoid table rewrite on PostgreSQL.
    All existing artifacts will have file_format='json' by default.
    """
    # Step 1: Add column with server-side default (efficient for large tables)
    op.add_column(
        'artifacts',
        sa.Column(
            'file_format',
            sa.String(length=20),
            nullable=False,
            server_default='json',  # PostgreSQL server-side default for existing rows
            comment='File format type: json, yaml, xml, java, py, txt, md, html, csv, etc.'
        )
    )

    # Step 2: Create index for efficient filtering queries
    op.create_index(
        'ix_artifacts_file_format',
        'artifacts',
        ['file_format'],
        unique=False
    )


def downgrade() -> None:
    """Remove file_format column and index.

    This will remove all file_format data. Only use in development/testing.
    DO NOT run in production without backup.
    """
    # Step 1: Drop index first (required before dropping column)
    op.drop_index('ix_artifacts_file_format', table_name='artifacts')

    # Step 2: Drop column
    op.drop_column('artifacts', 'file_format')
