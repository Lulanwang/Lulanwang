import uuid

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Patient(Base, TimestampMixin):
    """De-identified patient record.

    The original DICOM PatientID is never persisted in cleartext. We
    store a stable internal pseudonym and the per-patient date-shift
    so de-identification is reproducible for new studies belonging
    to the same source patient.
    """

    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Hash-based pseudonym (HMAC over original PatientID with site key);
    # stable across studies but not reversible.
    pseudonym: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    # Days to shift all dates for this patient. Preserves intervals.
    date_shift_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Non-identifying demographics retained for cohort analytics.
    sex: Mapped[str | None] = mapped_column(String(8), nullable=True)
    age_band: Mapped[str | None] = mapped_column(String(16), nullable=True)  # e.g. "40-49"
