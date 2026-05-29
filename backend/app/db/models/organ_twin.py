import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

# Lifecycle states for a twin generation. Mirrors `Job.status` so the UI
# can read it in one query without joining.
TWIN_STATUSES = ("queued", "running", "succeeded", "failed")


class OrganTwin(Base, TimestampMixin):
    """A research-only 3D mesh reconstruction of the primary organ for a
    study, plus its lesion findings. Stored as a glTF-binary file on the
    artifact volume, with per-structure metadata in JSONB.

    Not a validated anatomical model. The mesh is produced by classical
    computer vision (HU thresholding + Otsu + morphology + marching
    cubes) and is for demonstration only.
    """

    __tablename__ = "organ_twins"
    __table_args__ = (
        # Idempotency: one twin per (study, segmentation config). Bumping
        # SEG_CONFIG_VERSION invalidates the cache for every study.
        UniqueConstraint("study_id", "seg_config_version", name="uq_twin_study_config"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    study_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("studies.id"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=True
    )

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    seg_config_version: Mapped[str] = mapped_column(String(32), nullable=False)
    body_part: Mapped[str] = mapped_column(String(32), nullable=False)

    # Path on the artifact volume (NOT exposed to API consumers — they
    # fetch the binary through GET /twins/{study_id}/model.glb).
    glb_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    glb_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Per-structure metadata as JSONB. Schema:
    # [{name, kind, color, volume_cm3, vertices, faces,
    #   bounds_mm: [[xmin,ymin,zmin],[xmax,ymax,zmax]],
    #   synthetic_marker?: bool, synthetic_extrusion?: bool}]
    structures: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    error: Mapped[str | None] = mapped_column(String(2048), nullable=True)
