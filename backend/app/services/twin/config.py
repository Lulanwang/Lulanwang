"""Configuration for the 3D twin pipeline.

Bumping SEG_CONFIG_VERSION invalidates every cached twin: the next
``POST /twins/{study_id}/generate`` for any study will produce a fresh
one. This is the migration path when a real MONAI organ model is
swapped in for the classical-CV segmenters.
"""
from __future__ import annotations

# Versioned tag stamped into ``organ_twins.seg_config_version``.
# Format: "<segmenter-family>-<integer>".
SEG_CONFIG_VERSION = "twin-cv-1"

# Mesh-budget targets in face count. The organ is the big surface; lesions
# are small accents. Quadric decimation cuts to these counts after
# marching cubes.
ORGAN_FACE_BUDGET = 40_000
LESION_FACE_BUDGET = 5_000

# Hard ceiling on the final GLB. If we go over, organ is re-decimated
# once to half the budget. Keeps the browser fetch responsive.
GLB_BYTES_CEILING = 5 * 1024 * 1024

# Taubin smoothing: lambda/mu pair. mu must be negative and |mu| > lambda
# so the algorithm does not shrink the volume across iterations.
TAUBIN_LAMBDA = 0.5
TAUBIN_MU = -0.53
TAUBIN_ITERATIONS = 10

# Pre-marching-cubes Gaussian smoothing of the mask field. σ in voxels —
# the higher, the smoother the surface but the less faithful to the mask.
MASK_SIGMA = 1.0

# Default per-structure colors (hex RGB). Sampled to keep the demo
# visually distinct from the existing contour palette.
ORGAN_COLOR = "#9aa6f5"        # soft blue — organ envelope
ORGAN_OPACITY = 0.35           # semi-transparent so lesions show through
LESION_COLORS = (
    "#f87171",                  # red-400
    "#fb923c",                  # orange-400
    "#facc15",                  # yellow-400
    "#34d399",                  # emerald-400
    "#a78bfa",                  # violet-400
)


def lesion_color(index: int) -> str:
    """Deterministic color per lesion index."""
    return LESION_COLORS[index % len(LESION_COLORS)]
