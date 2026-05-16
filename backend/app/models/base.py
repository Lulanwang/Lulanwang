"""Model interface + Finding dataclass.

All AI adapters implement this protocol so the pipeline can route
studies to whichever model matches `(modality, body_part)`. Mock
adapters and real MONAI bundle wrappers share the same surface.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from pydicom import Dataset


@dataclass
class StudyInput:
    """Lightweight container handed to a Model.

    `datasets` is the list of pydicom Datasets for the study (already
    de-identified). `tempdir` is a writable scratch directory for
    intermediate volumes / MONAI bundle outputs.
    """

    study_instance_uid: str
    modality: str
    body_part: str
    datasets: list[Dataset]
    tempdir: str


@dataclass
class Finding:
    label: str
    confidence: float
    body_part: str
    icd10_suggestion: str | None = None
    geometry: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Model(Protocol):
    name: str
    version: str
    modality: str
    body_part: str

    def infer(self, study: StudyInput) -> list[Finding]: ...
