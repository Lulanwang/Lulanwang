"""Study thumbnail rendering.

Pulls the first instance of the first series via WADO-RS, decodes the
pixel data with pydicom, and emits a 256-pixel PNG. Cached on disk under
`<artifact_dir>/thumbnails/<study_id>.png`.

Designed to fail soft: if Orthanc isn't reachable, returns None so the
caller can 404 and the frontend renders a placeholder.
"""
from __future__ import annotations

import io
import logging
import uuid
from pathlib import Path

import httpx
import numpy as np
import pydicom
from PIL import Image
from pydicom.errors import InvalidDicomError

from app.core.config import settings

log = logging.getLogger(__name__)

THUMB_SIZE = 256


def _cache_path(study_id: uuid.UUID) -> Path:
    cache_dir = Path(settings.artifact_dir) / "thumbnails"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{study_id}.png"


async def get_or_render(study_id: uuid.UUID, study_instance_uid: str) -> bytes | None:
    cache = _cache_path(study_id)
    if cache.exists():
        try:
            return cache.read_bytes()
        except OSError:
            pass

    try:
        ds = await _fetch_first_instance(study_instance_uid)
    except Exception as exc:  # noqa: BLE001
        log.warning("thumbnail fetch failed for %s: %s", study_instance_uid, exc)
        return None

    if ds is None:
        return None

    try:
        png = _render_png(ds)
    except Exception as exc:  # noqa: BLE001
        log.warning("thumbnail render failed for %s: %s", study_instance_uid, exc)
        return None

    try:
        cache.write_bytes(png)
    except OSError:
        pass
    return png


def _base() -> str:
    return settings.orthanc_url.rstrip("/") + settings.orthanc_dicomweb_prefix


async def _fetch_first_instance(study_uid: str) -> pydicom.Dataset | None:
    auth = (settings.orthanc_user, settings.orthanc_password)
    async with httpx.AsyncClient(timeout=15.0) as client:
        # QIDO: pick first series, then first instance
        series_resp = await client.get(
            f"{_base()}/studies/{study_uid}/series",
            auth=auth,
            headers={"Accept": "application/dicom+json"},
        )
        if series_resp.status_code != 200 or not series_resp.content:
            return None
        series_list = series_resp.json()
        if not series_list:
            return None
        series_uid = series_list[0].get("0020000E", {}).get("Value", [None])[0]
        if not series_uid:
            return None

        instances_resp = await client.get(
            f"{_base()}/studies/{study_uid}/series/{series_uid}/instances",
            auth=auth,
            headers={"Accept": "application/dicom+json"},
        )
        if instances_resp.status_code != 200 or not instances_resp.content:
            return None
        instances = instances_resp.json()
        if not instances:
            return None
        instance_uid = instances[0].get("00080018", {}).get("Value", [None])[0]
        if not instance_uid:
            return None

        wado_resp = await client.get(
            f"{_base()}/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}",
            auth=auth,
            headers={"Accept": "application/dicom"},
        )
        if wado_resp.status_code != 200 or not wado_resp.content:
            return None
        try:
            return pydicom.dcmread(io.BytesIO(wado_resp.content), force=True)
        except InvalidDicomError:
            return None


def _render_png(ds: pydicom.Dataset) -> bytes:
    arr = ds.pixel_array
    # Multi-frame: take a middle frame
    if arr.ndim == 3 and not _is_rgb(ds):
        arr = arr[arr.shape[0] // 2]
    # Normalize to 8-bit grayscale (preserves CT/MR dynamic range)
    arr = _normalize_to_uint8(arr)
    img = Image.fromarray(arr).convert("L")
    img.thumbnail((THUMB_SIZE, THUMB_SIZE))
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _is_rgb(ds: pydicom.Dataset) -> bool:
    return getattr(ds, "SamplesPerPixel", 1) > 1


def _normalize_to_uint8(arr: np.ndarray) -> np.ndarray:
    a = arr.astype(np.float32)
    lo, hi = np.percentile(a, [1, 99])
    if hi <= lo:
        return np.zeros_like(arr, dtype=np.uint8)
    a = np.clip((a - lo) / (hi - lo), 0.0, 1.0) * 255.0
    return a.astype(np.uint8)
