"""Seed the QA database. Mirrors `seed/load_pydicom_samples.py` but
optionally stubs `orthanc_client.stow_datasets` to a no-op when Orthanc
isn't available.

Run BEFORE booting the uvicorn server so the schema + rows are ready.

Flags:
    --with-orthanc   Push the synthetic DICOMs into Orthanc too (required
                     for Round 11 viewer + thumbnail tests). When omitted,
                     STOW is stubbed.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Make sure DATABASE_URL points at the local Postgres BEFORE importing
# any app modules — pydantic-settings caches at import time.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://lulan:lulan_dev_password@localhost:5432/app",
)
os.environ.setdefault("ORTHANC_URL", "http://localhost:8042")
# Orthanc QA config has auth disabled; the client still sends a basic-auth
# header which Orthanc ignores. Provide deterministic creds anyway.
os.environ.setdefault("ORTHANC_USER", "qa")
os.environ.setdefault("ORTHANC_PASSWORD", "qa")

# Ensure backend/ is on sys.path so `app.*` and `seed.*` resolve when this
# file is run as a script from any cwd.
_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("qa.seed")


async def _noop_stow(datasets):  # noqa: D401, ANN001
    """Replacement for orthanc_client.stow_datasets — does nothing."""
    return {"qa_stub": True, "instances": sum(1 for _ in datasets)}


async def _direct_stow(datasets):  # noqa: ANN001
    """Push DICOMs to Orthanc via the native REST API (`POST /instances`)
    instead of DICOMweb STOW-RS. The bundled `orthanc-dicomweb` plugin
    in Ubuntu's package rejects the `multipart/form-data` body that
    httpx produces; the native endpoint takes the raw DICOM bytes and
    just works.
    """
    import io

    import httpx
    import pydicom

    base = os.environ.get("ORTHANC_URL", "http://localhost:8042").rstrip("/")
    pushed = 0
    async with httpx.AsyncClient(timeout=60.0) as client:
        for ds in datasets:
            buf = io.BytesIO()
            pydicom.dcmwrite(buf, ds, enforce_file_format=True)
            r = await client.post(
                f"{base}/instances",
                content=buf.getvalue(),
                headers={"Content-Type": "application/dicom"},
            )
            r.raise_for_status()
            pushed += 1
    log.info("direct STOW pushed %d instances to Orthanc", pushed)
    return {"instances": pushed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--with-orthanc",
        action="store_true",
        help="Push DICOMs into a live Orthanc at $ORTHANC_URL "
        "(instead of stubbing stow_datasets).",
    )
    args = parser.parse_args()

    from app.services import orthanc_client

    if args.with_orthanc:
        # Replace the DICOMweb STOW-RS path with native REST (see comment
        # on _direct_stow). The DICOMweb proxy that the Cornerstone viewer
        # uses still queries via `/dicom-web/studies/...`, which works
        # fine — only the upload path is broken with this Orthanc build.
        orthanc_client.stow_datasets = _direct_stow  # type: ignore[assignment]
    else:
        orthanc_client.stow_datasets = _noop_stow  # type: ignore[assignment]

    from seed.load_pydicom_samples import (
        ensure_users,
        ingest_pydicom_samples,
        ingest_synthetic_studies,
    )

    ensure_users()
    asyncio.run(ingest_synthetic_studies())
    asyncio.run(ingest_pydicom_samples())
    log.info("QA seed complete (with_orthanc=%s)", args.with_orthanc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

