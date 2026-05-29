"""3D digital-twin API endpoints.

* ``POST /twins/{study_id}/generate`` — enqueue mesh generation in the
  background (get-or-create per ``SEG_CONFIG_VERSION``).
* ``GET  /twins/{study_id}`` — current status + per-structure metadata.
* ``GET  /twins/{study_id}/model.glb`` — stream the glTF-binary mesh
  (auth-required, ``model/gltf-binary``).

Mirrors the ``treatment_plans`` router's style: prefix, ``current_user``
+ ``get_db`` dependencies, BackgroundTasks via a ``_run_in_new_session``
wrapper exactly like ``studies.run-inference``.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.security import current_user
from app.db.models.organ_twin import OrganTwin
from app.db.models.study import Study
from app.db.models.user import User
from app.db.session import get_db
from app.services.twin import config as twin_cfg
from app.services.twin.pipeline import enqueue_twin, run_twin_generation

log = logging.getLogger(__name__)
router = APIRouter(prefix="/twins", tags=["twins"])


class TwinOut(BaseModel):
    id: str
    study_id: str
    job_id: str | None
    status: str
    seg_config_version: str
    body_part: str
    structures: list[dict] | None
    glb_bytes: int | None
    error: str | None


class GenerateOut(BaseModel):
    twin_id: str
    status: str


def _serialize(twin: OrganTwin) -> TwinOut:
    return TwinOut(
        id=str(twin.id),
        study_id=str(twin.study_id),
        job_id=str(twin.job_id) if twin.job_id else None,
        status=twin.status,
        seg_config_version=twin.seg_config_version,
        body_part=twin.body_part,
        structures=twin.structures,
        glb_bytes=twin.glb_bytes,
        error=twin.error,
    )


def _run_twin_in_new_session(twin_id: uuid.UUID) -> None:
    """BackgroundTasks runs in the API loop; build our own DB session."""
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        run_twin_generation(db, twin_id)


@router.post(
    "/{study_id}/generate",
    response_model=GenerateOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_twin(
    study_id: uuid.UUID,
    background: BackgroundTasks,
    request: Request,
    force: bool = False,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> GenerateOut:
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "study not found")

    twin = enqueue_twin(db, study, force=force)
    if twin.status == "succeeded" and not force:
        return GenerateOut(twin_id=str(twin.id), status=twin.status)

    background.add_task(_run_twin_in_new_session, twin.id)
    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="twin.requested",
        resource_type="organ_twin",
        resource_id=str(twin.id),
        request_id=request.headers.get("x-request-id"),
        details={"study_id": str(study.id), "force": force},
    )
    return GenerateOut(twin_id=str(twin.id), status=twin.status)


@router.get("/{study_id}", response_model=TwinOut)
def get_twin(
    study_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> TwinOut:
    """Latest twin for the current SEG_CONFIG_VERSION."""
    twin = (
        db.query(OrganTwin)
        .filter(
            OrganTwin.study_id == study_id,
            OrganTwin.seg_config_version == twin_cfg.SEG_CONFIG_VERSION,
        )
        .one_or_none()
    )
    if twin is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no twin for study")
    return _serialize(twin)


@router.get("/{study_id}/model.glb")
def get_twin_glb(
    study_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream the glTF-binary mesh. Auth-required."""
    twin = (
        db.query(OrganTwin)
        .filter(
            OrganTwin.study_id == study_id,
            OrganTwin.seg_config_version == twin_cfg.SEG_CONFIG_VERSION,
        )
        .one_or_none()
    )
    if twin is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no twin for study")
    if twin.status != "succeeded":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"twin status={twin.status}; not yet available",
        )
    if not twin.glb_path or not Path(twin.glb_path).exists():
        raise HTTPException(
            status.HTTP_410_GONE, "twin GLB file missing on disk"
        )

    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="twin.download",
        resource_type="organ_twin",
        resource_id=str(twin.id),
        request_id=request.headers.get("x-request-id"),
    )

    def _stream():
        with open(twin.glb_path, "rb") as fh:  # noqa: PTH123
            while True:
                chunk = fh.read(64 * 1024)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        _stream(),
        media_type="model/gltf-binary",
        headers={
            "Cache-Control": "private, max-age=300",
            "Content-Length": str(twin.glb_bytes or 0),
            "Content-Disposition": f'inline; filename="twin-{study_id}.glb"',
        },
    )
