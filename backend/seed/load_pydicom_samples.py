"""Seed the system with demo users + a few studies from pydicom samples.

Run:  docker compose exec backend python -m seed.load_pydicom_samples
"""
from __future__ import annotations

import asyncio
import logging
import sys

import pydicom
from pydicom.data import get_testdata_files

from app.core.config import settings
from app.core.security import hash_password
from app.db.models.user import User
from app.db.session import SessionLocal
from app.services.study_pipeline import enqueue_inference, ingest_datasets, run_inference

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("seed")


def ensure_users() -> None:
    with SessionLocal() as db:
        for email, pw, role, name in (
            (settings.seed_admin_email, settings.seed_admin_password, "admin", "Demo Admin"),
            (
                settings.seed_clinician_email,
                settings.seed_clinician_password,
                "clinician",
                "Demo Clinician",
            ),
        ):
            existing = db.query(User).filter(User.email == email).one_or_none()
            if existing:
                continue
            db.add(
                User(
                    email=email,
                    password_hash=hash_password(pw),
                    role=role,
                    full_name=name,
                    is_active=True,
                )
            )
        db.commit()
        log.info("seeded users (admin=%s, clinician=%s)", settings.seed_admin_email, settings.seed_clinician_email)


def _override_body_part(ds, modality: str, body_part: str) -> None:
    ds.Modality = modality
    ds.BodyPartExamined = body_part


async def ingest_demo_studies() -> None:
    """Pydicom ships small sample files; we re-tag them so each routes to a
    different model and the worklist shows all three cancer types."""
    # Only use samples known to ship with pydicom across versions.
    # No open mammography sample is bundled, so we re-tag CT_small.dcm
    # as MG/BREAST purely to exercise the routing + pipeline end-to-end.
    samples: list[tuple[str, str, str]] = [
        ("MR_small.dcm", "MR", "BRAIN"),
        ("CT_small.dcm", "CT", "CHEST"),
        ("CT_small.dcm", "MG", "BREAST"),
    ]

    for name, mod, bp in samples:
        paths = get_testdata_files(name)
        if not paths:
            log.warning("sample %s not bundled with pydicom; skipping", name)
            continue
        ds = pydicom.dcmread(paths[0])
        _override_body_part(ds, mod, bp)
        # Give each variant a unique StudyInstanceUID so they show as separate studies.
        from pydicom.uid import generate_uid

        ds.StudyInstanceUID = generate_uid()
        ds.SeriesInstanceUID = generate_uid()
        ds.SOPInstanceUID = generate_uid()
        # file_meta must agree with the dataset for Orthanc STOW.
        if ds.file_meta is not None:
            ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
        ds.StudyDescription = f"Demo {mod} {bp} (RESEARCH USE ONLY)"
        with SessionLocal() as db:
            try:
                study = await ingest_datasets(
                    db, [ds], actor_id=None, actor_role="system", request_id="seed"
                )
                job = enqueue_inference(db, study)
                run_inference(db, job.id)
                log.info("seeded study %s (%s/%s)", study.id, mod, bp)
            except Exception:
                log.exception("failed to seed sample %s", name)


def main() -> int:
    ensure_users()
    asyncio.run(ingest_demo_studies())
    print(
        "\nSeed complete. Login as:\n"
        f"  admin     {settings.seed_admin_email} / {settings.seed_admin_password}\n"
        f"  clinician {settings.seed_clinician_email} / {settings.seed_clinician_password}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
