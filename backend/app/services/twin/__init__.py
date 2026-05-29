"""3D digital-twin pipeline.

`config` exposes the segmentation-config version used as the cache
idempotency key. `pipeline.run_twin_generation` is the orchestrator
called from the background runner. Everything else lives behind
:mod:`app.services.twin.segment` and :mod:`app.services.twin.meshing`
so a future MONAI organ model can be slotted in without touching the
API or storage layers.
"""
from app.services.twin.config import SEG_CONFIG_VERSION  # noqa: F401
