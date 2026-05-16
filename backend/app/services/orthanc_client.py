"""Thin DICOMweb client for Orthanc.

We talk to Orthanc over HTTP using its DICOMweb plugin
(STOW-RS for store, QIDO-RS for query, WADO-RS for retrieve).
"""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import httpx
from pydicom import Dataset, dcmwrite

from app.core.config import settings


def _auth() -> tuple[str, str]:
    return (settings.orthanc_user, settings.orthanc_password)


def _base() -> str:
    return settings.orthanc_url.rstrip("/") + settings.orthanc_dicomweb_prefix


async def stow_datasets(datasets: Iterable[Dataset]) -> dict:
    """STOW-RS multipart upload."""
    parts: list[tuple[str, tuple[str, bytes, str]]] = []
    for i, ds in enumerate(datasets):
        from io import BytesIO

        buf = BytesIO()
        dcmwrite(buf, ds, enforce_file_format=True)
        parts.append(("file", (f"instance_{i}.dcm", buf.getvalue(), "application/dicom")))

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Orthanc accepts multipart/related; httpx multipart works because
        # the DICOMweb plugin is lenient about the boundary parameters.
        resp = await client.post(
            f"{_base()}/studies",
            auth=_auth(),
            files=parts,
            headers={"Accept": "application/dicom+json"},
        )
        resp.raise_for_status()
        return resp.json() if resp.content else {}


async def qido_studies() -> list[dict]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{_base()}/studies",
            auth=_auth(),
            headers={"Accept": "application/dicom+json"},
        )
        resp.raise_for_status()
        if not resp.content:
            return []
        return resp.json()


async def wado_proxy(method: str, path: str, headers: dict, content: bytes | None) -> httpx.Response:
    """Generic proxy hook used by the DICOMweb authenticated proxy endpoint."""
    url = f"{_base()}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.request(
            method,
            url,
            auth=_auth(),
            headers=headers,
            content=content,
        )
    return resp


async def store_sr_file(sr_path: Path) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{_base()}/studies",
            auth=_auth(),
            files=[("file", (sr_path.name, sr_path.read_bytes(), "application/dicom"))],
            headers={"Accept": "application/dicom+json"},
        )
        resp.raise_for_status()
        return resp.json() if resp.content else {}
