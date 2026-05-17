"""Patient-centric routes — longitudinal view + change report.

Patients are identified only by their de-identified pseudonym; the
original PatientID is never exposed.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.security import current_user
from app.db.models.finding import Finding
from app.db.models.patient import Patient
from app.db.models.study import Study
from app.db.models.user import User
from app.db.session import get_db
from app.services.medgemma import build_narrator

router = APIRouter(prefix="/patients", tags=["patients"])


class PatientOut(BaseModel):
    pseudonym: str
    study_count: int
    first_study_at: datetime | None
    last_study_at: datetime | None


class PatientStudyOut(BaseModel):
    id: str
    study_instance_uid: str
    modality: str
    body_part: str
    description: str
    state: str
    study_date: datetime | None
    finding_count: int


class ChangeReportIn(BaseModel):
    baseline_study_id: uuid.UUID
    follow_up_study_id: uuid.UUID


class ChangeReportOut(BaseModel):
    text: str | None
    backend: str
    model_id: str
    error: str | None = None


@router.get("/", response_model=list[PatientOut])
def list_patients(
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[PatientOut]:
    patients = db.query(Patient).order_by(Patient.created_at.desc()).limit(200).all()
    out: list[PatientOut] = []
    for p in patients:
        studies = (
            db.query(Study.created_at)
            .filter(Study.patient_id == p.id)
            .order_by(Study.created_at.asc())
            .all()
        )
        if not studies:
            continue
        out.append(
            PatientOut(
                pseudonym=p.pseudonym,
                study_count=len(studies),
                first_study_at=studies[0][0],
                last_study_at=studies[-1][0],
            )
        )
    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="patient.list",
        request_id=request.headers.get("x-request-id"),
    )
    return out


@router.get("/{pseudonym}/studies", response_model=list[PatientStudyOut])
def patient_studies(
    pseudonym: str,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[PatientStudyOut]:
    p = db.query(Patient).filter(Patient.pseudonym == pseudonym).one_or_none()
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "patient not found")
    rows = (
        db.query(Study)
        .filter(Study.patient_id == p.id)
        .order_by(Study.study_date.desc().nullslast(), Study.created_at.desc())
        .all()
    )
    counts: dict[uuid.UUID, int] = {}
    if rows:
        for sid, _ in (
            db.query(Finding.study_id, Finding.id)
            .filter(
                Finding.study_id.in_([r.id for r in rows]),
                Finding.is_current == True,  # noqa: E712
            )
            .all()
        ):
            counts[sid] = counts.get(sid, 0) + 1
    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="patient.view",
        resource_type="patient",
        resource_id=pseudonym,
        request_id=request.headers.get("x-request-id"),
        details={"study_count": len(rows)},
    )
    return [
        PatientStudyOut(
            id=str(s.id),
            study_instance_uid=s.study_instance_uid,
            modality=s.modality,
            body_part=s.body_part,
            description=s.description,
            state=s.state,
            study_date=s.study_date,
            finding_count=counts.get(s.id, 0),
        )
        for s in rows
    ]


@router.post(
    "/{pseudonym}/change-report",
    response_model=ChangeReportOut,
)
def change_report(
    pseudonym: str,
    payload: ChangeReportIn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ChangeReportOut:
    p = db.query(Patient).filter(Patient.pseudonym == pseudonym).one_or_none()
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "patient not found")
    baseline = db.get(Study, payload.baseline_study_id)
    follow_up = db.get(Study, payload.follow_up_study_id)
    if not baseline or not follow_up or baseline.patient_id != p.id or follow_up.patient_id != p.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "both studies must belong to this patient",
        )

    baseline_findings = (
        db.query(Finding)
        .filter(Finding.study_id == baseline.id, Finding.is_current == True)  # noqa: E712
        .all()
    )
    follow_up_findings = (
        db.query(Finding)
        .filter(Finding.study_id == follow_up.id, Finding.is_current == True)  # noqa: E712
        .all()
    )

    narrator = build_narrator()
    result = narrator.compare_studies_sync(
        baseline=baseline,
        follow_up=follow_up,
        baseline_findings=baseline_findings,
        follow_up_findings=follow_up_findings,
    )

    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="patient.change_report_generated",
        resource_type="patient",
        resource_id=pseudonym,
        request_id=request.headers.get("x-request-id"),
        details={
            "baseline_study_id": str(baseline.id),
            "follow_up_study_id": str(follow_up.id),
            "backend": result.backend,
            "ok": bool(result.text),
            "error": result.error,
        },
    )
    return ChangeReportOut(
        text=result.text,
        backend=result.backend,
        model_id=result.model_id,
        error=result.error,
    )
