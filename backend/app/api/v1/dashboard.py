"""Dashboard KPIs + charts.

Cheap aggregate queries against the existing tables. No new schema.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.security import current_user
from app.db.models.audit_event import AuditEvent
from app.db.models.finding import Finding
from app.db.models.job import Job
from app.db.models.report import Report
from app.db.models.study import Study
from app.db.models.user import User
from app.db.session import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _fill_daily_buckets(
    timestamps: list[datetime], *, now: datetime, days: int
) -> list[dict]:
    """Group timestamps by calendar date in UTC, then emit a dense list of
    {date, count} dicts covering the last `days` calendar days (inclusive of
    today). Empty days get count=0 so the chart is contiguous."""
    bucket: dict[str, int] = defaultdict(int)
    for ts in timestamps:
        bucket[ts.date().isoformat()] += 1
    out: list[dict] = []
    for i in range(days):
        d = (now - timedelta(days=days - 1 - i)).date()
        out.append({"date": d.isoformat(), "count": bucket.get(d.isoformat(), 0)})
    return out


def _mean_latency_ms(pairs: list[tuple[datetime | None, datetime | None]]) -> float:
    """Mean wall-clock latency in ms across (started_at, finished_at) pairs.
    Skips rows missing either timestamp. Returns 0.0 on empty input."""
    latencies = [
        (f - s).total_seconds() * 1000.0 for s, f in pairs if s and f
    ]
    return sum(latencies) / len(latencies) if latencies else 0.0


@router.get("/kpis")
def kpis(
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    studies_7d = (
        db.query(func.count(Study.id))
        .filter(Study.created_at >= week_ago)
        .scalar()
        or 0
    )
    signed_reports = (
        db.query(func.count(Report.id))
        .filter(Report.signed_at.isnot(None))
        .scalar()
        or 0
    )

    finished_jobs = (
        db.query(Job.started_at, Job.finished_at)
        .filter(Job.started_at.isnot(None), Job.finished_at.isnot(None))
        .all()
    )
    mean_latency_ms = _mean_latency_ms(finished_jobs)

    ai_findings = db.query(Finding.status).filter(Finding.source == "ai").all()
    reviewed = [s for (s,) in ai_findings if s in ("accepted", "rejected")]
    accept_rate = (
        sum(1 for s in reviewed if s == "accepted") / len(reviewed)
        if reviewed
        else None
    )

    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="dashboard.kpis",
        request_id=request.headers.get("x-request-id"),
    )
    return {
        "studies_7d": studies_7d,
        "signed_reports": signed_reports,
        "mean_latency_ms": round(mean_latency_ms, 1),
        "accept_rate": accept_rate,  # null if no reviewed findings yet
        "reviewed_findings": len(reviewed),
    }


@router.get("/studies-per-day")
def studies_per_day(
    days: int = 30,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    days = max(1, min(days, 180))
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    rows = (
        db.query(Study.created_at)
        .filter(Study.created_at >= cutoff)
        .all()
    )
    return _fill_daily_buckets([ts for (ts,) in rows], now=now, days=days)


@router.get("/modality-breakdown")
def modality_breakdown(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = db.query(Study.modality).all()
    counter = Counter(m for (m,) in rows if m)
    return [{"modality": m, "count": c} for m, c in counter.most_common()]


@router.get("/recent-activity")
def recent_activity(
    limit: int = 10,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    limit = max(1, min(limit, 50))
    rows = (
        db.query(AuditEvent)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(r.id),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "action": r.action,
            "actor_role": r.actor_role,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
        }
        for r in rows
    ]


@router.get("/unsigned-studies")
def unsigned_studies(
    limit: int = 5,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    limit = max(1, min(limit, 20))
    rows = (
        db.query(Study)
        .filter(Study.state == "reported")
        .order_by(Study.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(s.id),
            "description": s.description,
            "modality": s.modality,
            "body_part": s.body_part,
            "state": s.state,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in rows
    ]
