"""Persist a radiologist-refined segmentation as a DICOM SEG instance.

Uses `highdicom` when installed (produces a real SOP Class
1.2.840.10008.5.1.4.1.1.66.4 instance referencing the source SOPInstanceUIDs).
When highdicom isn't available, falls back to writing a NumPy mask + a
small JSON sidecar to the artifacts directory and returns
`seg_sop_instance_uid=None`. The caller stores whichever was produced.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from pydicom import Dataset

log = logging.getLogger(__name__)


@dataclass
class SegWriteResult:
    sop_instance_uid: str | None
    file_path: Path  # absolute path on the artifacts volume
    is_real_seg: bool  # True if it's an actual DICOM SEG; False if fallback


def write_segmentation(
    *,
    mask: np.ndarray,           # (H, W) or (Z, H, W), uint8 (0 = bg, >=1 = labels)
    source_datasets: list[Dataset],
    label: str,
    out_dir: Path,
    series_description: str = "Lulan refined segmentation",
) -> SegWriteResult:
    """Write a single-class segmentation produced by a radiologist edit.

    The fallback path is intentional: production deployments install
    highdicom (bundled in requirements), but if a dev environment is
    missing it we'd rather persist the mask than throw — losing the
    radiologist's work is the worst outcome.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # Always write the raw mask + JSON sidecar so the data is recoverable
    # even if the DICOM SEG write fails for any reason.
    np.save(out_dir / "mask.npy", mask.astype(np.uint8))
    sidecar = {
        "label": label,
        "shape": list(mask.shape),
        "dtype": "uint8",
        "n_source_instances": len(source_datasets),
        "referenced_sop_instance_uids": [
            str(getattr(d, "SOPInstanceUID", "")) for d in source_datasets
        ],
    }
    (out_dir / "mask.json").write_text(json.dumps(sidecar, indent=2))

    try:
        return _write_highdicom(
            mask=mask,
            source_datasets=source_datasets,
            label=label,
            out_dir=out_dir,
            series_description=series_description,
        )
    except Exception:  # noqa: BLE001
        log.exception("highdicom SEG write failed — kept mask.npy/json fallback")
        return SegWriteResult(
            sop_instance_uid=None,
            file_path=out_dir / "mask.npy",
            is_real_seg=False,
        )


def _write_highdicom(
    *,
    mask: np.ndarray,
    source_datasets: list[Dataset],
    label: str,
    out_dir: Path,
    series_description: str,
) -> SegWriteResult:
    import highdicom as hd  # type: ignore[import-not-found]
    from pydicom.sr.coding import Code

    if not source_datasets:
        raise ValueError("source_datasets required for DICOM SEG")

    # Ensure mask has a z-axis (highdicom expects (frames, rows, cols))
    if mask.ndim == 2:
        mask = mask[np.newaxis, ...]
    if mask.shape[0] != len(source_datasets):
        # When the radiologist only edits one slice, the mask has a single
        # frame; replicate empty frames so the SEG's frame count matches
        # the source series. This is a pragmatic simplification — a real
        # editor would emit a per-slice frame.
        z, h, w = len(source_datasets), mask.shape[1], mask.shape[2]
        full = np.zeros((z, h, w), dtype=np.uint8)
        full[0] = mask[0]
        mask = full

    seg_uid = hd.UID()
    segmentation = hd.seg.Segmentation(
        source_images=source_datasets,
        pixel_array=mask.astype(np.uint8),
        segmentation_type=hd.seg.SegmentationTypeValues.BINARY,
        segment_descriptions=[
            hd.seg.SegmentDescription(
                segment_number=1,
                segment_label=label,
                segmented_property_category=Code("49755003", "SCT", "Morphologically Altered Structure"),
                segmented_property_type=Code("4147007", "SCT", "Mass"),
                algorithm_type=hd.seg.SegmentAlgorithmTypeValues.MANUAL,
                algorithm_identification=None,
            )
        ],
        series_instance_uid=hd.UID(),
        series_number=1000,
        sop_instance_uid=seg_uid,
        instance_number=1,
        manufacturer="Lulan-MVP",
        manufacturer_model_name="lulan-frontend",
        software_versions="0.1",
        device_serial_number="N/A",
        content_label="LULAN_REFINED",
        content_description=series_description,
    )
    out_path = out_dir / f"seg_{uuid.uuid4().hex[:8]}.dcm"
    segmentation.save_as(str(out_path))
    return SegWriteResult(
        sop_instance_uid=str(seg_uid),
        file_path=out_path,
        is_real_seg=True,
    )
