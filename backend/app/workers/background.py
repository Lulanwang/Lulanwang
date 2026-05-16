"""Crash recovery for FastAPI BackgroundTasks-driven jobs.

On boot, any Job left in `running` (process died mid-inference) is
marked `failed` with a clear error so the UI shows a re-queue affordance.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import update

from app.db.models.job import Job
from app.db.models.study import Study
from app.db.session import SessionLocal

log = logging.getLogger(__name__)


def recover_orphaned_jobs() -> None:
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        result = db.execute(
            update(Job)
            .where(Job.status == "running")
            .values(status="failed", error="orphaned by worker restart", finished_at=now)
            .returning(Job.id, Job.study_id)
        )
        rows = result.fetchall()
        if not rows:
            db.commit()
            return
        study_ids = [r.study_id for r in rows]
        db.execute(
            update(Study).where(Study.id.in_(study_ids)).values(state="failed", error="worker crash")
        )
        db.commit()
        log.warning("recovered %d orphaned inference jobs", len(rows))
