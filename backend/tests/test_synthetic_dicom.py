"""Tests for the synthetic DICOM generator + the end-to-end ingest pipeline
(modulo the DB and Orthanc, which are exercised by docker-compose smoke tests).
"""
from io import BytesIO

import numpy as np
import pydicom

from app.dicom.deidentify import deidentify
from app.dicom.parse import assemble_volume, extract_study_meta
from app.dicom.sr_tid1500 import SRFinding, build_sr
from app.dicom.validators import is_accepted_sop_class, model_key_for
from app.fhir.diagnostic_report import diagnostic_report, imaging_study
from app.models.base import StudyInput
from app.models.registry import resolve_model
from app.services import icd10
from seed.synthetic_dicom import (
    generate_burned_in_study,
    generate_demo_studies,
)


def test_generate_demo_studies_covers_three_modalities():
    studies = generate_demo_studies()
    modalities = {(s.modality, s.body_part) for s in studies}
    assert ("MR", "BRAIN") in modalities
    assert ("CT", "CHEST") in modalities
    assert ("MG", "BREAST") in modalities


def test_ct_chest_has_multiple_slices_and_volume_assembles():
    ct = next(s for s in generate_demo_studies() if s.modality == "CT")
    assert len(ct.datasets) >= 10
    vol = assemble_volume(ct.datasets)
    # (Z, Y, X)
    assert vol.ndim == 3
    assert vol.shape[0] == len(ct.datasets)
    # Modality LUT (RescaleSlope=1, Intercept=-1024) should produce HU-like values
    assert vol.min() < 0  # below water → some air-ish voxels
    assert vol.max() > 0


def test_mr_brain_has_multiple_slices():
    mr = next(s for s in generate_demo_studies() if s.modality == "MR")
    assert len(mr.datasets) >= 10
    for ds in mr.datasets:
        assert ds.Modality == "MR"
        assert ds.BodyPartExamined == "BRAIN"


def test_mammogram_single_high_res_image():
    mg = next(s for s in generate_demo_studies() if s.modality == "MG")
    assert len(mg.datasets) == 1
    ds = mg.datasets[0]
    assert ds.Rows >= 1024
    assert ds.ViewPosition == "CC"


def test_all_synthetic_instances_are_accepted_sop_classes():
    for synth in generate_demo_studies():
        for ds in synth.datasets:
            assert is_accepted_sop_class(ds), (
                f"SOP {ds.SOPClassUID} not accepted for {synth.modality}"
            )


def test_synthetic_routes_to_expected_model_keys():
    studies = generate_demo_studies()
    keys = {model_key_for(s.modality, s.body_part) for s in studies}
    assert {"brain_mri", "lung_ct", "breast_mammo"} == keys


def test_dicomwrite_roundtrip_preserves_uids():
    """Synthetic datasets must survive pydicom write+read; this is what STOW does."""
    for synth in generate_demo_studies():
        for ds in synth.datasets[:2]:
            buf = BytesIO()
            pydicom.dcmwrite(buf, ds, enforce_file_format=True)
            buf.seek(0)
            parsed = pydicom.dcmread(buf)
            assert str(parsed.SOPInstanceUID) == str(ds.SOPInstanceUID)
            assert str(parsed.StudyInstanceUID) == str(ds.StudyInstanceUID)
            assert parsed.pixel_array.shape == (ds.Rows, ds.Columns)


def test_deidentify_strips_phi_from_synthetic_studies():
    """The generator deliberately fills PHI (PatientName, ReferringPhysician,
    InstitutionName, AccessionNumber) so de-id must strip it."""
    for synth in generate_demo_studies():
        ds = synth.datasets[0]
        assert str(ds.PatientName).startswith("SYNTHETIC^")
        original_birthdate = ds.PatientBirthDate

        result = deidentify(ds)
        assert result.ok

        assert str(ds.PatientName).startswith("ANON^")
        assert "ReferringPhysicianName" not in ds
        assert "InstitutionName" not in ds
        assert "AccessionNumber" not in ds
        # Birth date is shifted (preserved interval), not removed
        assert ds.PatientBirthDate != ""
        # Should be at most ~90 days different
        assert ds.PatientBirthDate != original_birthdate or result.date_shift_days == 0


def test_burned_in_study_is_blocked():
    s = generate_burned_in_study()
    for ds in s.datasets:
        r = deidentify(ds)
        assert not r.ok
        assert "BurnedInAnnotation" in (r.blocked_reason or "")


def test_extracts_correct_metadata_from_synthetic():
    for synth in generate_demo_studies():
        meta = extract_study_meta(synth.datasets[0])
        assert meta.modality == synth.modality
        assert meta.body_part == synth.body_part
        assert meta.study_instance_uid


def test_pipeline_module_chain_runs_on_synthetic():
    """End-to-end module chain: synthetic study → de-id → resolve model →
    infer → ICD-10 suggest → build SR + FHIR. No DB, no Orthanc.

    This is the closest we can get to integration testing without booting
    the full docker-compose stack.
    """
    for synth in generate_demo_studies():
        # Copy datasets so the de-id mutation doesn't leak between tests
        datasets = [pydicom.dcmread(BytesIO(_dump(ds))) for ds in synth.datasets]
        for ds in datasets:
            r = deidentify(ds)
            assert r.ok

        model = resolve_model(synth.modality, synth.body_part)
        assert model is not None, f"no model for {synth.modality}/{synth.body_part}"

        findings = model.infer(
            StudyInput(
                study_instance_uid=str(datasets[0].StudyInstanceUID),
                modality=synth.modality,
                body_part=synth.body_part,
                datasets=datasets,
                tempdir="/tmp",
            )
        )
        assert findings, f"model produced no findings for {synth.modality}/{synth.body_part}"

        for f in findings:
            suggestion = f.icd10_suggestion or icd10.suggest_for(f.label, f.body_part)
            if suggestion is not None:
                assert isinstance(suggestion, str)
                assert len(suggestion) >= 3

        sr = build_sr(
            study_instance_uid=str(datasets[0].StudyInstanceUID),
            patient_pseudonym=str(datasets[0].PatientID),
            modality=synth.modality,
            findings=[
                SRFinding(
                    label=f.label,
                    confidence=f.confidence,
                    icd10=f.icd10_suggestion,
                    model_name=model.name,
                    model_version=model.version,
                )
                for f in findings
            ],
            impression="auto",
        )
        assert sr.Modality == "SR"

        dr = diagnostic_report(
            study_instance_uid=str(datasets[0].StudyInstanceUID),
            patient_pseudonym=str(datasets[0].PatientID),
            modality=synth.modality,
            impression="auto",
            icd10_codes=[f.icd10_suggestion for f in findings if f.icd10_suggestion],
            model_name=model.name,
            model_version=model.version,
        )
        assert dr["resourceType"] == "DiagnosticReport"
        assert "RESEARCH USE ONLY" in dr["conclusion"]

        s = imaging_study(
            study_instance_uid=str(datasets[0].StudyInstanceUID),
            patient_pseudonym=str(datasets[0].PatientID),
            modality=synth.modality,
            started=None,
            description=synth.description,
        )
        assert s["modality"][0]["code"] == synth.modality


def _dump(ds) -> bytes:
    buf = BytesIO()
    pydicom.dcmwrite(buf, ds, enforce_file_format=True)
    return buf.getvalue()


def test_lesion_visible_in_synthetic_pixel_data():
    """The generator places a bright spot — a reviewer / model should be
    able to find it. Compare the max pixel in the middle slice vs the
    edge slices."""
    ct = next(s for s in generate_demo_studies() if s.modality == "CT")
    mid_idx = len(ct.datasets) // 2
    mid_max = np.asarray(ct.datasets[mid_idx].pixel_array).max()
    edge_max = np.asarray(ct.datasets[0].pixel_array).max()
    # The middle slice (with nodule) should peak higher than the edge slice
    assert mid_max > edge_max
