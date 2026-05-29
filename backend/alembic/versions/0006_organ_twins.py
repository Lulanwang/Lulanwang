"""Create organ_twins table for 3D digital twin meshes.

Stores the result of the classical-CV organ + lesion mesh pipeline.
Idempotency is enforced by the unique constraint on
(study_id, seg_config_version): bumping SEG_CONFIG_VERSION in
app/services/twin/config.py invalidates every cached twin.

Revision ID: 0006
Revises: 0005
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organ_twins",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "study_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("studies.id"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id"),
            nullable=True,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("seg_config_version", sa.String(32), nullable=False),
        sa.Column("body_part", sa.String(32), nullable=False),
        sa.Column("glb_path", sa.String(512), nullable=True),
        sa.Column("glb_bytes", sa.Integer(), nullable=True),
        sa.Column("structures", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.String(2048), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "study_id", "seg_config_version", name="uq_twin_study_config"
        ),
    )
    op.create_index(
        "ix_organ_twins_study_id", "organ_twins", ["study_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_organ_twins_study_id", table_name="organ_twins")
    op.drop_table("organ_twins")
