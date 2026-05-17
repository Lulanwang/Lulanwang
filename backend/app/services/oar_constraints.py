"""Organ-at-risk dose constraints (published RTOG / QUANTEC values).

The constraint table is illustrative — it covers common organs across
brain, head-and-neck, thorax, abdomen, and pelvis. The thresholds match
widely-cited published values but are NOT a substitute for institutional
constraint sheets or a regulated TPS. Anything that consumes this
module must badge its output as RESEARCH USE ONLY.

API:
  - CONSTRAINTS — the raw table
  - lookup(tissue) → list[OarConstraint] (case-insensitive)
  - evaluate(tissue, dose_summary) → list[ConstraintEvaluation]

A ConstraintEvaluation carries `status` ∈ {"pass", "warn", "fail"} so
the UI can color-code each row.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Severity = Literal["pass", "warn", "fail"]
Metric = Literal["mean", "max", "v20", "v30", "d33", "d2cc"]


@dataclass(frozen=True)
class OarConstraint:
    tissue: str
    metric: Metric
    limit_gy: float
    severity_on_breach: Severity
    rationale: str
    source: str  # "QUANTEC", "RTOG-0813", etc.


# Spelled out per organ. Mean-dose constraints use "mean"; max-dose use
# "max"; V20 means "volume receiving ≥20 Gy expressed as a fraction 0..1".
CONSTRAINTS: list[OarConstraint] = [
    # Brain & head
    OarConstraint("brainstem", "max", 54.0, "fail",
                  "Max dose to brainstem ≤54 Gy", "QUANTEC"),
    OarConstraint("optic_chiasm", "max", 55.0, "fail",
                  "Max dose to optic chiasm ≤55 Gy", "QUANTEC"),
    OarConstraint("optic_nerve", "max", 55.0, "fail",
                  "Max dose to optic nerve ≤55 Gy", "QUANTEC"),
    OarConstraint("cochlea", "mean", 45.0, "warn",
                  "Mean dose to cochlea ≤45 Gy to limit hearing loss", "QUANTEC"),
    OarConstraint("lens", "max", 7.0, "fail",
                  "Max dose to lens ≤7 Gy", "QUANTEC"),

    # Head and neck
    OarConstraint("parotid_left", "mean", 26.0, "warn",
                  "Mean dose to parotid ≤26 Gy (xerostomia)", "QUANTEC"),
    OarConstraint("parotid_right", "mean", 26.0, "warn",
                  "Mean dose to parotid ≤26 Gy (xerostomia)", "QUANTEC"),
    OarConstraint("spinal_cord", "max", 50.0, "fail",
                  "Max dose to spinal cord ≤50 Gy", "QUANTEC"),
    OarConstraint("larynx", "mean", 45.0, "warn",
                  "Mean dose to larynx ≤45 Gy", "QUANTEC"),
    OarConstraint("mandible", "max", 70.0, "fail",
                  "Max dose to mandible ≤70 Gy (osteoradionecrosis)", "QUANTEC"),

    # Thorax
    OarConstraint("lung_left", "v20", 0.30, "warn",
                  "Lung V20 ≤30% (pneumonitis)", "QUANTEC"),
    OarConstraint("lung_right", "v20", 0.30, "warn",
                  "Lung V20 ≤30% (pneumonitis)", "QUANTEC"),
    OarConstraint("lung_total", "mean", 20.0, "warn",
                  "Mean lung dose ≤20 Gy", "QUANTEC"),
    OarConstraint("heart", "mean", 26.0, "warn",
                  "Mean heart dose ≤26 Gy (pericarditis)", "QUANTEC"),
    OarConstraint("heart", "v30", 0.46, "warn",
                  "Heart V30 ≤46%", "QUANTEC"),
    OarConstraint("esophagus", "mean", 34.0, "warn",
                  "Mean esophagus dose ≤34 Gy", "QUANTEC"),

    # Abdomen
    OarConstraint("liver", "mean", 30.0, "warn",
                  "Mean liver dose ≤30 Gy (RILD)", "QUANTEC"),
    OarConstraint("kidney_left", "mean", 18.0, "warn",
                  "Mean kidney dose ≤18 Gy", "QUANTEC"),
    OarConstraint("kidney_right", "mean", 18.0, "warn",
                  "Mean kidney dose ≤18 Gy", "QUANTEC"),
    OarConstraint("stomach", "max", 54.0, "warn",
                  "Max stomach dose ≤54 Gy", "QUANTEC"),

    # Pelvis
    OarConstraint("bladder", "mean", 65.0, "warn",
                  "Mean bladder dose ≤65 Gy", "QUANTEC"),
    OarConstraint("rectum", "mean", 50.0, "warn",
                  "Mean rectum dose ≤50 Gy", "QUANTEC"),
    OarConstraint("femoral_head_left", "max", 50.0, "warn",
                  "Max femoral head ≤50 Gy", "QUANTEC"),
    OarConstraint("femoral_head_right", "max", 50.0, "warn",
                  "Max femoral head ≤50 Gy", "QUANTEC"),
]


@dataclass(frozen=True)
class ConstraintEvaluation:
    constraint: OarConstraint
    observed: float
    status: Severity


WARN_RATIO = 0.85  # within 15% of limit → warn


def lookup(tissue: str) -> list[OarConstraint]:
    """All constraints registered for a tissue (case-insensitive)."""
    needle = tissue.lower()
    return [c for c in CONSTRAINTS if c.tissue.lower() == needle]


def supported_tissues() -> list[str]:
    return sorted({c.tissue for c in CONSTRAINTS})


def evaluate(tissue: str, dose_summary: dict) -> list[ConstraintEvaluation]:
    """Given a per-OAR dose dict like
        {"mean": 22.1, "max": 38.4, "v20": 0.27, "v30": 0.11}
    return one ConstraintEvaluation per registered constraint for the tissue.

    Pass: observed comfortably under limit. Warn: within WARN_RATIO of
    the limit but still below. Fail: at or above the limit.
    """
    out: list[ConstraintEvaluation] = []
    for c in lookup(tissue):
        observed = dose_summary.get(c.metric)
        if observed is None:
            continue
        if observed >= c.limit_gy:
            status: Severity = c.severity_on_breach
        elif observed >= c.limit_gy * WARN_RATIO:
            status = "warn"
        else:
            status = "pass"
        out.append(ConstraintEvaluation(constraint=c, observed=observed, status=status))
    return out
