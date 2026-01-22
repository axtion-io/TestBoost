"""Add metadata JSONB column to artifacts table

Revision ID: 006_add_artifact_metadata
Revises: 602dd0971fff
Create Date: 2026-01-10

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "006_add_artifact_metadata"
down_revision: str | Sequence[str] | None = "602dd0971fff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add metadata JSONB column to artifacts table."""
    op.add_column(
        "artifacts",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove metadata column from artifacts table."""
    op.drop_column("artifacts", "metadata")
