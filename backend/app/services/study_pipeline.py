"""Study lifecycle pipeline.

State machine:
  received → deidentified → queued → inferring → inferred → reported → signed

This module is the single place that mutates `Study.state`; everywhere
else just reads it. The pipeline is intentionally synchronous within a
BackgroundTask — no Celery, no Redis. Crash recovery is handled on
backend boot (see workers/background.py).
"""
from __future__ import annotations

import logging
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydicom import Dataset
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.config import settings
from app.db.models.finding import Finding as FindingRow
from app.db.models.job import Job
from app.db.models.patient import Patient
from app.db.models.report import Report
from app.db.models.study import Study
from app.dicom.deidentify import deidentify
from app.dicom.parse import extract_study_meta
from app.dicom.sr_tid1500 import SRFinding, build_sr, save_sr
from app.fhir.diagnostic_report import diagnostic_report
from app.models.base import StudyInput
from app.models.registry import resolve_model
from app.services import icd10, orthanc_client

log = logging.getLogger(__name__)


async def ingest_datasets(
    db: Session,
    datasets: list[Dataset],
    *,
    actor_id: uuid.UUID | None,
    actor_role: str | None,
    request_id: str | None,
) -> Study:
    """De-identify, register patient/study, STOW to Orthanc, return Study row."""
    if not datasets:
        raise ValueError("no datasets")

    # 1) De-identify in-place (all instances share a patient → same pseudonym/shift)
    results = [deidentify(ds) for ds in datasets]
    blocked = [r for r in results if not r.ok]
    if blocked:
        raise ValueError(f"ingestion blocked: {blocked[0].blocked_reason}")

    pseudonym = results[0].pseudonym
    date_shift = results[0].date_shift_days

    # 2) Get-or-create Patient
    patient = db.query(Patient).filter(Patient.pseudonym == pseudonym).one_or_none()
    if patient is None:
        patient = Patient(pseudonym=pseudonym, date_shift_days=date_shift)
        db.add(patient)
        db.flush()

    # 3) Get-or-create Study (from the first dataset's meta)
    meta = extract_study_meta(datasets[0])
    study = (
        db.query(Study)
        .filter(Study.study_instance_uid == meta.study_instance_uid)
        .one_or_none()
    )
    if study is None:
        study = Study(
            patient_id=patient.id,
            study_instance_uid=meta.study_instance_uid,
            modality=meta.modality,
            body_part=meta.body_part,
            study_date=meta.study_date,
            description=meta.description,
            state="deidentified",
        )
        db.add(study)
        db.flush()
    else:
        study.state = "deidentified"

    # 4) Push to Orthanc
    await orthanc_client.stow_datasets(datasets)

    db.commit()
    db.refresh(study)

    log_event(
        db,
        actor_id=actor_id,
        actor_role=actor_role,
        action="study.ingested",
        resource_type="study",
        resource_id=str(study.id),
        request_id=request_id,
        details={"study_instance_uid": study.study_instance_uid, "instances": len(datasets)},
    )
    return study


def enqueue_inference(db: Session, study: Study) -> Job:
    model = resolve_model(study.modality, study.body_part)
    job = Job(
        study_id=study.id,
        model_name=model.name if model else "(no-model)",
        model_version=model.version if model else "0",
        status="queued",
    )
    db.add(job)
    study.state = "queued"
    db.commit()
    db.refresh(job)
    return job


def run_inference(db: Session, job_id: uuid.UUID) -> None:
    """Runs in a BackgroundTask. Must not raise — errors are persisted."""
    job = db.get(Job, job_id)
    if job is None:
        log.warning("run_inference: job %s not found", job_id)
        return
    study = db.get(Study, job.study_id)
    if study is None:
        job.status = "failed"
        job.error = "study not found"
        db.commit()
        return

    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    study.state = "inferring"
    db.commit()

    try:
        # For MVP we don't re-fetch instances from Orthanc; we pass an
        # empty dataset list to the model. Real adapters either rely on
        # MockModel (the default) or would WADO-RS pull instances here.
        model = resolve_model(study.modality, study.body_part)
        if model is None:
            raise RuntimeError(
                f"no model registered for {study.modality}/{study.body_part}"
            )
        with tempfile.TemporaryDirectory() as td:
            study_input = StudyInput(
                study_instance_uid=study.study_instance_uid,
                modality=study.modality,
                body_part=study.body_part,
                datasets=[],
                tempdir=td,
            )
            findings = model.infer(study_input)

        for f in findings:
            icd = f.icd10_suggestion or icd10.suggest_for(f.label, f.body_part)
            db.add(
                FindingRow(
                    study_id=study.id,
                    job_id=job.id,
                    label=f.label,
                    body_part=f.body_part,
                    confidence=f.confidence,
                    icd10_suggestion=icd,
                    geometry=f.geometry or None,
                    model_name=model.name,
                    model_version=model.version,
                )
            )

        job.status = "succeeded"
        job.finished_at = datetime.now(timezone.utc)
        job.result = {"finding_count": len(findings)}
        study.state = "inferred"
        db.commit()

        # Auto-generate a draft report so the demo is one click away
        generate_report(db, study.id, signed_by=None)

        log_event(
            db,
            actor_id=None,
            actor_role="system",
            action="inference.completed",
            resource_type="study",
            resource_id=str(study.id),
            request_id=None,
            details={"job_id": str(job.id), "finding_count": len(findings)},
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("run_inference failed for job %s", job_id)
        job.status = "failed"
        job.error = str(exc)[:2000]
        job.finished_at = datetime.now(timezone.utc)
        study.state = "failed"
        study.error = str(exc)[:1000]
        db.commit()


def generate_report(db: Session, study_id: uuid.UUID, *, signed_by: uuid.UUID | None) -> Report:
    study = db.get(Study, study_id)
    if study is None:
        raise ValueError(f"study {study_id} not found")
    patient = db.get(Patient, study.patient_id)
    pseudonym = patient.pseudonym if patient else "unknown"

    findings = db.query(FindingRow).filter(FindingRow.study_id == study.id).all()
    icd_codes = sorted({f.icd10_suggestion for f in findings if f.icd10_suggestion})

    impression_lines = [f"- {f.label} (confidence={f.confidence:.2f})" for f in findings]
    if not impression_lines:
        impression_lines = ["- No AI findings produced."]
    impression = "AI-generated draft impression:\n" + "\n".join(impression_lines)

    sr_findings = [
        SRFinding(
            label=f.label,
            confidence=f.confidence,
            icd10=f.icd10_suggestion,
            model_name=f.model_name,
            model_version=f.model_version,
        )
        for f in findings
    ]
    sr = build_sr(
        study_instance_uid=study.study_instance_uid,
        patient_pseudonym=pseudonym,
        modality=study.modality,
        findings=sr_findings,
        impression=impression,
    )
    artifact_dir = Path(settings.artifact_dir) / str(study.id)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    sr_path = artifact_dir / "report_sr.dcm"
    save_sr(sr, sr_path)

    fhir_dr = diagnostic_report(
        study_instance_uid=study.study_instance_uid,
        patient_pseudonym=pseudonym,
        modality=study.modality,
        impression=impression,
        icd10_codes=list(icd_codes),
        model_name=findings[0].model_name if findings else "MockModel",
        model_version=findings[0].model_version if findings else "0.0",
    )

    report = (
        db.query(Report).filter(Report.study_id == study.id).order_by(Report.created_at.desc()).first()
    )
    if report is None:
        report = Report(study_id=study.id)
        db.add(report)
    report.impression = impression
    report.icd10_codes = list(icd_codes)
    report.sr_path = str(sr_path)
    report.fhir_diagnostic_report = fhir_dr
    if signed_by:
        report.signed_by = signed_by
        report.signed_at = datetime.now(timezone.utc)
        study.state = "signed"
    else:
        study.state = "reported"
    db.commit()
    db.refresh(report)
    return report
