import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

# State machine for the study lifecycle. The pipeline advances
# studies through these states; the worklist shows progress.
STUDY_STATES = (
    "received",
    "deidentified",
    "queued",
    "inferring",
    "inferred",
    "reported",
    "signed",
    "failed",
)


class Study(Base, TimestampMixin):
    __tablename__ = "studies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True
    )
    study_instance_uid: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True
    )
    modality: Mapped[str] = mapped_column(String(16), nullable=False)  # CT, MR, MG, CR, DX
    body_part: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    study_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="received")
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(String(1024), nullable=True)
