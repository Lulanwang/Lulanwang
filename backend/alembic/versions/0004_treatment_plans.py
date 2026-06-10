"""Add treatment_plans + contours.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-17 02:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "treatment_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "study_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("studies.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(128), nullable=False, server_default="Draft plan"),
        sa.Column("intent", sa.String(16), nullable=False, server_default="curative"),
        sa.Column("modality", sa.String(16), nullable=False, server_default="proton"),
        sa.Column(
            "prescription_dose_gy",
            sa.Float(),
            nullable=False,
            server_default="60.0",
        ),
        sa.Column("fractions", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("beams", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "dose_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "signed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_treatment_plans_study_id", "treatment_plans", ["study_id"]
    )

    op.create_table(
        "contours",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "study_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("studies.id"),
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("treatment_plans.id"),
            nullable=True,
        ),
        sa.Column("contour_type", sa.String(8), nullable=False, server_default="GTV"),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("color", sa.String(16), nullable=False, server_default="#ef4444"),
        sa.Column("geometry", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("volume_cm3", sa.Float(), nullable=True),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("rt_sop_instance_uid", sa.String(128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_contours_study_id", "contours", ["study_id"])
    op.create_index("ix_contours_plan_id", "contours", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_contours_plan_id", table_name="contours")
    op.drop_index("ix_contours_study_id", table_name="contours")
    op.drop_table("contours")
    op.drop_index("ix_treatment_plans_study_id", table_name="treatment_plans")
    op.drop_table("treatment_plans")
