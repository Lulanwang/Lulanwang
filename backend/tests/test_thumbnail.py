"""Tests for the thumbnail rendering helpers.

We don't reach Orthanc here; the WADO-RS path is exercised by the
docker-compose smoke check. These tests cover the pure rendering logic
that runs on whatever bytes come back.
"""
from __future__ import annotations

import io

import numpy as np
import pydicom
import pytest
from PIL import Image
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from app.services.thumbnail import THUMB_SIZE, _normalize_to_uint8, _render_png


def _make_ct(arr: np.ndarray) -> pydicom.Dataset:
    """Build a minimal CT dataset with the given pixel array."""
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = Dataset()
    ds.file_meta = meta
    ds.SOPClassUID = meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    ds.Rows, ds.Columns = arr.shape[-2:]
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    if arr.ndim == 3:
        ds.NumberOfFrames = arr.shape[0]
    ds.PixelData = arr.astype(np.uint16).tobytes()
    return ds


def test_normalize_to_uint8_handles_constant_input():
    arr = np.full((4, 4), 42, dtype=np.uint16)
    out = _normalize_to_uint8(arr)
    assert out.dtype == np.uint8
    assert out.shape == (4, 4)
    # Constant input → all zeros (no information to spread across 0-255)
    assert out.max() == 0


def test_normalize_to_uint8_spreads_range():
    arr = np.linspace(0, 1000, 100, dtype=np.uint16).reshape(10, 10)
    out = _normalize_to_uint8(arr)
    assert out.dtype == np.uint8
    assert out.min() == 0
    assert out.max() == 255


def test_render_png_emits_thumbnail_sized_image():
    arr = np.random.randint(0, 4000, size=(512, 512), dtype=np.uint16)
    ds = _make_ct(arr)
    png = _render_png(ds)
    img = Image.open(io.BytesIO(png))
    assert img.format == "PNG"
    # PIL.Image.thumbnail preserves aspect ratio; longest side ≤ THUMB_SIZE
    assert max(img.size) <= THUMB_SIZE
    assert img.mode == "L"


def test_render_png_picks_middle_frame_for_multiframe():
    # Each frame has a uniquely-positioned bright spot. The middle frame
    # places it in the top-left quadrant — the rendered thumbnail should
    # show high intensity there if middle-frame selection works.
    f_left = np.zeros((64, 64), dtype=np.uint16)
    f_mid = np.zeros((64, 64), dtype=np.uint16)
    f_right = np.zeros((64, 64), dtype=np.uint16)
    f_mid[:32, :32] = 4000  # top-left quadrant bright
    f_left[32:, :] = 4000  # whole bottom half bright (would dominate if picked)
    f_right[:, 32:] = 4000  # whole right half bright (would dominate if picked)
    arr3d = np.stack([f_left, f_mid, f_right])
    ds = _make_ct(arr3d)
    png = _render_png(ds)
    img = np.array(Image.open(io.BytesIO(png)))
    h, w = img.shape
    top_left = img[: h // 2, : w // 2].mean()
    bottom = img[h // 2 :, :].mean()
    right = img[:, w // 2 :].mean()
    # Middle frame's bright quadrant dominates the rendered thumbnail
    assert top_left > bottom
    assert top_left > right


def test_render_png_rejects_unrenderable_gracefully():
    # Photometric Interp absent + invalid data → pydicom raises on pixel_array.
    # Caller (get_or_render) catches this; here we just confirm it raises so
    # the outer try/except path is real.
    ds = Dataset()
    ds.Rows = 32
    ds.Columns = 32
    ds.BitsAllocated = 16
    with pytest.raises(Exception):
        _render_png(ds)
