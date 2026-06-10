"""RADS (Reporting And Data System) scoring schemes.

Three published schemes are supported:
  - BI-RADS  — breast mammography (ACR)
  - Lung-RADS — lung CT screening (ACR)
  - BT-RADS  — brain tumor follow-up (Emory Univ., widely adopted)

The picker UI determines which scheme to offer for a given
(modality, body_part). Scores are stored in `findings.geometry.rads`
(JSONB) — no schema migration. Validation happens here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

Scheme = Literal["BI-RADS", "Lung-RADS", "BT-RADS"]


@dataclass(frozen=True)
class RadsCode:
    scheme: Scheme
    code: str
    descriptor: str


BI_RADS: list[RadsCode] = [
    RadsCode("BI-RADS", "0", "Incomplete — need additional imaging"),
    RadsCode("BI-RADS", "1", "Negative"),
    RadsCode("BI-RADS", "2", "Benign"),
    RadsCode("BI-RADS", "3", "Probably benign — short-interval follow-up"),
    RadsCode("BI-RADS", "4A", "Low suspicion for malignancy"),
    RadsCode("BI-RADS", "4B", "Moderate suspicion for malignancy"),
    RadsCode("BI-RADS", "4C", "High suspicion for malignancy"),
    RadsCode("BI-RADS", "5", "Highly suggestive of malignancy"),
    RadsCode("BI-RADS", "6", "Known biopsy-proven malignancy"),
]

LUNG_RADS: list[RadsCode] = [
    RadsCode("Lung-RADS", "1", "Negative"),
    RadsCode("Lung-RADS", "2", "Benign appearance / behavior"),
    RadsCode("Lung-RADS", "3", "Probably benign"),
    RadsCode("Lung-RADS", "4A", "Suspicious"),
    RadsCode("Lung-RADS", "4B", "Very suspicious"),
    RadsCode("Lung-RADS", "4X", "Suspicious with additional features"),
]

BT_RADS: list[RadsCode] = [
    RadsCode("BT-RADS", "0", "Baseline — limited assessment"),
    RadsCode("BT-RADS", "1a", "Improved — definitely treatment effect"),
    RadsCode("BT-RADS", "1b", "Improved — probable treatment effect"),
    RadsCode("BT-RADS", "2", "Unchanged"),
    RadsCode("BT-RADS", "3a", "Slight worsening — probable treatment effect"),
    RadsCode("BT-RADS", "3b", "Worsening — equivocal"),
    RadsCode("BT-RADS", "3c", "Worsening — probable tumor progression"),
    RadsCode("BT-RADS", "4", "Highly suspicious for progression"),
]

ALL: dict[Scheme, list[RadsCode]] = {
    "BI-RADS": BI_RADS,
    "Lung-RADS": LUNG_RADS,
    "BT-RADS": BT_RADS,
}


def applicable_scheme(modality: str, body_part: str) -> Scheme | None:
    """Pick the scheme for a given (modality, body_part). Returns None when
    no scheme applies."""
    m = (modality or "").upper()
    bp = (body_part or "").upper()
    if m == "MG" or bp == "BREAST":
        return "BI-RADS"
    if m == "CT" and bp in ("CHEST", "LUNG", "THORAX"):
        return "Lung-RADS"
    if m == "MR" and bp in ("BRAIN", "HEAD"):
        return "BT-RADS"
    return None


def codes_for(scheme: Scheme) -> list[RadsCode]:
    return ALL[scheme]


def validate(scheme: Scheme, code: str) -> RadsCode:
    """Returns the matched RadsCode or raises ValueError."""
    if scheme not in ALL:
        raise ValueError(f"unknown scheme: {scheme}")
    for c in ALL[scheme]:
        if c.code == code:
            return c
    raise ValueError(f"unknown {scheme} code: {code}")


def build_score(
    *,
    scheme: Scheme,
    code: str,
    scored_by: str | None = None,
) -> dict:
    """Build the dict that gets stored in finding.geometry['rads']."""
    matched = validate(scheme, code)
    return {
        "scheme": matched.scheme,
        "code": matched.code,
        "descriptor": matched.descriptor,
        "scored_by": scored_by,
        "scored_at": datetime.now(timezone.utc).isoformat(),
    }


def coded_value(score: dict) -> dict:
    """For DICOM SR ContentSequence.ConceptCodeSequence — bare coded value."""
    return {
        "CodeValue": score["code"],
        "CodingSchemeDesignator": score["scheme"],
        "CodeMeaning": score["descriptor"],
    }
