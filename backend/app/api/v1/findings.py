"""Versioning state machine for findings.

  AI emits a Finding row at `version=1, source="ai", status="proposed", is_current=true`.

Radiologist actions (each logs an audit event):

  - accept   → set status="accepted" on the AI row. No new row.
  - reject   → set status="rejected", is_current=false. Excluded from report.
  - refine   → INSERT a new row (`version`++, `source="radiologist"`,
               `status="modified"`, parent_finding_id=old.id), set old
               row `is_current=false`. The AI row is never mutated, so
               its original geometry remains queryable indefinitely.

History endpoint walks the parent chain so the UI can render a timeline
of every revision.
"""
from __future__ import annotations

import json
import uuid
from io import BytesIO

import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.config import settings
from app.core.security import current_user
from app.db.models.finding import Finding
from app.db.models.study import Study
from app.db.models.user import User
from app.db.session import get_db
from app.dicom.seg_writer import write_segmentation
from pathlib import Path

router = APIRouter(prefix="/findings", tags=["findings"])


class FindingDetail(BaseModel):
    id: str
    study_id: str
    parent_finding_id: str | None
    version: int
    is_current: bool
    source: str
    status: str
    actor_id: str | None
    label: str
    body_part: str
    confidence: float | None
    icd10_suggestion: str | None
    geometry: dict | None
    model_name: str
    model_version: str
    seg_sop_instance_uid: str | None
    created_at: str


def _to_detail(f: Finding) -> FindingDetail:
    return FindingDetail(
        id=str(f.id),
        study_id=str(f.study_id),
        parent_finding_id=str(f.parent_finding_id) if f.parent_finding_id else None,
        version=f.version,
        is_current=f.is_current,
        source=f.source,
        status=f.status,
        actor_id=str(f.actor_id) if f.actor_id else None,
        label=f.label,
        body_part=f.body_part,
        confidence=f.confidence,
        icd10_suggestion=f.icd10_suggestion,
        geometry=f.geometry,
        model_name=f.model_name,
        model_version=f.model_version,
        seg_sop_instance_uid=f.seg_sop_instance_uid,
        created_at=f.created_at.isoformat(),
    )


@router.get("/{finding_id}", response_model=FindingDetail)
def get_finding(
    finding_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> FindingDetail:
    f = db.get(Finding, finding_id)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "finding not found")
    return _to_detail(f)


@router.get("/{finding_id}/history", response_model=list[FindingDetail])
def finding_history(
    finding_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[FindingDetail]:
    """Walk the parent chain backwards and the descendant chain forwards.

    Returns rows in version order (v1 = AI, v2 = first refinement, ...).
    """
    f = db.get(Finding, finding_id)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "finding not found")

    # Walk up to the root
    root = f
    while root.parent_finding_id is not None:
        parent = db.get(Finding, root.parent_finding_id)
        if parent is None:
            break
        root = parent

    # BFS down — for MVP each row has at most one descendant, so a
    # linear walk suffices
    chain = [root]
    seen = {root.id}
    cursor = root
    while True:
        child = (
            db.query(Finding)
            .filter(Finding.parent_finding_id == cursor.id)
            .order_by(Finding.version.asc())
            .first()
        )
        if child is None or child.id in seen:
            break
        chain.append(child)
        seen.add(child.id)
        cursor = child

    return [_to_detail(x) for x in chain]


class AcceptIn(BaseModel):
    icd10_override: str | None = None


@router.post("/{finding_id}/accept", response_model=FindingDetail)
def accept_finding(
    finding_id: uuid.UUID,
    body: AcceptIn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> FindingDetail:
    f = db.get(Finding, finding_id)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "finding not found")
    if not f.is_current:
        raise HTTPException(status.HTTP_409_CONFLICT, "only the current version can be accepted")
    if f.status in ("rejected", "modified"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"cannot accept a finding in status={f.status}")

    f.status = "accepted"
    if body.icd10_override:
        f.icd10_suggestion = body.icd10_override
    db.commit()
    db.refresh(f)

    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="finding.accepted",
        resource_type="finding",
        resource_id=str(f.id),
        request_id=request.headers.get("x-request-id"),
        details={"study_id": str(f.study_id)},
    )
    return _to_detail(f)


@router.post("/{finding_id}/reject", response_model=FindingDetail)
def reject_finding(
    finding_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> FindingDetail:
    f = db.get(Finding, finding_id)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "finding not found")
    if not f.is_current:
        raise HTTPException(status.HTTP_409_CONFLICT, "only the current version can be rejected")

    f.status = "rejected"
    f.is_current = False
    db.commit()
    db.refresh(f)

    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="finding.rejected",
        resource_type="finding",
        resource_id=str(f.id),
        request_id=request.headers.get("x-request-id"),
        details={"study_id": str(f.study_id)},
    )
    return _to_detail(f)


@router.post("/{finding_id}/refine", response_model=FindingDetail)
async def refine_finding(
    finding_id: uuid.UUID,
    request: Request,
    label: str = Form(...),
    icd10_suggestion: str | None = Form(default=None),
    geometry: str = Form(...),  # JSON-encoded; bbox/polygon/etc.
    mask: UploadFile | None = File(default=None),  # optional .npy mask
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> FindingDetail:
    """Append a radiologist-refined finding.

    The parent (AI) row is never mutated — only its is_current flag flips.
    `geometry` is the JSON sketch the viewer renders fast. `mask` is the
    pixel-precise overlay; when present, we persist it as a DICOM SEG.
    """
    parent = db.get(Finding, finding_id)
    if parent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "finding not found")
    if not parent.is_current:
        raise HTTPException(status.HTTP_409_CONFLICT, "only the current version can be refined")

    try:
        geometry_obj = json.loads(geometry)
    except json.JSONDecodeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"invalid geometry JSON: {exc}") from exc

    # Persist mask as DICOM SEG (with fallback) when provided.
    seg_uid: str | None = None
    if mask is not None:
        try:
            buf = BytesIO(await mask.read())
            arr = np.load(buf, allow_pickle=False)
            out_dir = Path(settings.artifact_dir) / str(parent.study_id) / "seg" / str(parent.id)
            result = write_segmentation(
                mask=arr,
                source_datasets=[],  # source datasets are loaded server-side in production
                label=label,
                out_dir=out_dir,
            )
            seg_uid = result.sop_instance_uid
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, f"mask processing failed: {exc}"
            ) from exc

    # Insert new row
    new = Finding(
        study_id=parent.study_id,
        job_id=parent.job_id,
        parent_finding_id=parent.id,
        version=parent.version + 1,
        is_current=True,
        source="radiologist",
        status="modified",
        actor_id=user.id,
        label=label,
        body_part=parent.body_part,
        confidence=None,  # human edits don't carry a model confidence
        icd10_suggestion=icd10_suggestion or parent.icd10_suggestion,
        geometry=geometry_obj,
        model_name=parent.model_name,
        model_version=parent.model_version,
        seg_sop_instance_uid=seg_uid,
    )
    parent.is_current = False
    db.add(new)
    db.commit()
    db.refresh(new)

    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="finding.refined",
        resource_type="finding",
        resource_id=str(new.id),
        request_id=request.headers.get("x-request-id"),
        details={
            "parent_finding_id": str(parent.id),
            "version": new.version,
            "study_id": str(parent.study_id),
            "has_seg": seg_uid is not None,
        },
    )
    return _to_detail(new)


@router.get("/study/{study_id}", response_model=list[FindingDetail])
def list_findings_for_study(
    study_id: uuid.UUID,
    include_history: bool = False,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[FindingDetail]:
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "study not found")
    q = db.query(Finding).filter(Finding.study_id == study_id)
    if not include_history:
        q = q.filter(Finding.is_current == True)  # noqa: E712
    rows = q.order_by(Finding.version.asc(), Finding.created_at.asc()).all()
    return [_to_detail(f) for f in rows]
