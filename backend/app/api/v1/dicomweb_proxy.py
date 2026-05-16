"""Authenticated DICOMweb reverse proxy.

OHIF (and any DICOMweb client) talks to `/dicom-web/*` on the public
origin. Caddy routes those calls into FastAPI, where we:
  1. Require a valid JWT.
  2. Log every QIDO/WADO/STOW call in audit_events.
  3. Forward to Orthanc with the server-side credentials.

This is the chokepoint that makes every PHI read auditable, even when
the user is "just looking at images" in the viewer.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.security import current_user
from app.db.models.user import User
from app.db.session import get_db
from app.services import orthanc_client

router = APIRouter(prefix="/dicom-web", tags=["dicomweb"], include_in_schema=False)


def _action_for(method: str, path: str) -> str:
    if method == "POST":
        return "dicomweb.stow"
    if "/instances" in path and "/frames" not in path:
        return "dicomweb.wado.instance"
    if "/frames" in path:
        return "dicomweb.wado.frames"
    if "/series" in path:
        return "dicomweb.qido.series"
    if path.rstrip("/").endswith("studies") or "/studies/" in path:
        return "dicomweb.qido.studies"
    return "dicomweb.other"


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "HEAD", "OPTIONS"],
)
async def proxy(
    path: str,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    body = await request.body() if request.method in {"POST"} else None
    fwd_headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() in {"accept", "content-type", "if-match", "if-none-match"}
    }
    resp = await orthanc_client.wado_proxy(
        method=request.method, path=path, headers=fwd_headers, content=body
    )
    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action=_action_for(request.method, path),
        resource_type="dicomweb",
        resource_id=path,
        request_id=request.headers.get("x-request-id"),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        details={"status_code": resp.status_code},
    )
    # Pass through content + content-type
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type"),
    )
