"""SOP class + modality routing checks."""
from __future__ import annotations

from pydicom import Dataset

# Accepted SOP Class UIDs for ingestion. Anything else triggers a
# warning and a skip (we will not silently store unfamiliar SOP classes).
ACCEPTED_SOP_CLASSES = {
    "1.2.840.10008.5.1.4.1.1.1",        # CR Image Storage
    "1.2.840.10008.5.1.4.1.1.1.1",      # Digital X-Ray Image Storage - For Presentation
    "1.2.840.10008.5.1.4.1.1.1.2",      # Digital Mammography Image Storage - For Presentation
    "1.2.840.10008.5.1.4.1.1.2",        # CT Image Storage
    "1.2.840.10008.5.1.4.1.1.2.1",      # Enhanced CT Image Storage
    "1.2.840.10008.5.1.4.1.1.4",        # MR Image Storage
    "1.2.840.10008.5.1.4.1.1.4.1",      # Enhanced MR Image Storage
    "1.2.840.10008.5.1.4.1.1.7",        # Secondary Capture (allowed but flagged)
    "1.2.840.10008.5.1.4.1.1.66.4",     # Segmentation Storage
    "1.2.840.10008.5.1.4.1.1.88.22",    # Enhanced SR
    "1.2.840.10008.5.1.4.1.1.88.33",    # Comprehensive SR
    "1.2.840.10008.5.1.4.1.1.88.34",    # Comprehensive 3D SR
}

# (modality, body_part) → model registry key
MODEL_ROUTING = {
    ("MR", "BRAIN"): "brain_mri",
    ("MR", "HEAD"): "brain_mri",
    ("CT", "CHEST"): "lung_ct",
    ("CT", "LUNG"): "lung_ct",
    ("CT", "THORAX"): "lung_ct",
    ("MG", "BREAST"): "breast_mammo",
    ("CR", "BREAST"): "breast_mammo",
    ("DX", "BREAST"): "breast_mammo",
}


def is_accepted_sop_class(ds: Dataset) -> bool:
    sop = str(getattr(ds, "SOPClassUID", "") or "")
    return sop in ACCEPTED_SOP_CLASSES


def model_key_for(modality: str, body_part: str) -> str | None:
    return MODEL_ROUTING.get((modality.upper(), body_part.upper()))
