"""Crash recovery for FastAPI BackgroundTasks-driven jobs.

On boot, any Job left in `running` (process died mid-inference) is
marked `failed` with a clear error so the UI shows a re-queue affordance.

FastAPI BackgroundTasks are in-process and scheduled only AFTER the HTTP
response returns. If the worker dies between the enqueue commit and the
task actually starting, the row never leaves `queued` and the UI shows a
permanent spinner. So we sweep both `running` AND `queued` rows.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import update

from app.db.models.job import Job
from app.db.models.organ_twin import OrganTwin
from app.db.models.study import Study
from app.db.session import SessionLocal

log = logging.getLogger(__name__)


def recover_orphaned_jobs() -> None:
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        # Reset jobs left in `running` (died mid-task) OR `queued` (the
        # in-process task was dropped before it ever started).
        result = db.execute(
            update(Job)
            .where(Job.status.in_(("running", "queued")))
            .values(status="failed", error="orphaned by worker restart", finished_at=now)
            .returning(Job.id, Job.study_id, Job.model_name)
        )
        rows = result.fetchall()
        # Twin rows track their own status (denormalized from Job) so we
        # reset them in the same sweep — otherwise the UI would keep
        # showing a stuck spinner after a worker restart.
        db.execute(
            update(OrganTwin)
            .where(OrganTwin.status.in_(("running", "queued")))
            .values(status="failed", error="orphaned by worker restart")
        )
        if not rows:
            db.commit()
            return
        # Inference jobs (not twin jobs) own the study state — only flip
        # study.state to failed for those.
        inference_study_ids = [
            r.study_id for r in rows if r.model_name != "twin-cv"
        ]
        if inference_study_ids:
            db.execute(
                update(Study)
                .where(Study.id.in_(inference_study_ids))
                .values(state="failed", error="worker crash")
            )
        db.commit()
        log.warning("recovered %d orphaned jobs", len(rows))
