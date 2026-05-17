import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

# Lifecycle states for a research treatment plan.
PLAN_STATUSES = ("draft", "approved", "archived")
PLAN_INTENTS = ("curative", "palliative")
PLAN_MODALITIES = ("proton", "photon")


class TreatmentPlan(Base, TimestampMixin):
    """A research-only radiation-therapy plan sketch for a study.

    Not a TPS (treatment planning system). Doses computed here are
    synthetic illustrations from a simplified Gaussian-superposition
    model — not Monte Carlo. Plans cannot be delivered to a real linac
    and are intended for demonstration only.
    """

    __tablename__ = "treatment_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    study_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("studies.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="Draft plan")
    intent: Mapped[str] = mapped_column(String(16), nullable=False, default="curative")
    modality: Mapped[str] = mapped_column(String(16), nullable=False, default="proton")
    prescription_dose_gy: Mapped[float] = mapped_column(
        Float, nullable=False, default=60.0
    )
    fractions: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")

    # JSONB columns hold the malleable structure:
    # beams: list[{id, gantry_angle, couch_angle, collimator_angle, energy_mev, mu, weight}]
    # dose_summary: result of dose_synth.compute() — {oars: {...mean/max/v20}, isocenter, computed_at}
    beams: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    dose_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    signed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
