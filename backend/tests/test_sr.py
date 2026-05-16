from io import BytesIO

import pydicom

from app.dicom.sr_tid1500 import SRFinding, build_sr


def test_sr_roundtrip_is_valid_dicom():
    sr = build_sr(
        study_instance_uid="1.2.3.4",
        patient_pseudonym="abcd1234",
        modality="CT",
        findings=[
            SRFinding(
                label="Pulmonary nodule, 9 mm",
                confidence=0.51,
                icd10="R91.1",
                model_name="MockModel",
                model_version="0.1.0",
            )
        ],
        impression="Test impression",
    )
    buf = BytesIO()
    pydicom.dcmwrite(buf, sr, enforce_file_format=True)
    buf.seek(0)
    parsed = pydicom.dcmread(buf)
    assert str(parsed.SOPClassUID) == "1.2.840.10008.5.1.4.1.1.88.34"
    assert parsed.Modality == "SR"
    # Disclaimer text must be present somewhere in the content tree
    text_blob = "".join(
        str(item.TextValue)
        for item in parsed.ContentSequence
        if getattr(item, "ValueType", "") == "TEXT"
    )
    assert "RESEARCH USE ONLY" in text_blob


def test_sr_handles_no_findings():
    sr = build_sr(
        study_instance_uid="1.2.3.4",
        patient_pseudonym="abcd1234",
        modality="MR",
        findings=[],
        impression="No findings",
    )
    assert sr.SOPClassUID == "1.2.840.10008.5.1.4.1.1.88.34"
