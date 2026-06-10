"""Widen audit_events.resource_id to 512 chars.

Round 11 QA caught a 500 on every WADO instance fetch: the DICOMweb
proxy logs `studies/{uid}/series/{uid}/instances/{uid}` (~156 chars)
into `resource_id`, which was VARCHAR(128). The TX rolled back and the
request 500'd. Widening to 512 fits the full path including the
optional `/frames/N` suffix.

Revision ID: 0005
Revises: 0004
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "audit_events",
        "resource_id",
        existing_type=sa.String(length=128),
        type_=sa.String(length=512),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "audit_events",
        "resource_id",
        existing_type=sa.String(length=512),
        type_=sa.String(length=128),
        existing_nullable=True,
    )
