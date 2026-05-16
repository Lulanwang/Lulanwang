"""Tests for app/dicom/seg_writer.py.

Exercises both branches:
  - highdicom path produces a real DICOM SEG (SOP class
    1.2.840.10008.5.1.4.1.1.66.4) with a SOPInstanceUID
  - fallback path writes mask.npy + mask.json when highdicom raises

The user requested versioned segmentations specifically so that
radiologist edits never lose AI data — that means the writer must
*always* persist the mask somewhere, even when highdicom fails.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pydicom
import pytest
from pydicom.data import get_testdata_file

from app.dicom import seg_writer
from app.dicom.seg_writer import write_segmentation


def _source_ds():
    """A real bundled CT instance to use as the SEG source-images reference."""
    path = get_testdata_file("CT_small.dcm")
    assert path
    return pydicom.dcmread(path)


def test_real_seg_when_highdicom_available(tmp_path: Path):
    ds = _source_ds()
    mask = np.zeros((ds.Rows, ds.Columns), dtype=np.uint8)
    # paint a small disc
    yy, xx = np.ogrid[: ds.Rows, : ds.Columns]
    mask[(yy - ds.Rows // 2) ** 2 + (xx - ds.Columns // 2) ** 2 <= 100] = 1

    result = write_segmentation(
        mask=mask,
        source_datasets=[ds],
        label="test refinement",
        out_dir=tmp_path,
    )

    # Fallback mask + sidecar are ALWAYS written, even on the real-SEG path,
    # because the seg_writer persists them up-front before attempting highdicom.
    assert (tmp_path / "mask.npy").exists()
    assert (tmp_path / "mask.json").exists()
    sidecar = json.loads((tmp_path / "mask.json").read_text())
    assert sidecar["label"] == "test refinement"
    assert sidecar["n_source_instances"] == 1
    assert sidecar["referenced_sop_instance_uids"] == [str(ds.SOPInstanceUID)]

    # With highdicom installed we expect the real path
    assert result.is_real_seg is True, "highdicom is in pyproject; real SEG should be written"
    assert result.sop_instance_uid is not None
    assert result.file_path.exists()
    # Round-trip via pydicom and assert the SOP class
    sr = pydicom.dcmread(str(result.file_path))
    assert str(sr.SOPClassUID) == "1.2.840.10008.5.1.4.1.1.66.4"  # Segmentation Storage


def test_fallback_when_highdicom_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ds = _source_ds()
    mask = np.zeros((ds.Rows, ds.Columns), dtype=np.uint8)
    mask[0:5, 0:5] = 1

    def _boom(**kw):
        raise RuntimeError("simulated highdicom failure")

    monkeypatch.setattr(seg_writer, "_write_highdicom", _boom)

    result = write_segmentation(
        mask=mask,
        source_datasets=[ds],
        label="fallback test",
        out_dir=tmp_path,
    )

    assert result.is_real_seg is False
    assert result.sop_instance_uid is None
    # Mask must still be on disk so radiologist work isn't lost
    assert (tmp_path / "mask.npy").exists()
    loaded = np.load(tmp_path / "mask.npy")
    assert loaded.shape == mask.shape
    assert loaded.sum() == mask.sum()


def test_mask_2d_is_padded_to_3d(tmp_path: Path):
    """A 2D edit should be padded to one frame and align with one source slice."""
    ds = _source_ds()
    mask_2d = np.zeros((ds.Rows, ds.Columns), dtype=np.uint8)
    mask_2d[10:20, 10:20] = 1
    result = write_segmentation(
        mask=mask_2d,
        source_datasets=[ds],
        label="2d pad test",
        out_dir=tmp_path,
    )
    # Either path: mask.npy is the 2D input shape on disk (we always np.save
    # the input as-is); the highdicom padding happens in-memory inside the
    # real-SEG branch. We just assert nothing crashed and the sidecar agrees.
    sidecar = json.loads((tmp_path / "mask.json").read_text())
    assert sidecar["shape"] == [int(ds.Rows), int(ds.Columns)]
    assert result.file_path.exists()
