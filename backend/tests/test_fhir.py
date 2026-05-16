from app.fhir.diagnostic_report import diagnostic_report, imaging_study


def test_diagnostic_report_shape():
    dr = diagnostic_report(
        study_instance_uid="1.2.3",
        patient_pseudonym="abcd1234",
        modality="CT",
        impression="Nodule, 9 mm",
        icd10_codes=["R91.1", "C34.90"],
        model_name="MockModel",
        model_version="0.1.0",
    )
    assert dr["resourceType"] == "DiagnosticReport"
    assert dr["status"] == "preliminary"
    assert "RESEARCH USE ONLY" in dr["conclusion"]
    codes = {c["coding"][0]["code"] for c in dr["conclusionCode"]}
    assert codes == {"R91.1", "C34.90"}
    assert dr["code"]["coding"][0]["system"] == "http://loinc.org"


def test_imaging_study_shape():
    s = imaging_study(
        study_instance_uid="1.2.3",
        patient_pseudonym="abcd1234",
        modality="MR",
        started=None,
        description="Brain MRI",
    )
    assert s["resourceType"] == "ImagingStudy"
    assert s["identifier"][0]["value"] == "urn:oid:1.2.3"
    assert s["modality"][0]["code"] == "MR"
