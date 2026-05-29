"""Orchestrate one twin generation from start to finish.

Mirrors :func:`app.services.study_pipeline.run_inference`:

* Runs inside a fresh DB session created by the BackgroundTasks
  wrapper.
* Must not raise — every error is captured into ``OrganTwin.error``
  and ``Job.error``, both rows flipped to ``status="failed"``.
* Emits audit events so the timeline shows what happened.

The shape matches the inference pipeline closely so the recovery sweep
in :func:`app.workers.background.recover_orphaned_jobs` catches twin
jobs the same way it catches inference jobs.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.config import settings
from app.db.models.finding import Finding
from app.db.models.job import Job
from app.db.models.organ_twin import OrganTwin
from app.db.models.study import Study
from app.dicom.validators import model_key_for
from app.services.twin import config as cfg
from app.services.twin.meshing import (
    StructureMesh,
    assemble_glb,
    mask_to_mesh,
)
from app.services.twin.segment import (
    LesionMask,
    build_lesion_masks,
    resolve_segmenter,
)
from app.services.twin.volume_loader import LoadedSeries, load_primary_series

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enqueue (get-or-create with idempotency)
# ---------------------------------------------------------------------------


def enqueue_twin(db: Session, study: Study, *, force: bool = False) -> OrganTwin:
    """Return the existing twin for the current SEG_CONFIG_VERSION, or
    create a new ``queued`` row + Job.

    ``force=True`` requeues even if a succeeded row already exists. The
    old row is left in place but flipped back to ``queued`` and a new
    Job is attached.
    """
    twin = (
        db.query(OrganTwin)
        .filter(
            OrganTwin.study_id == study.id,
            OrganTwin.seg_config_version == cfg.SEG_CONFIG_VERSION,
        )
        .one_or_none()
    )
    if twin is not None and not force and twin.status == "succeeded":
        return twin

    job = Job(
        study_id=study.id,
        model_name="twin-cv",
        model_version=cfg.SEG_CONFIG_VERSION,
        status="queued",
    )
    db.add(job)
    db.flush()  # populate job.id without committing

    if twin is None:
        twin = OrganTwin(
            study_id=study.id,
            job_id=job.id,
            status="queued",
            seg_config_version=cfg.SEG_CONFIG_VERSION,
            body_part=study.body_part,
        )
        db.add(twin)
    else:
        twin.job_id = job.id
        twin.status = "queued"
        twin.error = None

    db.commit()
    db.refresh(twin)
    return twin


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


def run_twin_generation(db: Session, twin_id: uuid.UUID) -> None:
    """BackgroundTasks entry point. Must not raise."""
    twin = db.get(OrganTwin, twin_id)
    if twin is None:
        log.warning("run_twin_generation: twin %s not found", twin_id)
        return
    job = db.get(Job, twin.job_id) if twin.job_id else None
    study = db.get(Study, twin.study_id)
    if study is None:
        _mark_failed(db, twin, job, "study not found")
        return

    twin.status = "running"
    twin.error = None
    if job is not None:
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
    db.commit()

    log_event(
        db,
        actor_id=None,
        actor_role=None,
        action="twin.started",
        resource_type="organ_twin",
        resource_id=str(twin.id),
        details={"study_id": str(study.id), "body_part": study.body_part},
    )

    try:
        series = asyncio.run(load_primary_series(study.study_instance_uid))
        if series is None:
            raise RuntimeError("could not load DICOM series from Orthanc")
        structures = _segment_study(db, study, series)
        if not structures:
            raise RuntimeError("no structures produced — segmenter returned empty")
        result = assemble_glb(structures)
        glb_path = _write_glb(study.id, twin.id, result.glb_bytes)
        twin.glb_path = str(glb_path)
        twin.glb_bytes = len(result.glb_bytes)
        twin.structures = result.metadata
        twin.status = "succeeded"
        if job is not None:
            job.status = "succeeded"
            job.finished_at = datetime.now(timezone.utc)
            job.result = {
                "twin_id": str(twin.id),
                "structures": len(result.metadata),
                "glb_bytes": twin.glb_bytes,
            }
        db.commit()
        log_event(
            db,
            actor_id=None,
            actor_role=None,
            action="twin.completed",
            resource_type="organ_twin",
            resource_id=str(twin.id),
            details={
                "study_id": str(study.id),
                "structures": len(result.metadata),
                "glb_bytes": twin.glb_bytes,
            },
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("twin generation failed for %s", twin_id)
        _mark_failed(db, twin, job, _short_err(exc))


# ---------------------------------------------------------------------------
# Segmenter dispatch
# ---------------------------------------------------------------------------


def _segment_study(
    db: Session, study: Study, series: LoadedSeries
) -> list[StructureMesh]:
    key = model_key_for(study.modality, study.body_part)
    structures: list[StructureMesh] = []

    organ_mesh, organ_mask, synth_extrusion = _build_organ(key, series)
    if organ_mesh is not None and organ_mask is not None:
        structures.append(
            StructureMesh(
                name="organ",
                kind="organ",
                color_hex=cfg.ORGAN_COLOR,
                mesh=organ_mesh,
                volume_cm3=_volume_cm3(organ_mask, series.spacing_zyx),
                synthetic_extrusion=synth_extrusion,
            )
        )

    findings = (
        db.query(Finding)
        .filter(
            Finding.study_id == study.id,
            Finding.is_current.is_(True),
            Finding.status != "rejected",
        )
        .all()
    )
    lesions = build_lesion_masks(
        findings, series.volume.shape, str(study.id)
    )
    for i, lesion in enumerate(lesions):
        m = mask_to_mesh(
            lesion.mask,
            series.spacing_zyx,
            face_budget=cfg.LESION_FACE_BUDGET,
        )
        if m is None:
            continue
        structures.append(
            StructureMesh(
                name=f"lesion_{lesion.finding_id}",
                kind="lesion",
                color_hex=cfg.lesion_color(i),
                mesh=m,
                volume_cm3=_volume_cm3(lesion.mask, series.spacing_zyx),
                synthetic_marker=lesion.synthetic_marker,
            )
        )
    return structures


def _build_organ(
    body_part_key: str | None, series: LoadedSeries
) -> tuple[object, object, bool]:
    """Return (mesh, mask, synthetic_extrusion).

    Returns ``(None, None, False)`` when we don't have a segmenter for
    this body part — caller treats that as "no organ mesh", and lesion
    meshes still go in the scene.
    """
    if not body_part_key:
        return None, None, False
    segmenter = resolve_segmenter(body_part_key)
    if segmenter is None:
        return None, None, False

    # Single-slice CT/MR (e.g. pydicom's bundled CT_small/MR_small) is
    # effectively 2D — route through the breast/2D silhouette segmenter
    # so we still produce a usable extruded mesh. Real multi-slice
    # studies stay on the dedicated 3D segmenter.
    if series.is_2d:
        from app.services.twin.segment import BreastSegmenter

        mask_2d = BreastSegmenter().segment(series.volume, series.spacing_zyx)
        if mask_2d is None or not mask_2d.any():
            return None, None, False
        extrude_mm = max(5.0, 3.0 * series.spacing_zyx[1])
        m = mask_to_mesh(
            mask_2d,
            series.spacing_zyx,
            face_budget=cfg.ORGAN_FACE_BUDGET,
            extrude_z_mm=extrude_mm,
        )
        return m, mask_2d, True

    mask = segmenter.segment(series.volume, series.spacing_zyx)
    if mask is None or not mask.any():
        return None, None, False

    m = mask_to_mesh(
        mask,
        series.spacing_zyx,
        face_budget=cfg.ORGAN_FACE_BUDGET,
    )
    return m, mask, False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _volume_cm3(mask, spacing_zyx: tuple[float, float, float]) -> float:
    sz, sy, sx = spacing_zyx
    voxel_mm3 = sz * sy * sx
    return float(mask.sum()) * voxel_mm3 / 1000.0


def _write_glb(study_id, twin_id, data: bytes) -> Path:
    out_dir = Path(settings.artifact_dir) / str(study_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"twin_{cfg.SEG_CONFIG_VERSION}.glb"
    out_path.write_bytes(data)
    return out_path


def _short_err(exc: Exception) -> str:
    msg = f"{type(exc).__name__}: {exc}"
    return msg[:2000]


def _mark_failed(
    db: Session, twin: OrganTwin, job: Job | None, message: str
) -> None:
    twin.status = "failed"
    twin.error = message
    if job is not None:
        job.status = "failed"
        job.error = message[:2048]
        job.finished_at = datetime.now(timezone.utc)
    db.commit()
    log_event(
        db,
        actor_id=None,
        actor_role=None,
        action="twin.failed",
        resource_type="organ_twin",
        resource_id=str(twin.id),
        details={"error": message},
    )
