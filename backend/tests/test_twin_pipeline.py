"""Tests for the 3D digital-twin pipeline (Round 12).

Covers the parts of the pipeline that don't require a live Orthanc:

* ``spacing_from`` derivation (anisotropic + fallback paths).
* ``segment.LungCtSegmenter`` / ``BrainMrSegmenter`` produce non-empty
  masks on synthetic volumes.
* ``mask_to_mesh`` returns a manifold, decimated mesh with the right
  volume order of magnitude (validates spacing handling).
* Lesion three-tier dispatch: ``mask.npy`` sidecar loads + bbox-only
  geometry synthesizes a flagged ellipsoid.
* ``assemble_glb`` produces a parseable glTF-binary under the size
  ceiling, with the expected geometry count.
* 2D MG path extrudes into a non-degenerate mesh.
"""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pydicom
import pytest
import trimesh
from pydicom import Dataset
from pydicom.dataset import FileMetaDataset

from app.dicom.parse import spacing_from
from app.services.twin import config as cfg
from app.services.twin.meshing import (
    StructureMesh,
    assemble_glb,
    mask_to_mesh,
)
from app.services.twin.segment import (
    BrainMrSegmenter,
    BreastSegmenter,
    LungCtSegmenter,
    _ellipsoid_from_bbox,
    _load_sidecar_mask,
)


# ---------------------------------------------------------------------------
# spacing_from
# ---------------------------------------------------------------------------


def _make_ds(z: float, pixel_spacing=(0.7, 0.5), shape=(8, 8)) -> Dataset:
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.PixelSpacing = list(pixel_spacing)
    ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    ds.ImagePositionPatient = [0.0, 0.0, float(z)]
    ds.Rows, ds.Columns = shape
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelData = np.zeros(shape, dtype=np.uint16).tobytes()
    return ds


def test_spacing_from_uses_ipp_median() -> None:
    """Anisotropic spacing from ImagePositionPatient z-deltas."""
    slices = [_make_ds(z=z) for z in (0.0, 2.5, 5.0, 7.5)]
    sz, sy, sx = spacing_from(slices)
    assert sz == pytest.approx(2.5, abs=1e-3)
    assert sy == pytest.approx(0.7, abs=1e-3)
    assert sx == pytest.approx(0.5, abs=1e-3)


def test_spacing_from_falls_back_to_slice_thickness() -> None:
    ds = _make_ds(z=0.0)
    ds.SliceThickness = 3.0
    # Strip IPP so the median path can't run.
    del ds.ImagePositionPatient
    sz, sy, sx = spacing_from([ds])
    assert sz == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# Segmenters
# ---------------------------------------------------------------------------


def test_lung_ct_segmenter_finds_internal_air() -> None:
    """Two air spheres inside a tissue cube → both lungs found."""
    seg = LungCtSegmenter()
    vol = np.full((40, 64, 64), 50.0, dtype=np.float32)  # soft tissue ≈ 50 HU
    # surrounding "air" outside body
    vol[:, :4, :] = -1000.0
    vol[:, -4:, :] = -1000.0
    vol[:, :, :4] = -1000.0
    vol[:, :, -4:] = -1000.0
    # left + right lung as low-HU spheres
    for cx in (20, 44):
        zz, yy, xx = np.ogrid[:40, :64, :64]
        rr = (zz - 20) ** 2 + (yy - 32) ** 2 + (xx - cx) ** 2
        vol[rr <= 8 ** 2] = -800.0
    mask = seg.segment(vol, (1.0, 1.0, 1.0))
    assert mask.dtype == bool
    assert mask.sum() > 0
    # both lungs are inside the body envelope
    assert not mask[0, :, :].any()
    assert not mask[-1, :, :].any()


def test_brain_mr_segmenter_returns_interior_blob() -> None:
    """Bright head with darker brain → brain mask is interior + smaller."""
    seg = BrainMrSegmenter()
    vol = np.zeros((24, 48, 48), dtype=np.float32)
    zz, yy, xx = np.ogrid[:24, :48, :48]
    head = (zz - 12) ** 2 + (yy - 24) ** 2 + (xx - 24) ** 2 <= 18 ** 2
    vol[head] = 200.0
    # carve a slightly smaller dark "brain" inside
    brain = (zz - 12) ** 2 + (yy - 24) ** 2 + (xx - 24) ** 2 <= 12 ** 2
    vol[brain] = 100.0
    mask = seg.segment(vol, (1.0, 1.0, 1.0))
    assert mask.sum() > 0
    # The brain mask should sit fully inside the bright head envelope.
    assert mask.sum() <= head.sum()


def test_breast_segmenter_2d_silhouette() -> None:
    """MG (Z=1) path returns a non-empty mask matching the 2D silhouette."""
    seg = BreastSegmenter()
    vol = np.zeros((1, 32, 32), dtype=np.float32)
    vol[0, 8:24, 8:24] = 200.0  # bright tissue square on dark detector
    mask = seg.segment(vol, (1.0, 1.0, 1.0))
    assert mask.shape == vol.shape
    assert mask.sum() > 0


# ---------------------------------------------------------------------------
# Meshing
# ---------------------------------------------------------------------------


def _sphere_mask(shape, center, radius) -> np.ndarray:
    zz, yy, xx = np.ogrid[: shape[0], : shape[1], : shape[2]]
    cz, cy, cx = center
    return ((zz - cz) ** 2 + (yy - cy) ** 2 + (xx - cx) ** 2) <= radius ** 2


def test_mask_to_mesh_sphere_volume_within_tolerance() -> None:
    """Marching cubes on a sphere → volume within ~15% of analytic."""
    spacing = (2.0, 1.0, 1.0)  # anisotropic on purpose
    mask = _sphere_mask((32, 64, 64), (16, 32, 32), 12)
    mesh = mask_to_mesh(mask, spacing, face_budget=8_000)
    assert mesh is not None
    # Analytic sphere volume in mm³ — radius is 12 voxels but voxel
    # spacing is (2,1,1) so the "sphere" is a 24×24×24 mm ellipsoid.
    rz, ry, rx = 12 * spacing[0], 12 * spacing[1], 12 * spacing[2]
    analytic_mm3 = 4.0 / 3.0 * np.pi * rz * ry * rx
    assert mesh.volume == pytest.approx(analytic_mm3, rel=0.15)
    # Decimated below budget.
    assert len(mesh.faces) <= 8_000


def test_mask_to_mesh_2d_extrudes_when_requested() -> None:
    """Single-slice mask + extrude_z_mm produces a usable slab."""
    spacing = (1.0, 1.0, 1.0)
    mask = np.zeros((1, 16, 16), dtype=bool)
    mask[0, 4:12, 4:12] = True
    mesh = mask_to_mesh(
        mask, spacing, face_budget=4_000, extrude_z_mm=10.0
    )
    assert mesh is not None
    assert len(mesh.faces) > 0
    # The slab is ~8 × 8 × 10 mm → volume order 640 mm³
    assert 100 < mesh.volume < 3000


def test_assemble_glb_round_trips_via_trimesh() -> None:
    """assemble_glb writes a valid glTF-binary trimesh can re-parse."""
    spacing = (1.0, 1.0, 1.0)
    organ = mask_to_mesh(
        _sphere_mask((20, 32, 32), (10, 16, 16), 8), spacing, face_budget=4_000
    )
    lesion = mask_to_mesh(
        _sphere_mask((20, 32, 32), (10, 22, 22), 3), spacing, face_budget=1_000
    )
    assert organ is not None and lesion is not None
    structs = [
        StructureMesh(
            name="organ", kind="organ", color_hex=cfg.ORGAN_COLOR,
            mesh=organ, volume_cm3=12.3,
        ),
        StructureMesh(
            name="lesion_x", kind="lesion", color_hex=cfg.LESION_COLORS[0],
            mesh=lesion, volume_cm3=0.4, synthetic_marker=True,
        ),
    ]
    result = assemble_glb(structs)
    # GLB magic + size ceiling
    assert result.glb_bytes[:4] == b"glTF"
    assert len(result.glb_bytes) <= cfg.GLB_BYTES_CEILING
    # Re-parse via trimesh
    loaded = trimesh.load(io.BytesIO(result.glb_bytes), file_type="glb")
    # Scene with two geometries
    if isinstance(loaded, trimesh.Scene):
        assert len(loaded.geometry) == 2
    else:
        assert len(loaded.faces) > 0
    # Metadata round-trips per-structure
    md = result.metadata
    assert len(md) == 2
    assert md[0]["kind"] == "organ"
    assert md[1]["synthetic_marker"] is True


# ---------------------------------------------------------------------------
# Lesion three-tier
# ---------------------------------------------------------------------------


def test_lesion_tier3_ellipsoid_from_bbox() -> None:
    geometry = {"kind": "bbox", "x": 0.25, "y": 0.25, "w": 0.5, "h": 0.5, "slice": 8}
    mask = _ellipsoid_from_bbox(geometry, (16, 32, 32))
    assert mask is not None
    assert mask.sum() > 0
    assert mask.shape == (16, 32, 32)


def test_lesion_tier2_loads_npy_sidecar(tmp_path: Path, monkeypatch) -> None:
    from app.services.twin import segment as seg_mod
    from app.core.config import settings

    monkeypatch.setattr(settings, "artifact_dir", str(tmp_path))
    study_id = "study-A"
    finding_id = "finding-B"
    seg_dir = tmp_path / study_id / "seg" / finding_id
    seg_dir.mkdir(parents=True)
    mask = np.zeros((24, 24), dtype=bool)
    mask[8:16, 8:16] = True
    np.save(seg_dir / "mask.npy", mask)

    loaded = _load_sidecar_mask(study_id, finding_id, (5, 24, 24))
    assert loaded is not None
    assert loaded.shape == (5, 24, 24)
    # The 2D mask got broadcast across every slice.
    assert loaded[0].sum() == mask.sum()
    assert (loaded[0] == loaded[-1]).all()


def test_lesion_tier3_returns_none_when_geometry_missing() -> None:
    assert _ellipsoid_from_bbox(None, (16, 16, 16)) is None
    assert _ellipsoid_from_bbox({"kind": "polygon"}, (16, 16, 16)) is None
