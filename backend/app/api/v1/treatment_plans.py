"""Treatment-planning workspace — RESEARCH USE ONLY.

The artifacts produced here (TreatmentPlan, Contour, dose summaries)
are not deliverable to a real linac. The system is not a TPS. The DICOM
RTSTRUCT/RTPLAN export tags every artifact with a research-only
ContentCreatorName so downstream viewers see the disclaimer.
"""
from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.security import current_user
from app.db.models.contour import Contour
from app.db.models.study import Study
from app.db.models.treatment_plan import TreatmentPlan
from app.db.models.user import User
from app.db.session import get_db
from app.services import dose_synth, oar_constraints

router = APIRouter(prefix="/treatment-plans", tags=["treatment-plans"])


# ---------- Pydantic shapes ----------


class BeamIn(BaseModel):
    id: str | None = None
    gantry_angle: float = 0.0
    couch_angle: float = 0.0
    collimator_angle: float = 0.0
    energy_mev: float = 6.0
    mu: float = 100.0
    weight: float = 1.0


class PlanCreate(BaseModel):
    study_id: uuid.UUID
    name: str = "Draft plan"
    intent: Literal["curative", "palliative"] = "curative"
    modality: Literal["proton", "photon"] = "proton"
    prescription_dose_gy: float = Field(60.0, gt=0)
    fractions: int = Field(30, gt=0)


class PlanPatch(BaseModel):
    name: str | None = None
    intent: Literal["curative", "palliative"] | None = None
    modality: Literal["proton", "photon"] | None = None
    prescription_dose_gy: float | None = Field(None, gt=0)
    fractions: int | None = Field(None, gt=0)
    notes: str | None = None
    beams: list[BeamIn] | None = None


class PlanOut(BaseModel):
    id: str
    study_id: str
    name: str
    intent: str
    modality: str
    prescription_dose_gy: float
    fractions: int
    notes: str | None
    status: str
    beams: list[dict] | None
    dose_summary: dict | None
    signed_by: str | None
    signed_at: str | None


class ContourCreate(BaseModel):
    contour_type: Literal["GTV", "CTV", "PTV", "OAR"]
    name: str
    color: str = "#ef4444"
    geometry: list[dict] | None = None
    volume_cm3: float | None = None


class ContourOut(BaseModel):
    id: str
    study_id: str
    plan_id: str | None
    contour_type: str
    name: str
    color: str
    geometry: list[dict] | None
    volume_cm3: float | None
    rt_sop_instance_uid: str | None


# ---------- helpers ----------


def _plan_out(p: TreatmentPlan) -> PlanOut:
    return PlanOut(
        id=str(p.id),
        study_id=str(p.study_id),
        name=p.name,
        intent=p.intent,
        modality=p.modality,
        prescription_dose_gy=p.prescription_dose_gy,
        fractions=p.fractions,
        notes=p.notes,
        status=p.status,
        beams=p.beams or [],
        dose_summary=p.dose_summary,
        signed_by=str(p.signed_by) if p.signed_by else None,
        signed_at=p.signed_at.isoformat() if p.signed_at else None,
    )


def _contour_out(c: Contour) -> ContourOut:
    return ContourOut(
        id=str(c.id),
        study_id=str(c.study_id),
        plan_id=str(c.plan_id) if c.plan_id else None,
        contour_type=c.contour_type,
        name=c.name,
        color=c.color,
        geometry=c.geometry,
        volume_cm3=c.volume_cm3,
        rt_sop_instance_uid=c.rt_sop_instance_uid,
    )


# ---------- endpoints ----------


@router.get("/", response_model=list[PlanOut])
def list_plans(
    study_id: uuid.UUID | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[PlanOut]:
    q = db.query(TreatmentPlan)
    if study_id:
        q = q.filter(TreatmentPlan.study_id == study_id)
    rows = q.order_by(TreatmentPlan.created_at.desc()).limit(200).all()
    return [_plan_out(p) for p in rows]


@router.post("/", response_model=PlanOut, status_code=201)
def create_plan(
    payload: PlanCreate,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> PlanOut:
    study = db.get(Study, payload.study_id)
    if study is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "study not found")
    plan = TreatmentPlan(
        study_id=payload.study_id,
        name=payload.name,
        intent=payload.intent,
        modality=payload.modality,
        prescription_dose_gy=payload.prescription_dose_gy,
        fractions=payload.fractions,
        beams=[],
        created_by=user.id,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="plan.created",
        resource_type="treatment_plan",
        resource_id=str(plan.id),
        request_id=request.headers.get("x-request-id"),
        details={"study_id": str(plan.study_id)},
    )
    return _plan_out(plan)


@router.get("/{plan_id}", response_model=PlanOut)
def get_plan(
    plan_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> PlanOut:
    plan = db.get(TreatmentPlan, plan_id)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "plan not found")
    return _plan_out(plan)


@router.patch("/{plan_id}", response_model=PlanOut)
def patch_plan(
    plan_id: uuid.UUID,
    payload: PlanPatch,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> PlanOut:
    plan = db.get(TreatmentPlan, plan_id)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "plan not found")
    if plan.status == "archived":
        raise HTTPException(status.HTTP_409_CONFLICT, "archived plans are read-only")

    changed: dict = {}
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "beams" and value is not None:
            plan.beams = [b if isinstance(b, dict) else b.model_dump() for b in value]
            changed["beams"] = len(value)
        elif value is not None:
            setattr(plan, field, value)
            changed[field] = value

    db.commit()
    db.refresh(plan)
    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="plan.updated",
        resource_type="treatment_plan",
        resource_id=str(plan.id),
        request_id=request.headers.get("x-request-id"),
        details=changed,
    )
    return _plan_out(plan)


@router.post("/{plan_id}/approve", response_model=PlanOut)
def approve_plan(
    plan_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> PlanOut:
    from datetime import datetime, timezone

    plan = db.get(TreatmentPlan, plan_id)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "plan not found")
    plan.status = "approved"
    plan.signed_by = user.id
    plan.signed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(plan)
    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="plan.approved",
        resource_type="treatment_plan",
        resource_id=str(plan.id),
        request_id=request.headers.get("x-request-id"),
    )
    return _plan_out(plan)


@router.post("/{plan_id}/compute-dose", response_model=PlanOut)
def compute_dose(
    plan_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> PlanOut:
    plan = db.get(TreatmentPlan, plan_id)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "plan not found")
    if not plan.beams:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "plan has no beams — add at least one before computing dose",
        )

    # Synthetic dose with no real OAR masks (UI may attach later).
    summary = dose_synth.compute(
        beams=plan.beams,
        modality=plan.modality,
        prescription_dose_gy=plan.prescription_dose_gy,
    )
    plan.dose_summary = summary
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(plan, "dose_summary")
    db.commit()
    db.refresh(plan)
    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="plan.dose_computed",
        resource_type="treatment_plan",
        resource_id=str(plan.id),
        request_id=request.headers.get("x-request-id"),
        details={
            "global_max": summary.get("global", {}).get("max"),
            "global_mean": summary.get("global", {}).get("mean"),
            "modality": plan.modality,
        },
    )
    return _plan_out(plan)


# ---------- contour endpoints ----------


@router.get("/{plan_id}/contours", response_model=list[ContourOut])
def list_contours(
    plan_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[ContourOut]:
    rows = (
        db.query(Contour)
        .filter(Contour.plan_id == plan_id)
        .order_by(Contour.created_at.asc())
        .all()
    )
    return [_contour_out(c) for c in rows]


@router.post("/{plan_id}/contours", response_model=ContourOut, status_code=201)
def add_contour(
    plan_id: uuid.UUID,
    payload: ContourCreate,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ContourOut:
    plan = db.get(TreatmentPlan, plan_id)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "plan not found")
    c = Contour(
        study_id=plan.study_id,
        plan_id=plan.id,
        contour_type=payload.contour_type,
        name=payload.name,
        color=payload.color,
        geometry=payload.geometry,
        volume_cm3=payload.volume_cm3,
        actor_id=user.id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="contour.created",
        resource_type="contour",
        resource_id=str(c.id),
        request_id=request.headers.get("x-request-id"),
        details={
            "plan_id": str(plan.id),
            "contour_type": c.contour_type,
            "name": c.name,
        },
    )
    return _contour_out(c)


@router.delete("/contours/{contour_id}", status_code=204)
def delete_contour(
    contour_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    c = db.get(Contour, contour_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "contour not found")
    db.delete(c)
    db.commit()
    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="contour.deleted",
        resource_type="contour",
        resource_id=str(contour_id),
        request_id=request.headers.get("x-request-id"),
    )


# ---------- constraint catalog ----------


@router.get("/constraints/oar")
def constraints_oar(user: User = Depends(current_user)) -> dict:
    """Return the constraint catalog so the frontend can render the table."""
    return {
        "tissues": oar_constraints.supported_tissues(),
        "constraints": [
            {
                "tissue": c.tissue,
                "metric": c.metric,
                "limit_gy": c.limit_gy,
                "severity_on_breach": c.severity_on_breach,
                "rationale": c.rationale,
                "source": c.source,
            }
            for c in oar_constraints.CONSTRAINTS
        ],
    }


@router.post("/constraints/evaluate")
def evaluate_constraints(
    payload: dict,
    user: User = Depends(current_user),
) -> list[dict]:
    """payload: {"tissue": "lung_left", "dose": {"mean": 18.2, "max": 35.4, "v20": 0.21, "v30": 0.08}}"""
    tissue = payload.get("tissue", "")
    dose = payload.get("dose", {}) or {}
    evals = oar_constraints.evaluate(tissue, dose)
    return [
        {
            "tissue": e.constraint.tissue,
            "metric": e.constraint.metric,
            "limit_gy": e.constraint.limit_gy,
            "observed": round(e.observed, 2),
            "status": e.status,
            "rationale": e.constraint.rationale,
            "source": e.constraint.source,
        }
        for e in evals
    ]
