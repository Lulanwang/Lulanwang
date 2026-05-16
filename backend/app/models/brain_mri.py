"""Brain MRI adapter — MONAI bundle wrapper.

Wraps the MONAI Model Zoo bundle `brats_mri_segmentation` (whole tumor,
tumor core, enhancing tumor segmentation on multimodal brain MRI).

Defaults to falling back to MockModel if MONAI/Torch is not installed
or the bundle has not been downloaded — keeps `docker compose up`
fast and deterministic.

NOT FDA cleared. Trained on adult glioma (BraTS); performance on
pediatric tumors, metastases, meningiomas, or non-tumor lesions is
undefined. See MODEL_CARDS.md.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import settings
from app.models.base import Finding, StudyInput
from app.models.mock import MockModel

log = logging.getLogger(__name__)

BUNDLE_NAME = "brats_mri_segmentation"


class BrainMRIModel:
    name = "MONAI/brats_mri_segmentation"
    version = "research-only"
    modality = "MR"
    body_part = "BRAIN"

    def __init__(self) -> None:
        self._fallback = MockModel("MR", "BRAIN")
        self._ready = self._maybe_load()

    def _maybe_load(self) -> bool:
        bundle_path = Path(settings.monai_bundle_dir) / BUNDLE_NAME
        if not bundle_path.exists():
            log.info("brain MRI bundle not present at %s — using MockModel", bundle_path)
            return False
        try:
            # Import lazily so the backend boots even without torch.
            import monai  # noqa: F401
            import torch  # noqa: F401
        except ImportError:
            log.info("torch/monai not installed — using MockModel for brain MRI")
            return False
        # We don't actually load the bundle in __init__ to avoid blocking
        # boot; the real bundle inference runs in `infer`.
        return True

    def infer(self, study: StudyInput) -> list[Finding]:
        if not self._ready:
            return self._fallback.infer(study)
        try:
            # The MONAI bundle inference would go here. For MVP we keep
            # the integration intentionally minimal: load the bundle,
            # build the inference workflow, and run it on a stacked
            # volume. The output mask would be converted to a Finding
            # with volume in mL and a saved DICOM SEG path in geometry.
            #
            # This is a placeholder that runs the fallback so the
            # plumbing is exercised in CI without requiring weights.
            log.warning(
                "BrainMRIModel: bundle present but real inference not wired in MVP; using fallback"
            )
            return self._fallback.infer(study)
        except Exception as exc:  # noqa: BLE001
            log.exception("brain MRI inference failed; falling back to MockModel")
            return self._fallback.infer(study) + [
                Finding(
                    label=f"(real inference error: {exc})",
                    confidence=0.0,
                    body_part="BRAIN",
                )
            ]
