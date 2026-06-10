"""Tests for the MedGemma chat endpoint helpers.

We don't spin up TestClient (which would need a DB); instead we
exercise the prompt-building helper directly. The full HTTP shape is
covered by the docker-compose integration smoke test.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.api.v1.chat import _system_prompt, _sse


@dataclass
class StubStudy:
    modality: str = "MR"
    body_part: str = "BRAIN"
    description: str = "MRI brain w/ contrast"


@dataclass
class StubFinding:
    label: str
    body_part: str = "BRAIN"
    confidence: float | None = 0.42
    icd10_suggestion: str | None = "C71.9"
    model_name: str = "MockModel"
    model_version: str = "0.1.0"


def test_system_prompt_includes_findings_block():
    findings = [
        StubFinding(label="Suspected glioma"),
        StubFinding(label="Edema", icd10_suggestion="G93.6"),
    ]
    prompt = _system_prompt(StubStudy(), findings)  # type: ignore[arg-type]
    assert "RESEARCH ONLY" in prompt
    assert "Suspected glioma" in prompt
    assert "Edema" in prompt
    assert "MR BRAIN" in prompt or ("MR" in prompt and "BRAIN" in prompt)


def test_system_prompt_with_no_findings():
    prompt = _system_prompt(StubStudy(), [])  # type: ignore[arg-type]
    assert "(no AI findings produced)" in prompt
    assert "RESEARCH ONLY" in prompt


def test_sse_encoding():
    out = _sse({"delta": "hello"})
    assert out.startswith(b"data: ")
    assert out.endswith(b"\n\n")
    assert b'"delta"' in out and b'"hello"' in out


def test_sse_done_message():
    out = _sse({"done": True})
    assert b"done" in out and b"true" in out
