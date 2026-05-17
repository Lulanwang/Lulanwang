"""Tests for the longitudinal change-report path of MedGemmaNarrator."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pytest

from app.services.medgemma import (
    RESEARCH_DISCLAIMER,
    MedGemmaNarrator,
)


@dataclass
class StubStudy:
    modality: str
    body_part: str
    description: str
    study_date: datetime | None
    study_instance_uid: str = "1.2"


@dataclass
class StubFinding:
    label: str
    body_part: str = "BRAIN"
    confidence: float | None = 0.42
    icd10_suggestion: str | None = "C71.9"
    model_name: str = "MockModel"
    model_version: str = "0.1.0"


def _baseline() -> StubStudy:
    return StubStudy(
        modality="MR",
        body_part="BRAIN",
        description="initial",
        study_date=datetime(2025, 1, 1),
    )


def _follow_up() -> StubStudy:
    return StubStudy(
        modality="MR",
        body_part="BRAIN",
        description="follow-up",
        study_date=datetime(2026, 1, 1),
    )


@pytest.mark.asyncio
async def test_mock_compare_flags_new_and_resolved_findings():
    n = MedGemmaNarrator(backend="mock")
    baseline = [StubFinding(label="Suspected glioma")]
    follow_up = [
        StubFinding(label="Suspected glioma"),
        StubFinding(label="Peritumoral edema", icd10_suggestion="G93.6"),
    ]
    out = await n.compare_studies(
        baseline=_baseline(),  # type: ignore[arg-type]
        follow_up=_follow_up(),  # type: ignore[arg-type]
        baseline_findings=baseline,  # type: ignore[arg-type]
        follow_up_findings=follow_up,  # type: ignore[arg-type]
    )
    assert out.text is not None
    assert "Peritumoral edema" in out.text  # new
    assert "Suspected glioma" in out.text  # stable
    assert "Resolved" not in out.text  # nothing resolved
    assert RESEARCH_DISCLAIMER in out.text


@pytest.mark.asyncio
async def test_mock_compare_flags_resolved_only():
    n = MedGemmaNarrator(backend="mock")
    baseline = [StubFinding(label="Suspected glioma")]
    follow_up: list[StubFinding] = []
    out = await n.compare_studies(
        baseline=_baseline(),  # type: ignore[arg-type]
        follow_up=_follow_up(),  # type: ignore[arg-type]
        baseline_findings=baseline,  # type: ignore[arg-type]
        follow_up_findings=follow_up,
    )
    assert out.text is not None
    assert "Resolved" in out.text
    assert "Suspected glioma" in out.text


@pytest.mark.asyncio
async def test_mock_compare_handles_both_empty():
    n = MedGemmaNarrator(backend="mock")
    out = await n.compare_studies(
        baseline=_baseline(),  # type: ignore[arg-type]
        follow_up=_follow_up(),  # type: ignore[arg-type]
        baseline_findings=[],
        follow_up_findings=[],
    )
    assert out.text is not None
    assert "No AI findings" in out.text


def test_compare_studies_sync_wrapper():
    n = MedGemmaNarrator(backend="mock")
    out = n.compare_studies_sync(
        baseline=_baseline(),  # type: ignore[arg-type]
        follow_up=_follow_up(),  # type: ignore[arg-type]
        baseline_findings=[],
        follow_up_findings=[StubFinding(label="New mass")],  # type: ignore[arg-type]
    )
    assert out.text is not None
    assert "New" in out.text
    assert "New mass" in out.text
