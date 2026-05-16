import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.security import current_user
from app.db.models.finding import Finding
from app.db.models.study import Study
from app.db.models.user import User
from app.db.session import get_db
from app.services.study_pipeline import enqueue_inference, generate_report, run_inference

router = APIRouter(prefix="/studies", tags=["studies"])


class StudyOut(BaseModel):
    id: str
    study_instance_uid: str
    modality: str
    body_part: str
    description: str
    state: str
    finding_count: int


class FindingOut(BaseModel):
    id: str
    label: str
    body_part: str
    confidence: float
    icd10_suggestion: str | None
    model_name: str
    model_version: str
    geometry: dict | None


@router.get("/", response_model=list[StudyOut])
def list_studies(
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[StudyOut]:
    rows = db.query(Study).order_by(Study.created_at.desc()).limit(200).all()
    counts = {}
    if rows:
        for sid, n in (
            db.query(Finding.study_id, Finding.id)
            .filter(Finding.study_id.in_([r.id for r in rows]))
            .all()
        ):
            counts[sid] = counts.get(sid, 0) + 1

    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="study.list",
        request_id=request.headers.get("x-request-id"),
    )
    return [
        StudyOut(
            id=str(s.id),
            study_instance_uid=s.study_instance_uid,
            modality=s.modality,
            body_part=s.body_part,
            description=s.description,
            state=s.state,
            finding_count=counts.get(s.id, 0),
        )
        for s in rows
    ]


@router.get("/{study_id}", response_model=StudyOut)
def get_study(
    study_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> StudyOut:
    s = db.get(Study, study_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "study not found")
    n = db.query(Finding).filter(Finding.study_id == s.id).count()
    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="study.view",
        resource_type="study",
        resource_id=str(s.id),
        request_id=request.headers.get("x-request-id"),
    )
    return StudyOut(
        id=str(s.id),
        study_instance_uid=s.study_instance_uid,
        modality=s.modality,
        body_part=s.body_part,
        description=s.description,
        state=s.state,
        finding_count=n,
    )


@router.get("/{study_id}/findings", response_model=list[FindingOut])
def list_findings(
    study_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[FindingOut]:
    rows = db.query(Finding).filter(Finding.study_id == study_id).all()
    return [
        FindingOut(
            id=str(f.id),
            label=f.label,
            body_part=f.body_part,
            confidence=f.confidence,
            icd10_suggestion=f.icd10_suggestion,
            model_name=f.model_name,
            model_version=f.model_version,
            geometry=f.geometry,
        )
        for f in rows
    ]


@router.post("/{study_id}/run-inference", status_code=202)
def run_inference_endpoint(
    study_id: uuid.UUID,
    background: BackgroundTasks,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "study not found")
    job = enqueue_inference(db, study)
    background.add_task(_run_in_new_session, job.id)
    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="inference.requested",
        resource_type="study",
        resource_id=str(study.id),
        request_id=request.headers.get("x-request-id"),
        details={"job_id": str(job.id)},
    )
    return {"job_id": str(job.id), "status": job.status}


@router.post("/{study_id}/sign", response_model=dict)
def sign_report(
    study_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    report = generate_report(db, study_id, signed_by=user.id)
    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="report.signed",
        resource_type="study",
        resource_id=str(study_id),
        request_id=request.headers.get("x-request-id"),
        details={"report_id": str(report.id)},
    )
    return {"report_id": str(report.id), "signed_at": report.signed_at.isoformat()}


def _run_in_new_session(job_id: uuid.UUID) -> None:
    """BackgroundTasks runs in the same event loop; we need our own DB session."""
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        run_inference(db, job_id)
