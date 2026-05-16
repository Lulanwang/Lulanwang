"""Deterministic mock inference adapter.

Lets the entire pipeline (PACS → infer → ICD-10 → SR/FHIR → audit) run
without GPUs or model weights. Each finding is keyed off the modality
and body part so the demo shows realistic-looking AI outputs.
"""
from __future__ import annotations

from app.models.base import Finding, Model, StudyInput

_PROFILES = {
    ("MR", "BRAIN"): [
        Finding(
            label="Suspected glioma (mock)",
            confidence=0.42,
            body_part="BRAIN",
            icd10_suggestion="C71.9",
            geometry={"kind": "bbox", "x": 0.45, "y": 0.40, "w": 0.15, "h": 0.18},
        ),
        Finding(
            label="Peritumoral edema (mock)",
            confidence=0.39,
            body_part="BRAIN",
            icd10_suggestion="G93.6",
        ),
    ],
    ("CT", "CHEST"): [
        Finding(
            label="Solitary pulmonary nodule, 9 mm (mock)",
            confidence=0.51,
            body_part="LUNG",
            icd10_suggestion="R91.1",
            geometry={"kind": "bbox", "x": 0.62, "y": 0.55, "w": 0.04, "h": 0.04},
        ),
        Finding(
            label="Suspicious right upper lobe lesion (mock)",
            confidence=0.34,
            body_part="LUNG",
            icd10_suggestion="C34.11",
        ),
    ],
    ("MG", "BREAST"): [
        Finding(
            label="Suspicious cluster of microcalcifications, upper outer quadrant (mock)",
            confidence=0.47,
            body_part="BREAST",
            icd10_suggestion="R92.0",
            geometry={"kind": "bbox", "x": 0.30, "y": 0.25, "w": 0.10, "h": 0.10},
        ),
        Finding(
            label="Possible mass, left breast UOQ (mock)",
            confidence=0.38,
            body_part="BREAST",
            icd10_suggestion="C50.412",
        ),
    ],
}


class MockModel:
    name = "MockModel"
    version = "0.1.0"

    def __init__(self, modality: str, body_part: str):
        self.modality = modality.upper()
        self.body_part = body_part.upper()

    def infer(self, study: StudyInput) -> list[Finding]:
        key = (self.modality, self.body_part)
        # Fallback to a generic finding if we don't have a profile
        return _PROFILES.get(
            key,
            [
                Finding(
                    label=f"No-op mock finding for {self.modality}/{self.body_part}",
                    confidence=0.10,
                    body_part=self.body_part,
                )
            ],
        )
