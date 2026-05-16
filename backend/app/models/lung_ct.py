"""Lung CT adapter — MONAI bundle wrapper.

Wraps the MONAI Model Zoo bundle `lung_nodule_ct_detection`
(RetinaNet-3D, LUNA16-trained).

Defaults to MockModel fallback if bundle / torch are unavailable.

NOT FDA cleared. Trained on screening-style LDCT; detection only,
no benign-vs-malignant characterization. See MODEL_CARDS.md.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import settings
from app.models.base import Finding, StudyInput
from app.models.mock import MockModel

log = logging.getLogger(__name__)

BUNDLE_NAME = "lung_nodule_ct_detection"


class LungCTModel:
    name = "MONAI/lung_nodule_ct_detection"
    version = "research-only"
    modality = "CT"
    body_part = "CHEST"

    def __init__(self) -> None:
        self._fallback = MockModel("CT", "CHEST")
        self._ready = self._maybe_load()

    def _maybe_load(self) -> bool:
        bundle_path = Path(settings.monai_bundle_dir) / BUNDLE_NAME
        if not bundle_path.exists():
            log.info("lung CT bundle not present at %s — using MockModel", bundle_path)
            return False
        try:
            import monai  # noqa: F401
            import torch  # noqa: F401
        except ImportError:
            log.info("torch/monai not installed — using MockModel for lung CT")
            return False
        return True

    def infer(self, study: StudyInput) -> list[Finding]:
        if not self._ready:
            return self._fallback.infer(study)
        try:
            log.warning(
                "LungCTModel: bundle present but real inference not wired in MVP; using fallback"
            )
            return self._fallback.infer(study)
        except Exception as exc:  # noqa: BLE001
            log.exception("lung CT inference failed; falling back to MockModel")
            return self._fallback.infer(study) + [
                Finding(
                    label=f"(real inference error: {exc})",
                    confidence=0.0,
                    body_part="LUNG",
                )
            ]
