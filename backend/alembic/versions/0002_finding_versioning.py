"""Add versioning fields to findings.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-16 12:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # New columns
    op.add_column(
        "findings",
        sa.Column("parent_finding_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "findings",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "findings",
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "findings",
        sa.Column("source", sa.String(16), nullable=False, server_default="ai"),
    )
    op.add_column(
        "findings",
        sa.Column("status", sa.String(16), nullable=False, server_default="proposed"),
    )
    op.add_column(
        "findings",
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "findings",
        sa.Column("seg_sop_instance_uid", sa.String(128), nullable=True),
    )

    # `confidence` becomes nullable so radiologist edits (which have no
    # AI confidence) can be persisted without sentinel values.
    op.alter_column("findings", "confidence", existing_type=sa.Float(), nullable=True)

    # FKs
    op.create_foreign_key(
        "fk_findings_parent", "findings", "findings", ["parent_finding_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_findings_actor", "findings", "users", ["actor_id"], ["id"]
    )

    # Indexes for the two highest-traffic filters
    op.create_index("ix_findings_parent_finding_id", "findings", ["parent_finding_id"])
    op.create_index("ix_findings_is_current", "findings", ["is_current"])


def downgrade() -> None:
    op.drop_index("ix_findings_is_current", table_name="findings")
    op.drop_index("ix_findings_parent_finding_id", table_name="findings")
    op.drop_constraint("fk_findings_actor", "findings", type_="foreignkey")
    op.drop_constraint("fk_findings_parent", "findings", type_="foreignkey")
    op.alter_column("findings", "confidence", existing_type=sa.Float(), nullable=False)
    op.drop_column("findings", "seg_sop_instance_uid")
    op.drop_column("findings", "actor_id")
    op.drop_column("findings", "status")
    op.drop_column("findings", "source")
    op.drop_column("findings", "is_current")
    op.drop_column("findings", "version")
    op.drop_column("findings", "parent_finding_id")
