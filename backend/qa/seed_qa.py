"""Seed the QA database. Mirrors `seed/load_pydicom_samples.py` but
monkey-patches `orthanc_client.stow_datasets` to a no-op, because
Orthanc isn't available in this environment.

Run BEFORE booting the uvicorn server so the schema + rows are ready.
"""
from __future__ import annotations

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

# Ensure backend/ is on sys.path so `app.*` and `seed.*` resolve when this
# file is run as a script from any cwd.
_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("qa.seed")


async def _noop_stow(datasets):  # noqa: D401, ANN001
    """Replacement for orthanc_client.stow_datasets — does nothing."""
    return {"qa_stub": True, "instances": sum(1 for _ in datasets)}


def main() -> int:
    from app.services import orthanc_client

    orthanc_client.stow_datasets = _noop_stow  # type: ignore[assignment]

    from seed.load_pydicom_samples import (
        ensure_users,
        ingest_pydicom_samples,
        ingest_synthetic_studies,
    )

    ensure_users()
    asyncio.run(ingest_synthetic_studies())
    asyncio.run(ingest_pydicom_samples())
    log.info("QA seed complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
