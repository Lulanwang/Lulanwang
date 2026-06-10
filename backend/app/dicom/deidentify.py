"""DICOM de-identification per PS3.15 Annex E (NEMA Sup 142).

Implements:
- **Basic Profile**: removes/replaces the mandatory tag set.
- **Clean Descriptors Option**: scrubs free-text descriptor fields.
- **Retain Longitudinal Temporal Information with Modified Dates**:
  shifts every Date/Time by a per-patient offset (preserves intervals).

Burned-in pixel PHI is detected but NOT redacted: if
`BurnedInAnnotation=YES` or `RecognizableVisualFeatures=YES`, ingestion
is blocked and a manual-QA warning is returned.

This is **not** a complete or certified de-identification implementation.
Production deployments must:
  - Apply additional Annex E options based on data-use agreements
  - Validate against the institution's IRB / DPA requirements
  - Use OCR-based pixel redaction for SC / OT / annotated modalities
  - Replace `_hmac_pseudonym` with an HSM-backed keyed hash
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import random
import re
from dataclasses import dataclass

from pydicom import Dataset
from pydicom.tag import Tag

from app.core.config import settings

# Basic Profile tag list (PS3.15 Annex E, Table E.1-1). Trimmed to the
# subset that actually appears in pixel-data-bearing SOP classes for
# CR/DX/CT/MR/MG. Production deployments should consult the full table.
BASIC_PROFILE_REMOVE: tuple[tuple[int, int], ...] = (
    (0x0008, 0x0014),  # Instance Creator UID
    (0x0008, 0x0050),  # Accession Number
    (0x0008, 0x0080),  # Institution Name
    (0x0008, 0x0081),  # Institution Address
    (0x0008, 0x0090),  # Referring Physician's Name
    (0x0008, 0x0092),  # Referring Physician's Address
    (0x0008, 0x0094),  # Referring Physician's Telephone Numbers
    (0x0008, 0x1010),  # Station Name
    (0x0008, 0x1030),  # Study Description    (cleared by Clean Descriptors)
    (0x0008, 0x103E),  # Series Description   (cleared by Clean Descriptors)
    (0x0008, 0x1040),  # Institutional Department Name
    (0x0008, 0x1048),  # Physician(s) of Record
    (0x0008, 0x1050),  # Performing Physician's Name
    (0x0008, 0x1060),  # Name of Physician(s) Reading Study
    (0x0008, 0x1070),  # Operators' Name
    (0x0008, 0x1080),  # Admitting Diagnoses Description
    (0x0010, 0x1000),  # Other Patient IDs
    (0x0010, 0x1001),  # Other Patient Names
    (0x0010, 0x1040),  # Patient's Address
    (0x0010, 0x2154),  # Patient's Telephone Numbers
    (0x0010, 0x2160),  # Ethnic Group
    (0x0010, 0x21B0),  # Additional Patient History
    (0x0010, 0x4000),  # Patient Comments
    (0x0018, 0x1000),  # Device Serial Number
    (0x0018, 0x1030),  # Protocol Name        (cleared by Clean Descriptors)
    (0x0020, 0x0010),  # Study ID
    (0x0020, 0x4000),  # Image Comments
    (0x0032, 0x1032),  # Requesting Physician
    (0x0032, 0x1060),  # Requested Procedure Description
    (0x0038, 0x0010),  # Admission ID
    (0x0038, 0x0050),  # Special Needs
    (0x0038, 0x0300),  # Current Patient Location
    (0x0038, 0x0400),  # Patient's Institution Residence
    (0x0038, 0x0500),  # Patient State
    (0x0040, 0x0006),  # Scheduled Performing Physician's Name
    (0x0040, 0x0007),  # Scheduled Procedure Step Description
    (0x0040, 0x0275),  # Request Attributes Sequence
    (0x0040, 0x1001),  # Requested Procedure ID
    (0x0040, 0x1010),  # Names of Intended Recipients of Results
    (0x0040, 0x1400),  # Requested Procedure Comments
    (0x0040, 0x2001),  # Reason for Imaging Service Request
    (0x0040, 0x2400),  # Imaging Service Request Comments
    (0x4008, 0x0114),  # Physician(s) Approving Interpretation
    (0x4008, 0x0115),  # Interpretation Diagnosis Description
)

# Tags that are date/time and should be shifted (not removed) under the
# "Retain Longitudinal Temporal Information with Modified Dates Option".
DATE_TAGS: tuple[tuple[int, int], ...] = (
    (0x0008, 0x0020),  # Study Date
    (0x0008, 0x0021),  # Series Date
    (0x0008, 0x0022),  # Acquisition Date
    (0x0008, 0x0023),  # Content Date
    (0x0010, 0x0030),  # Patient Birth Date
    (0x0010, 0x21D0),  # Last Menstrual Date
)


@dataclass
class DeidResult:
    ok: bool
    pseudonym: str
    date_shift_days: int
    warnings: list[str]
    blocked_reason: str | None = None


def _hmac_pseudonym(patient_id: str) -> str:
    """Stable HMAC-SHA256 pseudonym keyed by the site secret.

    Production: replace with an HSM-backed keyed hash so the key never
    sits in process memory or app config.
    """
    key = settings.app_secret.encode()
    return hmac.new(key, patient_id.encode(), hashlib.sha256).hexdigest()[:32]


def _deterministic_date_shift(patient_id: str) -> int:
    seed = int.from_bytes(hashlib.sha256(patient_id.encode()).digest()[:4], "big")
    rng = random.Random(seed)
    n = settings.deid_date_shift_days_max
    return rng.randint(-n, n)


def _shift_date(date_str: str, days: int) -> str | None:
    """DICOM DA format is YYYYMMDD."""
    if not date_str or not re.fullmatch(r"\d{8}", date_str):
        return date_str or None
    try:
        d = dt.datetime.strptime(date_str, "%Y%m%d").date()
        return (d + dt.timedelta(days=days)).strftime("%Y%m%d")
    except ValueError:
        return None


def _remove_repeating_groups(ds: Dataset) -> None:
    """Delete all overlay (0x6000-0x60FF) and curve (0x5000-0x50FF)
    repeating groups.

    Overlay planes (incl. ``OverlayData``, 0x60xx,3000) frequently carry
    burned-in annotations and patient identifiers; curve data (retired,
    but still seen) can carry the same. The Basic Profile removes both.
    We collect the tags first because deleting during iteration mutates
    the dataset.
    """
    to_delete = [
        elem.tag
        for elem in ds
        if 0x5000 <= elem.tag.group <= 0x50FF or 0x6000 <= elem.tag.group <= 0x60FF
    ]
    for tag in to_delete:
        del ds[tag]


def _has_burned_in_phi(ds: Dataset) -> tuple[bool, str | None]:
    if getattr(ds, "BurnedInAnnotation", "").upper() == "YES":
        return True, "BurnedInAnnotation=YES"
    if getattr(ds, "RecognizableVisualFeatures", "").upper() == "YES":
        return True, "RecognizableVisualFeatures=YES"
    # Secondary Capture and "Other" modalities frequently contain
    # screenshot overlays; require manual QA.
    modality = getattr(ds, "Modality", "")
    if modality in {"SC", "OT"}:
        return True, f"Modality={modality} requires manual pixel-PHI QA"
    return False, None


def deidentify(ds: Dataset) -> DeidResult:
    """Mutate `ds` in place per PS3.15 Annex E Basic Profile."""
    warnings: list[str] = []

    blocked, reason = _has_burned_in_phi(ds)
    if blocked:
        return DeidResult(
            ok=False,
            pseudonym="",
            date_shift_days=0,
            warnings=warnings,
            blocked_reason=reason,
        )

    original_patient_id = str(getattr(ds, "PatientID", "") or "anonymous")
    pseudonym = _hmac_pseudonym(original_patient_id)
    shift = _deterministic_date_shift(original_patient_id)

    # Replace patient identifiers
    ds.PatientID = pseudonym
    ds.PatientName = f"ANON^{pseudonym[:8]}"

    # Remove tags from Basic Profile
    for group, elem in BASIC_PROFILE_REMOVE:
        tag = Tag(group, elem)
        if tag in ds:
            del ds[tag]

    # Basic Profile also mandates removing ALL private tags (vendor
    # private blocks routinely carry patient name, operator, accession,
    # raw demographics) and stripping repeating overlay/curve groups,
    # which are a common burned-in-PHI vector. Without these, the
    # docstring's Annex-E claim would not hold.
    ds.remove_private_tags()
    _remove_repeating_groups(ds)

    # Date shifting
    for group, elem in DATE_TAGS:
        tag = Tag(group, elem)
        if tag in ds and ds[tag].value:
            new = _shift_date(str(ds[tag].value), shift)
            if new:
                ds[tag].value = new

    # De-identification marker tags
    ds.PatientIdentityRemoved = "YES"
    # 0012,0063 Deidentification Method
    ds.add_new(Tag(0x0012, 0x0063), "LO", "Lulan-MVP/PS3.15-Annex-E/Basic+CleanDescriptors+ShiftedDates")
    # 0012,0064 Deidentification Method Code Sequence — omitted (would need coded sequence)

    return DeidResult(
        ok=True,
        pseudonym=pseudonym,
        date_shift_days=shift,
        warnings=warnings,
    )
