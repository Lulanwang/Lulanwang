import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.security import current_user
from app.db.models.finding import Finding
from app.db.models.study import Study
from app.db.models.user import User
from app.db.session import get_db
from app.services import thumbnail
from app.services.study_pipeline import enqueue_inference, generate_report, run_inference

router = APIRouter(prefix="/studies", tags=["studies"])

SORTABLE = {
    "created_at": Study.created_at,
    "study_date": Study.study_date,
    "modality": Study.modality,
    "body_part": Study.body_part,
    "state": Study.state,
}


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
    confidence: float | None
    icd10_suggestion: str | None
    model_name: str
    model_version: str
    geometry: dict | None
    version: int
    is_current: bool
    source: str
    status: str
    parent_finding_id: str | None
    seg_sop_instance_uid: str | None


@router.get("/", response_model=list[StudyOut])
def list_studies(
    request: Request,
    modality: str | None = Query(None, description="Filter by modality (e.g. CT, MR, MG)"),
    body_part: str | None = Query(None, description="Filter by body part (e.g. BRAIN, CHEST)"),
    state: str | None = Query(None, description="Filter by lifecycle state"),
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    has_findings: bool | None = Query(
        None, description="True = at least one current finding; False = none"
    ),
    sort: str = Query("created_at", description="Sort column"),
    order: str = Query("desc", description="asc | desc"),
    limit: int = Query(200, ge=1, le=500),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[StudyOut]:
    q = db.query(Study)
    if modality:
        q = q.filter(Study.modality == modality.upper())
    if body_part:
        q = q.filter(Study.body_part == body_part.upper())
    if state:
        q = q.filter(Study.state == state)
    if from_date:
        q = q.filter(Study.study_date >= datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc))
    if to_date:
        q = q.filter(Study.study_date <= datetime.combine(to_date, datetime.max.time(), tzinfo=timezone.utc))

    col = SORTABLE.get(sort, Study.created_at)
    direction = asc if order.lower() == "asc" else desc
    q = q.order_by(direction(col)).limit(limit)

    rows = q.all()

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

    if has_findings is True:
        rows = [r for r in rows if counts.get(r.id, 0) > 0]
    elif has_findings is False:
        rows = [r for r in rows if counts.get(r.id, 0) == 0]

    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="study.list",
        request_id=request.headers.get("x-request-id"),
        details={
            "filters": {
                "modality": modality,
                "body_part": body_part,
                "state": state,
                "has_findings": has_findings,
            },
            "result_count": len(rows),
        },
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


@router.get("/facets")
def list_facets(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Distinct values for the worklist filter sidebar."""
    modalities = sorted(
        {m for (m,) in db.query(Study.modality).distinct().all() if m}
    )
    body_parts = sorted(
        {b for (b,) in db.query(Study.body_part).distinct().all() if b}
    )
    states = sorted({s for (s,) in db.query(Study.state).distinct().all() if s})
    return {
        "modalities": modalities,
        "body_parts": body_parts,
        "states": states,
    }


@router.get("/{study_id}/thumbnail")
async def study_thumbnail(
    study_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    s = db.get(Study, study_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "study not found")
    png = await thumbnail.get_or_render(study_id, s.study_instance_uid)
    if png is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "thumbnail unavailable")
    return Response(content=png, media_type="image/png")


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
    include_history: bool = False,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[FindingOut]:
    q = db.query(Finding).filter(Finding.study_id == study_id)
    if not include_history:
        q = q.filter(Finding.is_current == True)  # noqa: E712
    rows = q.order_by(Finding.version.asc(), Finding.created_at.asc()).all()
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
            version=f.version,
            is_current=f.is_current,
            source=f.source,
            status=f.status,
            parent_finding_id=str(f.parent_finding_id) if f.parent_finding_id else None,
            seg_sop_instance_uid=f.seg_sop_instance_uid,
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
