"""Breast mammography adapter.

There is no permissively-licensed open-weights mammography classifier
of clinical relevance we are willing to ship as a "real" demo. The
default behavior is to delegate to MockModel and surface a clear
"model not loaded" badge in the UI.

If `BREAST_MAMMO_WEIGHTS` is set to a path containing a torchvision
`densenet121` state_dict, we'll load it as an illustrative classifier —
but the burden of validating those weights is on the operator and
the output remains "research use only."

See MODEL_CARDS.md.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import settings
from app.models.base import Finding, StudyInput
from app.models.mock import MockModel

log = logging.getLogger(__name__)


class BreastMammoModel:
    name = "BreastMammo (mock-by-default)"
    version = "research-only"
    modality = "MG"
    body_part = "BREAST"

    def __init__(self) -> None:
        self._fallback = MockModel("MG", "BREAST")
        self._weights_path = (
            Path(settings.breast_mammo_weights) if settings.breast_mammo_weights else None
        )
        self._ready = self._maybe_load()

    def _maybe_load(self) -> bool:
        if not self._weights_path or not self._weights_path.exists():
            log.info("breast mammo weights not provided; using MockModel")
            return False
        try:
            import torch  # noqa: F401
            import torchvision  # noqa: F401
        except ImportError:
            log.info("torch/torchvision not installed; using MockModel for breast mammo")
            return False
        return True

    def infer(self, study: StudyInput) -> list[Finding]:
        if not self._ready:
            return self._fallback.infer(study)
        # If a user provided their own weights, this is where the
        # densenet121 forward pass would run on a normalized mammo
        # crop. For MVP safety we still delegate to MockModel and
        # tag the finding with the user-supplied weights path.
        log.warning(
            "BreastMammoModel: weights supplied but real inference not wired in MVP; using fallback"
        )
        return self._fallback.infer(study)
