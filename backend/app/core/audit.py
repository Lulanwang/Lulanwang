"""Append-only audit log.

The application layer never updates or deletes audit_events. A
database trigger should enforce this at the storage layer in
production (see infra/postgres/init.sql).
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.audit_event import AuditEvent

log = logging.getLogger(__name__)


def log_event(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    actor_role: str | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    request_id: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    evt = AuditEvent(
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=request_id,
        ip=ip,
        user_agent=user_agent,
        details=details,
    )
    db.add(evt)
    db.commit()
    log.info(
        "audit",
        extra={
            "actor": str(actor_id) if actor_id else None,
            "action": action,
            "resource": f"{resource_type}:{resource_id}",
            "request_id": request_id,
        },
    )
