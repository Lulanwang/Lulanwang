"""Add MedGemma clinical narrative fields to reports.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-16 18:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("clinical_narrative", sa.Text(), nullable=True))
    op.add_column("reports", sa.Column("narrative_model", sa.String(64), nullable=True))
    op.add_column(
        "reports",
        sa.Column("narrative_generated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("reports", "narrative_generated_at")
    op.drop_column("reports", "narrative_model")
    op.drop_column("reports", "clinical_narrative")
