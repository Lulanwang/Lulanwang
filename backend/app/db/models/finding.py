import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

# Source of a finding row:
#   "ai"          — created by an AI adapter, never mutated after creation
#   "radiologist" — created by a human refinement on top of an AI finding
SOURCES = ("ai", "radiologist")

# Status — drives what shows up in the signed report and the worklist badge.
#   "proposed"  — AI's initial output, awaiting review
#   "accepted"  — radiologist accepted AI's output as-is
#   "rejected"  — radiologist marked AI's output as a false positive
#   "modified"  — radiologist redrew / refined; this row carries the refined geometry
STATUSES = ("proposed", "accepted", "rejected", "modified")


class Finding(Base, TimestampMixin):
    """Versioned finding row.

    AI rows (`source="ai"`) are immutable after creation; only their
    `status` and `is_current` may change. Radiologist refinements append a
    new row that points back at its parent via `parent_finding_id` and
    bumps `version`. The original AI geometry is therefore always
    preserved and queryable for QA, audit, and AI improvement loops.
    """

    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    study_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("studies.id"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=True
    )

    # Versioning
    parent_finding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("findings.id"), nullable=True, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="ai")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="proposed")
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    label: Mapped[str] = mapped_column(String(128), nullable=False)
    body_part: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    icd10_suggestion: Mapped[str | None] = mapped_column(String(16), nullable=True)
    geometry: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)

    # If the geometry is persisted as a DICOM SEG instance in Orthanc,
    # this is its SOPInstanceUID. nullable because not every refinement
    # produces a SEG (e.g., simple bbox-only edits).
    seg_sop_instance_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
