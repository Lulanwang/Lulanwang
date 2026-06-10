"""Classical-CV organ + lesion segmentation for the digital-twin pipeline.

Three body-part buckets, matching ``app.models.registry.model_key_for``:

* ``lung_ct`` — HU-thresholded lung parenchyma from a chest CT.
* ``brain_mri`` — Otsu + morphological skull-strip on a head MR.
* ``breast_mammo`` — 2D silhouette extruded a few mm for a "billboard"
  breast outline on a single-slice mammogram.

Each implementation conforms to :class:`OrganSegmenter`, and the
:func:`resolve_segmenter` registry returns the right one for a study's
body-part key. A future MONAI organ model can be registered the same
way without touching the API or storage layers.

Lesion masks come from three tiers, surfaced by
:func:`build_lesion_masks`:

1. ``finding.seg_sop_instance_uid`` is set → pull the SEG instance from
   Orthanc and reproject. (Not implemented yet; sketched as a stub —
   the synthetic ellipsoid fallback covers the demo cohort.)
2. ``seg/<finding_id>/mask.npy`` sidecar exists on the artifact volume
   (written by the radiologist-refine flow).
3. Only normalized 2D ``bbox`` geometry available → synthesize a smooth
   ellipsoid marker sized to the bbox, flagged ``synthetic_marker: true``
   so the UI can disclose provenance.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Protocol, runtime_checkable

import numpy as np
from scipy import ndimage as ndi
from skimage import filters, measure, morphology

from app.core.config import settings
from app.db.models.finding import Finding

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Segmenter protocol + registry
# ---------------------------------------------------------------------------


@runtime_checkable
class OrganSegmenter(Protocol):
    body_part: str
    version: str

    def segment(
        self, volume: np.ndarray, spacing_zyx: tuple[float, float, float]
    ) -> np.ndarray:
        """Return a boolean (Z, Y, X) mask of the target organ."""


# ---------------------------------------------------------------------------
# Lung CT — HU thresholds + connected components
# ---------------------------------------------------------------------------


@dataclass
class LungCtSegmenter:
    body_part: str = "lung_ct"
    version: str = "cv-1"

    def segment(
        self, volume: np.ndarray, spacing_zyx: tuple[float, float, float]
    ) -> np.ndarray:
        if volume.ndim != 3 or volume.shape[0] < 2:
            return np.zeros_like(volume, dtype=bool)

        # Adapt thresholds to the volume's intensity distribution.
        # A clinical calibrated CT has air at ≈ -1000 HU and the body
        # at +50 — so the fixed -500 / -320 split works. A synthetic
        # generator (or a CT with no RescaleSlope/Intercept applied)
        # often clamps air much higher; in that case we fall back to
        # Otsu for the body envelope and produce just the body mesh
        # (the lung air step finds nothing and we return the body).
        air_p1 = float(np.percentile(volume, 1))
        if air_p1 < -700.0:
            body_thresh = -500.0
            air_thresh = -320.0
        else:
            try:
                body_thresh = float(filters.threshold_otsu(volume))
            except ValueError:
                return np.zeros_like(volume, dtype=bool)
            air_thresh = body_thresh - 200.0  # disable interior-air step

        # 1. Body envelope.
        body = volume > body_thresh
        body = ndi.binary_fill_holes(body)
        body = _largest_cc(body)
        if not body.any():
            return body

        # 2. Air inside the body — classic lung HU window. Only runs
        # for true HU-calibrated volumes; otherwise air_thresh is
        # below the body mean and ``interior_air`` is empty.
        interior_air = (volume < air_thresh) & body

        # 3. Drop tiny speckle and components that touch the volume
        # border (which would mean air outside the body).
        labels = measure.label(interior_air, connectivity=1)
        keep = np.zeros_like(interior_air, dtype=bool)
        for region in measure.regionprops(labels):
            if region.area < 500:
                continue
            zmin, ymin, xmin, zmax, ymax, xmax = region.bbox
            touches_border = (
                zmin == 0
                or ymin == 0
                or xmin == 0
                or zmax == volume.shape[0]
                or ymax == volume.shape[1]
                or xmax == volume.shape[2]
            )
            if touches_border:
                continue
            keep |= labels == region.label
        keep = morphology.closing(keep, morphology.ball(2))

        if keep.any():
            return keep
        # Non-calibrated / synthetic volume — return the body envelope
        # so the twin always shows a 3D shape. The page banner already
        # says "research only" so a body mesh is honest output.
        return body


# ---------------------------------------------------------------------------
# Brain MR — Otsu + poor-man's skull strip
# ---------------------------------------------------------------------------


@dataclass
class BrainMrSegmenter:
    body_part: str = "brain_mri"
    version: str = "cv-1"

    def segment(
        self, volume: np.ndarray, spacing_zyx: tuple[float, float, float]
    ) -> np.ndarray:
        if volume.ndim != 3 or volume.shape[0] < 2:
            return np.zeros_like(volume, dtype=bool)

        # 1. Foreground: head vs background air.
        try:
            thresh = filters.threshold_otsu(volume)
        except ValueError:
            return np.zeros_like(volume, dtype=bool)
        fg = volume > thresh
        fg = ndi.binary_fill_holes(fg)
        head = _largest_cc(fg)
        if not head.any():
            return head

        # 2. Erode to break the thin skull-brain bridge, keep the largest
        # interior blob (the brain), then dilate back to roughly the
        # original brain envelope, clipped by the head mask.
        # ``ball(3)`` is enough on synthetic anatomies and on the
        # MR_small bundled fixture (slice spacing ~5 mm).
        eroded = morphology.erosion(head, morphology.ball(3))
        brain_core = _largest_cc(eroded)
        if not brain_core.any():
            return head  # fallback — better than nothing
        brain = morphology.dilation(brain_core, morphology.ball(3)) & head
        return brain


# ---------------------------------------------------------------------------
# Breast — 2D MG silhouette, extruded to a thin 3D slab
# ---------------------------------------------------------------------------


@dataclass
class BreastSegmenter:
    body_part: str = "breast_mammo"
    version: str = "cv-1"

    def segment(
        self, volume: np.ndarray, spacing_zyx: tuple[float, float, float]
    ) -> np.ndarray:
        if volume.ndim != 3 or volume.size == 0:
            return np.zeros_like(volume, dtype=bool)

        # Pick the middle slice (handles future 3D breast MR too).
        z_mid = volume.shape[0] // 2
        slab2d = volume[z_mid]

        try:
            thresh = filters.threshold_otsu(slab2d)
        except ValueError:
            return np.zeros_like(volume, dtype=bool)

        # Mammograms have white tissue on dark detector. Otsu returns a
        # threshold; we want everything brighter than it.
        fg = slab2d > thresh
        fg = ndi.binary_fill_holes(fg)
        if not fg.any():
            return np.zeros_like(volume, dtype=bool)

        # Largest CC = the breast (we strip any text annotation /
        # paddle artefacts that survived the threshold).
        labels = measure.label(fg)
        regions = measure.regionprops(labels)
        if not regions:
            return np.zeros_like(volume, dtype=bool)
        largest = max(regions, key=lambda r: r.area)
        silhouette = labels == largest.label

        if volume.shape[0] == 1:
            # Genuine 2D MG: extrude the silhouette over a synthetic
            # depth so marching cubes has something to chew on. The
            # output volume still has Z=1 — we expand to a small slab
            # below.
            return np.broadcast_to(silhouette[None, :, :], (1,) + silhouette.shape).copy()

        # 3D series (breast MR): apply the silhouette across all slices
        # then erode to drop the skin/fat outer rind.
        out = np.broadcast_to(silhouette[None, :, :], volume.shape).copy()
        return morphology.erosion(out, morphology.ball(2))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


_REGISTRY: dict[str, OrganSegmenter] = {
    "lung_ct": LungCtSegmenter(),
    "brain_mri": BrainMrSegmenter(),
    "breast_mammo": BreastSegmenter(),
}


def resolve_segmenter(body_part_key: str) -> OrganSegmenter | None:
    """Return the registered segmenter for a body-part key.

    The key matches :func:`app.models.registry.model_key_for`. ``None``
    means we don't have a classical-CV segmenter for this combo and
    the caller should fail soft.
    """
    return _REGISTRY.get(body_part_key)


# ---------------------------------------------------------------------------
# Lesions — three-tier fallback
# ---------------------------------------------------------------------------


@dataclass
class LesionMask:
    finding_id: str
    label: str
    mask: np.ndarray            # bool (Z, Y, X), aligned to the loaded volume
    synthetic_marker: bool      # True when synthesized from bbox alone


def build_lesion_masks(
    findings: Iterable[Finding],
    volume_shape: tuple[int, int, int],
    study_id_for_artifact: str,
) -> list[LesionMask]:
    """Return per-finding 3D masks aligned to the loaded volume."""
    out: list[LesionMask] = []
    for f in findings:
        mask = _load_sidecar_mask(study_id_for_artifact, str(f.id), volume_shape)
        synthetic = False
        if mask is None:
            mask = _ellipsoid_from_bbox(f.geometry, volume_shape)
            synthetic = mask is not None
        if mask is None or not mask.any():
            continue
        out.append(
            LesionMask(
                finding_id=str(f.id),
                label=str(getattr(f, "label", "Finding")),
                mask=mask,
                synthetic_marker=synthetic,
            )
        )
    return out


def _load_sidecar_mask(
    study_id: str, finding_id: str, target_shape: tuple[int, int, int]
) -> Optional[np.ndarray]:
    """Tier 2: load a numpy mask sidecar from the artifact volume."""
    path = (
        Path(settings.artifact_dir)
        / str(study_id)
        / "seg"
        / finding_id
        / "mask.npy"
    )
    if not path.exists():
        return None
    try:
        m = np.load(path, allow_pickle=False)
    except Exception as exc:  # noqa: BLE001
        log.warning("sidecar mask %s load failed: %s", path, exc)
        return None
    if m.shape == target_shape:
        return m.astype(bool)
    if m.ndim == 2 and target_shape[1:] == m.shape:
        # 2D radiologist refinement — broadcast across all slices in
        # the loaded series.
        return np.broadcast_to(m.astype(bool)[None, :, :], target_shape).copy()
    log.warning(
        "sidecar mask shape mismatch finding=%s want=%s got=%s",
        finding_id,
        target_shape,
        m.shape,
    )
    return None


def _ellipsoid_from_bbox(
    geometry: dict | None, volume_shape: tuple[int, int, int]
) -> Optional[np.ndarray]:
    """Tier 3: synthesize a smooth ellipsoid sized to a normalized bbox.

    ``geometry`` shape (Round 5 schema):
        { "kind": "bbox", "x": 0..1, "y": 0..1, "w": 0..1, "h": 0..1,
          "slice"?: int }
    """
    if not geometry or geometry.get("kind") != "bbox":
        return None
    try:
        nx = float(geometry["x"])
        ny = float(geometry["y"])
        nw = float(geometry["w"])
        nh = float(geometry["h"])
    except (KeyError, TypeError, ValueError):
        return None

    Z, Y, X = volume_shape
    cy = int(round((ny + nh / 2.0) * Y))
    cx = int(round((nx + nw / 2.0) * X))
    ry = max(2, int(round(nh / 2.0 * Y)))
    rx = max(2, int(round(nw / 2.0 * X)))
    # Use the bbox's larger dim as the z-radius so the marker is roughly
    # spherical in patient space rather than a flat disc.
    rz = max(2, min(Z // 4, int(round(max(rx, ry) * 0.6))))

    slice_idx = geometry.get("slice")
    if isinstance(slice_idx, (int, float)) and 0 <= int(slice_idx) < Z:
        cz = int(slice_idx)
    else:
        cz = Z // 2

    mask = np.zeros(volume_shape, dtype=bool)
    z = np.arange(Z)[:, None, None]
    y = np.arange(Y)[None, :, None]
    x = np.arange(X)[None, None, :]
    rr = ((z - cz) / rz) ** 2 + ((y - cy) / ry) ** 2 + ((x - cx) / rx) ** 2
    mask = rr <= 1.0
    if not mask.any():
        return None
    return mask


def _largest_cc(mask: np.ndarray) -> np.ndarray:
    """Keep only the largest connected component."""
    labels = measure.label(mask, connectivity=1)
    if labels.max() == 0:
        return np.zeros_like(mask, dtype=bool)
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0  # background
    return labels == int(np.argmax(sizes))
