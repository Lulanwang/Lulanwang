import uuid

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

CONTOUR_TYPES = ("GTV", "CTV", "PTV", "OAR")


class Contour(Base, TimestampMixin):
    """Anatomical contour drawn on the study.

    Geometry is stored as a JSONB blob: a list of {slice_index, points}
    dicts where points is a flat array [x1,y1,x2,y2,...] in image
    coordinates. Volume is the simple-sum approximation in cm³ computed
    at insert time (slice_area_cm² × slice_thickness_cm × #slices).
    """

    __tablename__ = "contours"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    study_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("studies.id"), nullable=False, index=True
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("treatment_plans.id"),
        nullable=True,
        index=True,
    )
    contour_type: Mapped[str] = mapped_column(String(8), nullable=False, default="GTV")
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    color: Mapped[str] = mapped_column(String(16), nullable=False, default="#ef4444")
    geometry: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    volume_cm3: Mapped[float | None] = mapped_column(Float, nullable=True)

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    # When the contour is also persisted as a DICOM RTSTRUCT instance,
    # we record its SOPInstanceUID for download / WADO retrieval.
    rt_sop_instance_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
