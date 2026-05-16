"""Model registry: routes (modality, body_part) → adapter."""
from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.dicom.validators import model_key_for
from app.models.base import Model
from app.models.brain_mri import BrainMRIModel
from app.models.breast_mammo import BreastMammoModel
from app.models.lung_ct import LungCTModel
from app.models.mock import MockModel


@lru_cache(maxsize=1)
def _registry() -> dict[str, Model]:
    if settings.mock_inference:
        return {
            "brain_mri": MockModel("MR", "BRAIN"),
            "lung_ct": MockModel("CT", "CHEST"),
            "breast_mammo": MockModel("MG", "BREAST"),
        }
    return {
        "brain_mri": BrainMRIModel(),
        "lung_ct": LungCTModel(),
        "breast_mammo": BreastMammoModel(),
    }


def resolve_model(modality: str, body_part: str) -> Model | None:
    key = model_key_for(modality, body_part)
    if key is None:
        return None
    return _registry().get(key)
