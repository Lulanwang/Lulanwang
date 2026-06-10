import pydicom
from pydicom.data import get_testdata_files
from pydicom.tag import Tag

from app.dicom.deidentify import BASIC_PROFILE_REMOVE, DATE_TAGS, deidentify


def _load_sample():
    paths = get_testdata_files("CT_small.dcm")
    return pydicom.dcmread(paths[0])


def test_basic_profile_tags_removed():
    ds = _load_sample()
    # Inject realistic PHI so the test is meaningful
    ds.PatientName = "Doe^John"
    ds.PatientID = "MRN-12345"
    ds.PatientAddress = "1 Main St"
    ds.ReferringPhysicianName = "Dr Smith"
    ds.InstitutionName = "Acme Hospital"
    ds.PatientBirthDate = "19850101"
    ds.StudyDate = "20240501"

    result = deidentify(ds)

    assert result.ok
    assert result.pseudonym
    # PatientName replaced
    assert str(ds.PatientName).startswith("ANON^")
    # PatientID replaced with pseudonym (hash, not original)
    assert str(ds.PatientID) == result.pseudonym
    # Every Basic Profile tag we listed must be gone
    for group, elem in BASIC_PROFILE_REMOVE:
        tag = Tag(group, elem)
        assert tag not in ds, f"tag {tag} should have been removed"
    # Marker tag added
    assert ds.PatientIdentityRemoved == "YES"


def test_private_tags_and_overlays_removed():
    """Basic Profile mandates stripping ALL private tags and the
    repeating overlay/curve groups — both are common PHI vectors that
    the hardcoded BASIC_PROFILE_REMOVE list does not cover."""
    ds = _load_sample()
    ds.PatientID = "MRN-99"

    # Inject a vendor private block carrying a patient name (the classic
    # leak), plus an overlay group with an annotation plane.
    block = ds.private_block(0x0009, "ACME PRIVATE", create=True)
    block.add_new(0x01, "LO", "Doe^John (operator note)")
    ds.add_new(Tag(0x6000, 0x0010), "US", 512)  # OverlayRows
    ds.add_new(Tag(0x6000, 0x0022), "LO", "PT NAME BURNED IN")  # OverlayDescription

    result = deidentify(ds)

    assert result.ok
    # No private tags survive
    private_tags = [el.tag for el in ds if el.tag.is_private]
    assert private_tags == [], f"private tags leaked: {private_tags}"
    # No overlay (0x60xx) or curve (0x50xx) repeating-group tags survive
    repeating = [
        el.tag
        for el in ds
        if 0x5000 <= el.tag.group <= 0x50FF or 0x6000 <= el.tag.group <= 0x60FF
    ]
    assert repeating == [], f"overlay/curve tags leaked: {repeating}"


def test_date_shift_preserves_intervals():
    ds = _load_sample()
    ds.PatientID = "patient-A"
    ds.StudyDate = "20240101"
    ds.PatientBirthDate = "19800101"
    result = deidentify(ds)
    assert result.ok
    # After de-id, the gap between StudyDate and BirthDate should be the same
    # (date shift applies to both).
    sd = ds[Tag(*DATE_TAGS[0])].value
    bd = ds[Tag(0x0010, 0x0030)].value
    # Both shifted by the same delta → still 44-year gap (16071 days).
    import datetime as dt
    sd_d = dt.datetime.strptime(str(sd), "%Y%m%d").date()
    bd_d = dt.datetime.strptime(str(bd), "%Y%m%d").date()
    assert (sd_d - bd_d).days == (dt.date(2024, 1, 1) - dt.date(1980, 1, 1)).days


def test_burned_in_annotation_blocks_ingestion():
    ds = _load_sample()
    ds.BurnedInAnnotation = "YES"
    result = deidentify(ds)
    assert not result.ok
    assert "BurnedInAnnotation" in (result.blocked_reason or "")
