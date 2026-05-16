import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    study_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("studies.id"), nullable=False, index=True
    )
    impression: Mapped[str] = mapped_column(Text, nullable=False, default="")
    icd10_codes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Path on the artifacts volume to the DICOM SR file
    sr_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Hand-built FHIR DiagnosticReport JSON
    fhir_diagnostic_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    signed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # AI free-text clinical narrative (MedGemma). Unverified, research-only.
    clinical_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    narrative_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    narrative_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
