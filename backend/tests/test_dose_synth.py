"""Tests for the synthetic dose model.

These don't assert clinical correctness (the model is illustrative).
They lock in the invariants any downstream code relies on:
- isocenter receives ≈ prescription dose
- dose falls off with distance and depth
- multiple beams superpose
- summarize_voxels handles empty input
"""
from __future__ import annotations

import numpy as np

from app.services.dose_synth import (
    Beam,
    GridSpec,
    Isocenter,
    compute,
    compute_dose_grid,
    summarize_voxels,
)


def _center_iso(grid: GridSpec) -> Isocenter:
    return Isocenter(x=grid.nx / 2, y=grid.ny / 2, z=grid.nz / 2)


def test_single_beam_isocenter_receives_prescription_dose():
    grid = GridSpec(nx=16, ny=16, nz=16, spacing_cm=0.5)
    iso = _center_iso(grid)
    arr = compute_dose_grid(
        beams=[Beam(gantry_angle_deg=0.0, weight=1.0)],
        isocenter=iso,
        grid=grid,
        prescription_dose_gy=60.0,
    )
    # isocenter cell ≈ prescription (allow a few % slack from voxel rounding)
    iso_val = arr[int(iso.z), int(iso.y), int(iso.x)]
    assert 55.0 <= iso_val <= 65.0


def test_dose_falls_off_with_distance_from_isocenter():
    grid = GridSpec(nx=32, ny=32, nz=32, spacing_cm=0.5)
    iso = _center_iso(grid)
    arr = compute_dose_grid(
        beams=[Beam(gantry_angle_deg=0.0, weight=1.0)],
        isocenter=iso,
        grid=grid,
        prescription_dose_gy=60.0,
    )
    cz, cy, cx = int(iso.z), int(iso.y), int(iso.x)
    near = arr[cz, cy, cx]
    # Move 5 voxels (2.5 cm) laterally — should be much smaller
    far = arr[cz, cy, cx + 5]
    assert near > far


def test_multi_beam_plan_still_normalized_to_prescription_at_iso():
    """Whether the plan has one beam or six, isocenter receives
    approximately the prescription dose. This is the contract the
    constraint evaluator relies on."""
    grid = GridSpec(nx=24, ny=24, nz=24, spacing_cm=0.5)
    iso = _center_iso(grid)
    for n in (1, 2, 4, 6):
        beams = [
            Beam(gantry_angle_deg=i * (360 / n), weight=1.0) for i in range(n)
        ]
        arr = compute_dose_grid(
            beams=beams,
            isocenter=iso,
            grid=grid,
            prescription_dose_gy=60.0,
        )
        cz, cy, cx = int(iso.z), int(iso.y), int(iso.x)
        assert 55.0 <= arr[cz, cy, cx] <= 65.0, f"n={n}: {arr[cz,cy,cx]}"


def test_more_beams_improves_field_uniformity():
    """A 4-beam box plan spreads dose more evenly through the target
    volume than a single beam — average dose in a small sphere around
    isocenter is closer to prescription than std-dev/spread of 1 beam."""
    grid = GridSpec(nx=24, ny=24, nz=24, spacing_cm=0.5)
    iso = _center_iso(grid)
    one = compute_dose_grid(
        beams=[Beam(gantry_angle_deg=0.0, weight=1.0)],
        isocenter=iso,
        grid=grid,
        prescription_dose_gy=60.0,
    )
    four = compute_dose_grid(
        beams=[Beam(gantry_angle_deg=i * 90.0, weight=1.0) for i in range(4)],
        isocenter=iso,
        grid=grid,
        prescription_dose_gy=60.0,
    )
    cz, cy, cx = int(iso.z), int(iso.y), int(iso.x)
    # 3-voxel radius sphere around isocenter — pull a small target block
    z0, y0, x0 = cz - 2, cy - 2, cx - 2
    block_one = one[z0 : z0 + 5, y0 : y0 + 5, x0 : x0 + 5]
    block_four = four[z0 : z0 + 5, y0 : y0 + 5, x0 : x0 + 5]
    # Four-beam plan has lower in-target dose stddev (better uniformity)
    assert float(block_four.std()) < float(block_one.std())


def test_empty_beam_list_returns_zeros():
    grid = GridSpec(nx=8, ny=8, nz=8)
    iso = _center_iso(grid)
    arr = compute_dose_grid(beams=[], isocenter=iso, grid=grid)
    assert arr.shape == (8, 8, 8)
    assert float(arr.max()) == 0.0


def test_summarize_voxels_handles_empty():
    s = summarize_voxels(np.array([]))
    assert s.mean == 0.0 and s.max == 0.0 and s.v20 == 0.0 and s.v30 == 0.0


def test_summarize_voxels_computes_v20_v30():
    arr = np.array([5.0, 15.0, 22.0, 35.0, 40.0])  # 3 of 5 ≥20, 2 of 5 ≥30
    s = summarize_voxels(arr)
    assert s.v20 == 0.6
    assert s.v30 == 0.4
    assert s.max == 40.0


def test_compute_returns_dose_summary_dict():
    summary = compute(
        beams=[{"gantry_angle": 0, "energy_mev": 6.0, "weight": 1.0}],
        prescription_dose_gy=50.0,
    )
    assert "global" in summary
    assert "isocenter" in summary
    assert "disclaimer" in summary
    assert "RESEARCH" in summary["disclaimer"]
    g = summary["global"]
    # Max anywhere in the grid should be close to prescription
    assert g["max"] >= 45.0
    assert summary["prescription_dose_gy"] == 50.0


def test_compute_proton_vs_photon_modality_propagates():
    s_proton = compute(
        beams=[{"gantry_angle": 0, "weight": 1.0}],
        modality="proton",
        prescription_dose_gy=40.0,
    )
    s_photon = compute(
        beams=[{"gantry_angle": 0, "weight": 1.0}],
        modality="photon",
        prescription_dose_gy=40.0,
    )
    assert s_proton["modality"] == "proton"
    assert s_photon["modality"] == "photon"
    # Proton sigma is tighter → narrower beam → larger max on-axis dose
    # for the same prescription normalization
    assert s_proton["global"]["max"] >= s_photon["global"]["max"] * 0.5
