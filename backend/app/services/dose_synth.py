"""Synthetic dose distribution — RESEARCH USE ONLY.

This is NOT a Monte Carlo dose engine. It is a deliberately simplified
illustration that lets the UI render isodose-like overlays and feed
per-OAR mean / max / V20-style numbers into the constraint evaluator.

Model:
  For each beam, dose deposition is a Gaussian falloff in 3D from the
  isocenter along the beam axis, attenuated linearly with depth (no
  Bragg peak modeling). Multiple beams superpose linearly. Prescription
  dose is the target's mean dose; beam weights are normalized so that
  superposition at isocenter equals prescription.

Limitations (must be disclaimed in MODEL_CARDS.md):
  - No heterogeneity correction (lungs treated as water)
  - No biological-effective-dose / fractionation effects
  - No proton-specific Bragg peak — proton flag selected only narrows
    the lateral Gaussian sigma slightly (cosmetic)
  - No collimator / MLC modeling
  - Dose grid is anisotropic to make computation tractable (32×32×Z by
    default, ~10× coarser than a real TPS)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

import numpy as np


@dataclass
class Beam:
    gantry_angle_deg: float  # 0=AP, 90=left, 180=PA, 270=right
    couch_angle_deg: float = 0.0
    collimator_angle_deg: float = 0.0
    energy_mev: float = 6.0
    weight: float = 1.0


@dataclass
class Isocenter:
    x: float
    y: float
    z: float


@dataclass
class GridSpec:
    nx: int = 32
    ny: int = 32
    nz: int = 32
    spacing_cm: float = 0.5  # 0.5 cm voxel → ~16 cm cube field of view


PROTON_SIGMA_CM = 1.5
PHOTON_SIGMA_CM = 2.5
DEPTH_ATTEN_PER_CM = 0.03  # 3% linear falloff per cm of depth


def compute_dose_grid(
    *,
    beams: list[Beam],
    isocenter: Isocenter,
    grid: GridSpec,
    modality: str = "photon",
    prescription_dose_gy: float = 60.0,
) -> np.ndarray:
    """Return a 3D float array of dose-in-Gy, shape (nz, ny, nx).

    Coordinates are voxel indices; isocenter is in voxel space.
    """
    if not beams:
        return np.zeros((grid.nz, grid.ny, grid.nx), dtype=np.float32)

    sigma = PROTON_SIGMA_CM if modality == "proton" else PHOTON_SIGMA_CM
    sigma_vox = sigma / grid.spacing_cm

    # Voxel index grids
    zz, yy, xx = np.indices((grid.nz, grid.ny, grid.nx), dtype=np.float32)
    iso_x, iso_y, iso_z = isocenter.x, isocenter.y, isocenter.z

    total = np.zeros_like(xx, dtype=np.float32)
    weight_sum = 0.0
    for b in beams:
        w = max(b.weight, 0.0)
        weight_sum += w
        if w == 0.0:
            continue
        # Beam direction unit vector (axial plane only; couch rotation
        # ignored for the synthetic model). Gantry 0° = +y (anterior),
        # 90° = +x (left), 180° = -y (posterior), 270° = -x (right).
        ang = math.radians(b.gantry_angle_deg)
        dir_x = math.sin(ang)
        dir_y = -math.cos(ang)
        dir_z = 0.0  # ignore couch tilt

        # Vector from isocenter to each voxel
        vx = xx - iso_x
        vy = yy - iso_y
        vz = zz - iso_z

        # Distance along beam axis (signed: + = entry side)
        depth = vx * dir_x + vy * dir_y + vz * dir_z

        # Perpendicular distance from beam axis
        proj_x = depth * dir_x
        proj_y = depth * dir_y
        proj_z = depth * dir_z
        perp_x = vx - proj_x
        perp_y = vy - proj_y
        perp_z = vz - proj_z
        perp_sq = perp_x**2 + perp_y**2 + perp_z**2
        perp_cm_sq = perp_sq * (grid.spacing_cm**2)

        # Lateral Gaussian + linear depth attenuation. Treat dose as zero
        # behind the patient by clamping depth-attenuation.
        lateral = np.exp(-perp_cm_sq / (2.0 * sigma**2))
        depth_cm = np.clip(depth * grid.spacing_cm, -50.0, 50.0)
        atten = np.clip(1.0 - DEPTH_ATTEN_PER_CM * np.abs(depth_cm), 0.0, 1.0)

        total += w * lateral * atten

    if weight_sum == 0:
        return total
    # Normalize so that the isocenter (depth=0, perp=0) sums to weight_sum,
    # then scale to prescription dose at isocenter.
    iso_val = float(weight_sum)
    if iso_val > 0:
        total = total * (prescription_dose_gy / iso_val)

    return total.astype(np.float32)


@dataclass
class DoseSummary:
    mean: float
    max: float
    v20: float  # fraction of voxels receiving ≥20 Gy
    v30: float


def summarize_voxels(values: np.ndarray) -> DoseSummary:
    """Compact stats over a 1D array of dose-in-Gy values."""
    if values.size == 0:
        return DoseSummary(mean=0.0, max=0.0, v20=0.0, v30=0.0)
    return DoseSummary(
        mean=float(values.mean()),
        max=float(values.max()),
        v20=float((values >= 20.0).sum()) / values.size,
        v30=float((values >= 30.0).sum()) / values.size,
    )


def summarize_oars(
    dose_grid: np.ndarray,
    oar_masks: dict[str, np.ndarray],
) -> dict[str, dict]:
    """For each OAR mask, return its dose summary as a plain dict.

    Masks must have the same shape as dose_grid. Anything else is
    skipped with a 0-valued summary.
    """
    out: dict[str, dict] = {}
    for tissue, mask in oar_masks.items():
        if mask.shape != dose_grid.shape:
            s = DoseSummary(0.0, 0.0, 0.0, 0.0)
        else:
            s = summarize_voxels(dose_grid[mask.astype(bool)])
        out[tissue] = {
            "mean": round(s.mean, 2),
            "max": round(s.max, 2),
            "v20": round(s.v20, 3),
            "v30": round(s.v30, 3),
        }
    return out


def compute(
    *,
    beams: Iterable[dict],
    isocenter: tuple[float, float, float] | None = None,
    grid: GridSpec | None = None,
    modality: str = "photon",
    prescription_dose_gy: float = 60.0,
    oar_masks: dict[str, np.ndarray] | None = None,
) -> dict:
    """High-level entry point used by the API.

    Accepts beam dicts as persisted in the DB (gantry_angle, energy_mev,
    weight, etc.) and returns a dict that gets stored in
    treatment_plans.dose_summary."""
    grid = grid or GridSpec()
    iso = Isocenter(
        x=(isocenter or (grid.nx / 2, grid.ny / 2, grid.nz / 2))[0],
        y=(isocenter or (grid.nx / 2, grid.ny / 2, grid.nz / 2))[1],
        z=(isocenter or (grid.nx / 2, grid.ny / 2, grid.nz / 2))[2],
    )
    beam_objs = [
        Beam(
            gantry_angle_deg=float(b.get("gantry_angle", 0)),
            couch_angle_deg=float(b.get("couch_angle", 0)),
            collimator_angle_deg=float(b.get("collimator_angle", 0)),
            energy_mev=float(b.get("energy_mev", 6.0)),
            weight=float(b.get("weight", 1.0)),
        )
        for b in beams
    ]
    grid_arr = compute_dose_grid(
        beams=beam_objs,
        isocenter=iso,
        grid=grid,
        modality=modality,
        prescription_dose_gy=prescription_dose_gy,
    )

    oar_summary = summarize_oars(grid_arr, oar_masks or {})

    # Whole-grid summary for the "global" row
    global_summary = summarize_voxels(grid_arr.ravel())

    return {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "modality": modality,
        "prescription_dose_gy": prescription_dose_gy,
        "isocenter": [iso.x, iso.y, iso.z],
        "grid_shape": [grid.nz, grid.ny, grid.nx],
        "spacing_cm": grid.spacing_cm,
        "global": {
            "mean": round(global_summary.mean, 2),
            "max": round(global_summary.max, 2),
            "v20": round(global_summary.v20, 3),
            "v30": round(global_summary.v30, 3),
        },
        "oars": oar_summary,
        "disclaimer": (
            "RESEARCH USE ONLY. Synthetic Gaussian-superposition model — "
            "not Monte Carlo. Do not use for clinical decision-making."
        ),
    }
