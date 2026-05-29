"""Safe pydicom reader + series volume assembly."""
from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pydicom
from pydicom import Dataset


@dataclass
class StudyMeta:
    study_instance_uid: str
    patient_id: str
    modality: str
    body_part: str
    study_date: datetime | None
    description: str


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_dataset(path: Path) -> Dataset:
    return pydicom.dcmread(str(path), stop_before_pixels=False, force=True)


def extract_study_meta(ds: Dataset) -> StudyMeta:
    sd = str(getattr(ds, "StudyDate", "") or "")
    st = str(getattr(ds, "StudyTime", "") or "")
    study_date: datetime | None = None
    if sd:
        try:
            study_date = datetime.strptime(sd + (st[:6] if st else "000000"), "%Y%m%d%H%M%S")
        except ValueError:
            study_date = None
    # Real-world DICOMs sometimes omit StudyInstanceUID (intentionally
    # broken test fixtures, or post-anonymization tools that strip it).
    # Synthesize a stable fallback rather than crashing — callers in
    # the ingest path will reject the study upstream if they need a
    # real UID.
    study_uid = getattr(ds, "StudyInstanceUID", None)
    if not study_uid:
        sop = str(getattr(ds, "SOPInstanceUID", "") or "")
        study_uid = f"unknown.{sop[-32:] or 'no-uid'}"
    return StudyMeta(
        study_instance_uid=str(study_uid),
        patient_id=str(getattr(ds, "PatientID", "") or "anonymous"),
        modality=str(getattr(ds, "Modality", "") or "OT"),
        body_part=str(getattr(ds, "BodyPartExamined", "") or "UNKNOWN").upper(),
        study_date=study_date,
        description=str(getattr(ds, "StudyDescription", "") or ""),
    )


def _apply_modality_lut(pixel: np.ndarray, ds: Dataset) -> np.ndarray:
    slope = float(getattr(ds, "RescaleSlope", 1.0) or 1.0)
    intercept = float(getattr(ds, "RescaleIntercept", 0.0) or 0.0)
    if slope == 1.0 and intercept == 0.0:
        return pixel.astype(np.float32)
    return pixel.astype(np.float32) * slope + intercept


def _sort_key(ds: Dataset) -> float:
    """Sort slices along the cross-product of ImageOrientationPatient,
    which is the standard DICOM ordering for axial CT/MR.
    """
    ipp = getattr(ds, "ImagePositionPatient", None)
    iop = getattr(ds, "ImageOrientationPatient", None)
    if ipp and iop and len(ipp) == 3 and len(iop) == 6:
        row = np.array(iop[:3], dtype=float)
        col = np.array(iop[3:], dtype=float)
        normal = np.cross(row, col)
        return float(np.dot(np.array(ipp, dtype=float), normal))
    return float(getattr(ds, "InstanceNumber", 0) or 0)


def assemble_volume(datasets: Iterable[Dataset]) -> np.ndarray:
    """Stack a series into a (Z, Y, X) float32 volume with modality LUT applied.

    Caller is responsible for ensuring all datasets are from the same series.
    """
    sorted_ds = sorted([d for d in datasets if hasattr(d, "PixelData")], key=_sort_key)
    if not sorted_ds:
        return np.zeros((0, 0, 0), dtype=np.float32)
    slices = [_apply_modality_lut(d.pixel_array, d) for d in sorted_ds]
    return np.stack(slices, axis=0).astype(np.float32)


def spacing_from(datasets: Iterable[Dataset]) -> tuple[float, float, float]:
    """Return ``(sz, sy, sx)`` voxel spacing in millimetres for a sorted series.

    Row/column spacing comes from ``PixelSpacing`` (rows first per DICOM).
    Slice spacing is the median absolute distance between consecutive
    ``ImagePositionPatient`` values projected onto the slice normal —
    robust to gaps and irregular axial sampling. Falls back to
    ``SpacingBetweenSlices`` → ``SliceThickness`` → 1.0 when geometry is
    missing (e.g. single-slice 2D MG).

    Returned in (Z, Y, X) order to match :func:`assemble_volume`'s axis
    order, so callers can pass it straight into
    ``skimage.measure.marching_cubes(..., spacing=spacing_zyx)`` and get
    vertices in real-world millimetres.
    """
    ds_list = sorted(
        [d for d in datasets if hasattr(d, "PixelData")], key=_sort_key
    )
    if not ds_list:
        return (1.0, 1.0, 1.0)
    first = ds_list[0]
    px = getattr(first, "PixelSpacing", None)
    sy = float(px[0]) if px and len(px) >= 2 else 1.0
    sx = float(px[1]) if px and len(px) >= 2 else 1.0

    sz: float | None = None
    if len(ds_list) >= 2:
        iop = getattr(first, "ImageOrientationPatient", None)
        if iop and len(iop) == 6:
            row = np.array(iop[:3], dtype=float)
            col = np.array(iop[3:], dtype=float)
            normal = np.cross(row, col)
            positions: list[float] = []
            for d in ds_list:
                ipp = getattr(d, "ImagePositionPatient", None)
                if ipp and len(ipp) == 3:
                    positions.append(
                        float(np.dot(np.array(ipp, dtype=float), normal))
                    )
            if len(positions) >= 2:
                diffs = np.abs(np.diff(np.array(positions, dtype=float)))
                diffs = diffs[diffs > 1e-6]  # drop duplicate-position slices
                if diffs.size:
                    sz = float(np.median(diffs))
    if sz is None:
        sbs = getattr(first, "SpacingBetweenSlices", None)
        st = getattr(first, "SliceThickness", None)
        sz = float(sbs or st or 1.0)
    return (sz, sy, sx)
