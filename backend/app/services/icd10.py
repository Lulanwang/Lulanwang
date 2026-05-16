"""ICD-10 service.

Loads the curated cancer-relevant CSV at startup and exposes:
  - `search(q)` for the ICD-10 picker
  - `suggest_for(finding)` heuristic that the pipeline uses to
    pre-fill `icd10_suggestion` on each Finding

The curated subset covers brain (C71.x, D33.x, D43.x), lung (C34.x,
D14.3x, R91.x), and breast (C50.x, D24.x, R92.x). Full ICD-10-CM
ingestion is on the roadmap.
"""
from __future__ import annotations

import csv
import functools
import logging
import os
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

# Default location (mounted from repo root in dev; can be overridden).
DEFAULT_PATH = Path(os.environ.get("ICD10_CSV_PATH", "/app/data/icd10/cancer_codes.csv"))


@dataclass(frozen=True)
class ICD10Code:
    code: str
    description: str
    category: str  # malignant | benign | in_situ | uncertain | metastatic | finding | screening | history
    body_part: str  # brain | lung | breast


@functools.lru_cache(maxsize=1)
def all_codes() -> list[ICD10Code]:
    # The CSV is bundled into the image and also mounted in dev, so
    # this path resolves the same way in both contexts.
    candidates = [DEFAULT_PATH, Path(__file__).resolve().parents[3] / "data/icd10/cancer_codes.csv"]
    for p in candidates:
        if p.exists():
            with p.open(newline="") as f:
                return [
                    ICD10Code(
                        code=row["code"].strip(),
                        description=row["description"].strip(),
                        category=row["category"].strip(),
                        body_part=row["body_part"].strip(),
                    )
                    for row in csv.DictReader(f)
                ]
    log.warning("ICD-10 CSV not found in any candidate; service will be empty")
    return []


def search(q: str, limit: int = 25) -> list[ICD10Code]:
    q = (q or "").strip().lower()
    if not q:
        return all_codes()[:limit]
    out: list[ICD10Code] = []
    for c in all_codes():
        if q in c.code.lower() or q in c.description.lower():
            out.append(c)
            if len(out) >= limit:
                break
    return out


# Coarse mapping from finding label / body part → preferred code.
# The mock model populates `icd10_suggestion` directly; this is the
# fallback used when a real model returns a labeled finding without a
# pre-attached suggestion.
def suggest_for(label: str, body_part: str) -> str | None:
    bp = body_part.upper()
    lbl = label.lower()
    if bp in {"BRAIN", "HEAD"}:
        if "edema" in lbl:
            return "G93.6"
        if "metast" in lbl:
            return "C79.31"
        if "benign" in lbl:
            return "D33.2"
        if "uncertain" in lbl or "indeterminate" in lbl:
            return "D43.2"
        return "C71.9"
    if bp in {"LUNG", "CHEST", "THORAX"}:
        if "nodule" in lbl:
            return "R91.1"
        if "metast" in lbl:
            return "C78.00"
        if "benign" in lbl:
            return "D14.30"
        return "C34.90"
    if bp == "BREAST":
        if "microcalcific" in lbl or "calcific" in lbl:
            return "R92.0"
        if "in situ" in lbl or "dcis" in lbl:
            return "D05.90"
        if "benign" in lbl:
            return "D24.9"
        return "C50.919"
    return None
