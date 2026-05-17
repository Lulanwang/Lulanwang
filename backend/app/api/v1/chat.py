"""MedGemma chat panel for interactive Q&A on a study.

Streams tokens back to the browser via Server-Sent Events. Each chat
turn is audited. MedGemma sees the current accepted findings + study
metadata, NOT pixel data.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import AsyncIterator, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.audit import log_event
from app.core.config import settings
from app.core.security import current_user
from app.db.models.finding import Finding
from app.db.models.study import Study
from app.db.models.user import User
from app.db.session import get_db
from app.services.medgemma import (
    DEFAULT_HF_PATH,
    RESEARCH_DISCLAIMER,
    _findings_block,
    build_narrator,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/studies", tags=["chat"])


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


def _system_prompt(study: Study, accepted_findings: list[Finding]) -> str:
    return (
        "You are a radiology AI assistant answering a radiologist's questions "
        "about a single imaging study. Output for RESEARCH ONLY — NOT for "
        "diagnosis or treatment. Answer concisely. Do not invent findings "
        "not in the provided list. Do not provide treatment recommendations. "
        "If asked something outside this study's scope, say so plainly.\n\n"
        f"Study: {study.modality} {study.body_part} — "
        f"{study.description or '(no description)'}\n"
        f"Accepted AI findings:\n{_findings_block(accepted_findings)}"
    )


@router.post("/{study_id}/chat")
async def chat(
    study_id: uuid.UUID,
    payload: ChatRequest,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "study not found")
    if not payload.messages:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "messages cannot be empty")

    accepted = (
        db.query(Finding)
        .filter(
            Finding.study_id == study_id,
            Finding.is_current == True,  # noqa: E712
            Finding.status.in_(("accepted", "proposed", "modified")),
        )
        .all()
    )

    system = _system_prompt(study, accepted)
    narrator = build_narrator()
    last_user_msg = next(
        (m.content for m in reversed(payload.messages) if m.role == "user"),
        "",
    )

    log_event(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="report.chat_turn",
        resource_type="study",
        resource_id=str(study.id),
        request_id=request.headers.get("x-request-id"),
        details={
            "backend": narrator.backend,
            "model_id": narrator.model_id,
            "turn_count": len(payload.messages),
            "user_chars": len(last_user_msg),
            "accepted_findings": len(accepted),
        },
    )

    async def event_stream() -> AsyncIterator[bytes]:
        if narrator.backend == "mock":
            text = (
                "Mock chat backend: the radiologist asked about "
                f"{last_user_msg!r}. The study currently has "
                f"{len(accepted)} accepted finding(s). "
                "Configure MEDGEMMA_BACKEND=hf with a live endpoint to "
                "stream real MedGemma answers.\n\n"
                f"{RESEARCH_DISCLAIMER}"
            )
            for token in text.split(" "):
                yield _sse({"delta": token + " "})
            yield _sse({"done": True})
            return

        # hf streaming
        if not settings.medgemma_hf_endpoint_url:
            yield _sse({"error": "endpoint not configured"})
            return

        url = settings.medgemma_hf_endpoint_url.rstrip("/") + DEFAULT_HF_PATH
        headers = {
            "Authorization": f"Bearer {settings.medgemma_hf_token}"
            if settings.medgemma_hf_token
            else "",
            "Content-Type": "application/json",
        }
        body = {
            "model": settings.medgemma_model_id,
            "messages": [{"role": "system", "content": system}]
            + [m.model_dump() for m in payload.messages],
            "max_tokens": settings.medgemma_max_new_tokens,
            "temperature": 0.2,
            "stream": True,
        }
        try:
            async with httpx.AsyncClient(
                timeout=float(settings.medgemma_timeout_seconds)
            ) as client:
                async with client.stream(
                    "POST", url, headers=headers, json=body
                ) as resp:
                    if resp.status_code != 200:
                        text = (await resp.aread()).decode("utf-8", "replace")[:500]
                        yield _sse(
                            {"error": f"HTTP {resp.status_code}: {text}"}
                        )
                        return
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data = line[6:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            obj = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        delta = (
                            obj.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content")
                        )
                        if delta:
                            yield _sse({"delta": delta})
        except Exception as exc:  # noqa: BLE001
            log.warning("chat stream failed: %s", exc)
            yield _sse({"error": str(exc)[:500]})
            return
        yield _sse({"done": True})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(obj: dict) -> bytes:
    return f"data: {json.dumps(obj)}\n\n".encode("utf-8")
