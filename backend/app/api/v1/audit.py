from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.models.audit_event import AuditEvent
from app.db.models.user import User
from app.db.session import get_db

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditOut(BaseModel):
    id: str
    created_at: str
    actor_id: str | None
    actor_role: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    request_id: str | None
    ip: str | None
    details: dict | None


@router.get("/", response_model=list[AuditOut])
def list_events(
    limit: int = 200,
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> list[AuditOut]:
    rows = db.query(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit).all()
    return [
        AuditOut(
            id=str(r.id),
            created_at=r.created_at.isoformat(),
            actor_id=str(r.actor_id) if r.actor_id else None,
            actor_role=r.actor_role,
            action=r.action,
            resource_type=r.resource_type,
            resource_id=r.resource_id,
            request_id=r.request_id,
            ip=r.ip,
            details=r.details,
        )
        for r in rows
    ]
