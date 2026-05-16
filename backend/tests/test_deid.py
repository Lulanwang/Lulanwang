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
    assert ds.PatientName.original_string.startswith("ANON^")
    # PatientID replaced with pseudonym (hash, not original)
    assert str(ds.PatientID) == result.pseudonym
    # Every Basic Profile tag we listed must be gone
    for group, elem in BASIC_PROFILE_REMOVE:
        tag = Tag(group, elem)
        assert tag not in ds, f"tag {tag} should have been removed"
    # Marker tag added
    assert ds.PatientIdentityRemoved == "YES"


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
