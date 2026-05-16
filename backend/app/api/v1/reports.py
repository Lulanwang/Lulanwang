import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.security import current_user
from app.db.models.report import Report
from app.db.models.user import User
from app.db.session import get_db

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/study/{study_id}")
def get_for_study(
    study_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    r = (
        db.query(Report)
        .filter(Report.study_id == study_id)
        .order_by(Report.created_at.desc())
        .first()
    )
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no report for study")
    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="report.view",
        resource_type="report",
        resource_id=str(r.id),
        request_id=request.headers.get("x-request-id"),
    )
    return {
        "id": str(r.id),
        "study_id": str(r.study_id),
        "impression": r.impression,
        "icd10_codes": r.icd10_codes or [],
        "fhir_diagnostic_report": r.fhir_diagnostic_report,
        "signed_at": r.signed_at.isoformat() if r.signed_at else None,
        "signed_by": str(r.signed_by) if r.signed_by else None,
        "sr_available": bool(r.sr_path),
    }


@router.get("/{report_id}/fhir")
def report_fhir(
    report_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    r = db.get(Report, report_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")
    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="report.export.fhir",
        resource_type="report",
        resource_id=str(r.id),
        request_id=request.headers.get("x-request-id"),
    )
    return JSONResponse(r.fhir_diagnostic_report or {})


@router.get("/{report_id}/sr")
def report_sr(
    report_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    r = db.get(Report, report_id)
    if r is None or not r.sr_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no SR file")
    p = Path(r.sr_path)
    if not p.exists():
        raise HTTPException(status.HTTP_410_GONE, "SR artifact missing on disk")
    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="report.export.sr",
        resource_type="report",
        resource_id=str(r.id),
        request_id=request.headers.get("x-request-id"),
    )
    return FileResponse(p, media_type="application/dicom", filename="report_sr.dcm")
