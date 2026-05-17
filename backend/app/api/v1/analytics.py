"""Operational analytics across the platform.

Cheap aggregates over the existing schema. Nothing here is privacy-
sensitive: AI-finding statuses, modality/body-part breakdowns, latency.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.security import current_user
from app.db.models.audit_event import AuditEvent
from app.db.models.finding import Finding
from app.db.models.job import Job
from app.db.models.user import User
from app.db.session import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/accept-rate")
def accept_rate(
    request: Request,
    group_by: str = "model",
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """AI accept-vs-reject rate grouped by model_name (default) or body_part."""
    if group_by not in ("model", "body_part"):
        group_by = "model"

    rows = (
        db.query(Finding.model_name, Finding.body_part, Finding.status)
        .filter(Finding.source == "ai")
        .all()
    )

    buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {"accepted": 0, "rejected": 0, "modified": 0, "proposed": 0}
    )
    for model_name, body_part, status in rows:
        key = model_name if group_by == "model" else body_part
        if not key:
            continue
        if status in buckets[key]:
            buckets[key][status] += 1

    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="analytics.accept_rate",
        request_id=request.headers.get("x-request-id"),
        details={"group_by": group_by},
    )
    return [
        {
            "group": k,
            "accepted": v["accepted"],
            "rejected": v["rejected"],
            "modified": v["modified"],
            "proposed": v["proposed"],
            "total": sum(v.values()),
        }
        for k, v in sorted(buckets.items())
    ]


@router.get("/job-latency")
def job_latency(
    days: int = 30,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Per-day mean inference latency in ms."""
    days = max(1, min(days, 180))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(Job.finished_at, Job.started_at)
        .filter(
            Job.finished_at.isnot(None),
            Job.started_at.isnot(None),
            Job.finished_at >= cutoff,
        )
        .all()
    )
    per_day: dict[str, list[float]] = defaultdict(list)
    for finished_at, started_at in rows:
        if not finished_at or not started_at:
            continue
        per_day[finished_at.date().isoformat()].append(
            (finished_at - started_at).total_seconds() * 1000.0
        )

    out: list[dict] = []
    for i in range(days):
        d = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).date()
        key = d.isoformat()
        latencies = per_day.get(key, [])
        out.append(
            {
                "date": key,
                "mean_ms": round(sum(latencies) / len(latencies), 1)
                if latencies
                else 0.0,
                "count": len(latencies),
            }
        )
    return out


@router.get("/audit-heatmap")
def audit_heatmap(
    days: int = 90,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Per-day audit event counts (GitHub-style heatmap)."""
    days = max(1, min(days, 365))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(AuditEvent.created_at)
        .filter(AuditEvent.created_at >= cutoff)
        .all()
    )
    counts: Counter[str] = Counter()
    for (ts,) in rows:
        if ts:
            counts[ts.date().isoformat()] += 1
    out: list[dict] = []
    for i in range(days):
        d = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).date()
        key = d.isoformat()
        out.append({"date": key, "count": counts.get(key, 0)})
    return out
