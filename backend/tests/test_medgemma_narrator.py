"""Tests for the MedGemma narrative writer.

In-process only — never hits a real HF endpoint. The hf-backend tests
monkeypatch httpx.AsyncClient.post so we exercise the request shaping
+ response parsing logic without network.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import pytest

from app.services.medgemma import (
    RESEARCH_DISCLAIMER,
    MedGemmaNarrator,
    NarrativeResult,
    build_narrator,
)


@dataclass
class StubStudy:
    study_instance_uid: str = "1.2.3.4"
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


def _findings() -> list[StubFinding]:
    return [
        StubFinding(label="Suspected glioma"),
        StubFinding(label="Edema", confidence=0.31, icd10_suggestion="G93.6"),
    ]


@pytest.mark.asyncio
async def test_mock_backend_produces_deterministic_narrative():
    narrator = MedGemmaNarrator(backend="mock")
    out = await narrator.narrate(study=StubStudy(), findings=_findings())  # type: ignore[arg-type]
    assert out.backend == "mock"
    assert out.text is not None
    assert RESEARCH_DISCLAIMER in out.text
    assert "Suspected glioma" in out.text
    assert "Edema" in out.text
    assert "C71.9" in out.text
    assert "MR" in out.text and "BRAIN" in out.text
    assert out.error is None


@pytest.mark.asyncio
async def test_mock_backend_handles_empty_findings():
    narrator = MedGemmaNarrator(backend="mock")
    out = await narrator.narrate(study=StubStudy(), findings=[])  # type: ignore[arg-type]
    assert out.text is not None
    assert "No AI findings" in out.text
    assert RESEARCH_DISCLAIMER in out.text


@pytest.mark.asyncio
async def test_hf_backend_calls_endpoint_and_returns_text(monkeypatch):
    captured: dict[str, Any] = {}

    class _Resp:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> Any:
            # OpenAI-compatible chat completions response (vLLM/TGI).
            return {
                "id": "stub",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "AI narrative: looks like a small mass.",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 10},
            }

    class _Client:
        def __init__(self, *args, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return _Resp()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    narrator = MedGemmaNarrator(
        backend="hf",
        hf_endpoint_url="https://endpoint.test",
        hf_token="hf_test_token",
        max_new_tokens=128,
        model_id="google/medgemma-27b-text-it",
    )
    out = await narrator.narrate(study=StubStudy(), findings=_findings())  # type: ignore[arg-type]

    # URL is suffixed with /v1/chat/completions
    assert captured["url"] == "https://endpoint.test/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer hf_test_token"
    assert captured["json"]["model"] == "google/medgemma-27b-text-it"
    assert captured["json"]["max_tokens"] == 128
    # System + user messages
    msgs = captured["json"]["messages"]
    assert msgs[0]["role"] == "system"
    assert "RESEARCH ONLY" in msgs[0]["content"]
    assert msgs[1]["role"] == "user"
    assert "Suspected glioma" in msgs[1]["content"]

    assert out.text is not None
    assert "looks like a small mass" in out.text
    assert RESEARCH_DISCLAIMER in out.text  # auto-appended when missing
    assert out.error is None
    assert out.backend == "hf"


@pytest.mark.asyncio
async def test_hf_backend_graceful_on_missing_url():
    narrator = MedGemmaNarrator(backend="hf", hf_endpoint_url="", hf_token="x")
    out = await narrator.narrate(study=StubStudy(), findings=_findings())  # type: ignore[arg-type]
    assert out.text is None
    assert out.error == "endpoint not configured"
    assert out.backend == "hf"


@pytest.mark.asyncio
async def test_hf_backend_graceful_on_http_error(monkeypatch):
    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    narrator = MedGemmaNarrator(
        backend="hf",
        hf_endpoint_url="https://endpoint.test/medgemma",
        hf_token="hf_test_token",
    )
    out = await narrator.narrate(study=StubStudy(), findings=_findings())  # type: ignore[arg-type]
    assert out.text is None
    assert out.error is not None
    assert "boom" in out.error


def test_build_narrator_defaults_to_mock(monkeypatch):
    # Unset/empty settings should produce a mock narrator
    from app.core import config

    monkeypatch.setattr(config.settings, "medgemma_backend", "")
    n = build_narrator()
    assert isinstance(n, MedGemmaNarrator)
    assert n.backend == "mock"


def test_build_narrator_picks_hf_when_configured(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "medgemma_backend", "hf")
    monkeypatch.setattr(
        config.settings, "medgemma_hf_endpoint_url", "https://endpoint.test/medgemma"
    )
    monkeypatch.setattr(config.settings, "medgemma_hf_token", "tok")
    n = build_narrator()
    assert n.backend == "hf"
    assert n.hf_endpoint_url == "https://endpoint.test/medgemma"
    assert n.hf_token == "tok"


def test_narrate_sync_wrapper():
    narrator = MedGemmaNarrator(backend="mock")
    out = narrator.narrate_sync(study=StubStudy(), findings=[])  # type: ignore[arg-type]
    assert isinstance(out, NarrativeResult)
    assert out.text is not None
