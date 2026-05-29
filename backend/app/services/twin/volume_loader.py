"""Pull a full DICOM series from Orthanc via WADO-RS and assemble it
into a numpy volume with metric spacing.

Mirrors the QIDO → instances → WADO retrieve pattern in
:mod:`app.services.thumbnail`, but every instance of the chosen series
is pulled, not just the first. The series with the most instances is
treated as the primary volume — for axial CT/MR that's the stack we
want; for 2D MG it's still the only series.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import Optional

import httpx
import numpy as np
import pydicom
from pydicom import Dataset

from app.core.config import settings
from app.dicom.parse import assemble_volume, spacing_from

log = logging.getLogger(__name__)


@dataclass
class LoadedSeries:
    volume: np.ndarray                       # (Z, Y, X) float32
    spacing_zyx: tuple[float, float, float]  # mm
    datasets: list[Dataset]                  # sorted, same order as volume
    series_instance_uid: str
    is_2d: bool


def _base() -> str:
    return settings.orthanc_url.rstrip("/") + settings.orthanc_dicomweb_prefix


async def _qido(client: httpx.AsyncClient, path: str) -> list[dict] | None:
    auth = (settings.orthanc_user, settings.orthanc_password)
    r = await client.get(
        f"{_base()}/{path}",
        auth=auth,
        headers={"Accept": "application/dicom+json"},
    )
    if r.status_code != 200 or not r.content:
        return None
    return r.json()


async def _wado_instance(
    client: httpx.AsyncClient, study_uid: str, series_uid: str, instance_uid: str
) -> Optional[Dataset]:
    """Retrieve one DICOM instance.

    The bundled Ubuntu ``orthanc-dicomweb`` plugin rejects WADO-RS
    Retrieve with a plain ``application/dicom`` Accept header (it
    requires the DICOMweb-spec ``multipart/related; type="application/dicom"``
    and the multipart response then has to be unpacked). To keep things
    simple AND robust, we go through Orthanc's native REST API instead:
    look up the Orthanc instance ID by the DICOM UID, then GET
    ``/instances/{id}/file`` which returns the raw DICOM bytes.

    Same approach Round 11's seeder uses for STOW (it pushes via
    ``POST /instances`` instead of DICOMweb STOW-RS for the same
    plugin-compat reason).
    """
    auth = (settings.orthanc_user, settings.orthanc_password)
    base = settings.orthanc_url.rstrip("/")
    # Resolve the DICOM SOP Instance UID to Orthanc's internal short ID.
    r = await client.post(
        f"{base}/tools/lookup",
        auth=auth,
        content=instance_uid.encode("ascii"),
    )
    if r.status_code != 200 or not r.content:
        return None
    matches = r.json()
    instance_id = next(
        (m["ID"] for m in matches if m.get("Type") == "Instance"), None
    )
    if not instance_id:
        return None
    r = await client.get(f"{base}/instances/{instance_id}/file", auth=auth)
    if r.status_code != 200 or not r.content:
        return None
    try:
        return pydicom.dcmread(io.BytesIO(r.content), force=True)
    except Exception as exc:  # noqa: BLE001
        log.warning("dcmread failed for %s: %s", instance_uid, exc)
        return None


async def load_primary_series(study_instance_uid: str) -> LoadedSeries | None:
    """Pick the series with the most instances and download all of them.

    Returns None when Orthanc isn't reachable or the study has no
    decodable pixel data — caller treats that as a hard failure.
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        series_list = await _qido(client, f"studies/{study_instance_uid}/series")
        if not series_list:
            return None
        # Pick the series with the most instances.
        best_uid: str | None = None
        best_count = -1
        for s in series_list:
            uid = s.get("0020000E", {}).get("Value", [None])[0]
            count = int(s.get("00201209", {}).get("Value", [0])[0] or 0)
            if uid and count > best_count:
                best_uid = uid
                best_count = count
        if not best_uid:
            return None

        instances = await _qido(
            client, f"studies/{study_instance_uid}/series/{best_uid}/instances"
        )
        if not instances:
            return None

        datasets: list[Dataset] = []
        for inst in instances:
            inst_uid = inst.get("00080018", {}).get("Value", [None])[0]
            if not inst_uid:
                continue
            ds = await _wado_instance(
                client, study_instance_uid, best_uid, inst_uid
            )
            if ds is not None and hasattr(ds, "PixelData"):
                datasets.append(ds)

    if not datasets:
        return None

    volume = assemble_volume(datasets)
    spacing = spacing_from(datasets)
    if volume.size == 0:
        return None
    return LoadedSeries(
        volume=volume,
        spacing_zyx=spacing,
        datasets=sorted(
            datasets,
            key=lambda d: (
                float(np.dot(
                    np.cross(
                        np.array(d.ImageOrientationPatient[:3], dtype=float)
                        if hasattr(d, "ImageOrientationPatient")
                        else np.array([1.0, 0.0, 0.0]),
                        np.array(d.ImageOrientationPatient[3:], dtype=float)
                        if hasattr(d, "ImageOrientationPatient")
                        else np.array([0.0, 1.0, 0.0]),
                    ),
                    np.array(d.ImagePositionPatient, dtype=float)
                    if hasattr(d, "ImagePositionPatient")
                    else np.array([0.0, 0.0, 0.0]),
                )),
            ),
        ),
        series_instance_uid=best_uid,
        is_2d=volume.shape[0] <= 1,
    )
