"""Download MONAI Model Zoo bundles for real (non-mock) inference.

Run: docker compose exec backend python -m seed.download_monai_bundles

WARNING: Pulls ~1.5 GB of model weights from MONAI / HuggingFace.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from app.core.config import settings

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("download-bundles")

BUNDLES = ["brats_mri_segmentation", "lung_nodule_ct_detection"]


def main() -> int:
    try:
        from monai.bundle import download
    except ImportError:
        log.error("MONAI is not installed in this image; nothing to download.")
        return 1
    out = Path(settings.monai_bundle_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name in BUNDLES:
        log.info("downloading bundle: %s", name)
        try:
            download(name=name, bundle_dir=str(out))
        except Exception:
            log.exception("failed to download bundle %s — adapter will use MockModel", name)
    log.info("done. Set MOCK_INFERENCE=false and restart backend to use real models.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
