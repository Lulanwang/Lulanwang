from app.models.mock import MockModel
from app.models.base import StudyInput


def test_mock_brain_returns_glioma_finding():
    m = MockModel("MR", "BRAIN")
    out = m.infer(
        StudyInput(
            study_instance_uid="1.2.3", modality="MR", body_part="BRAIN", datasets=[], tempdir="/tmp"
        )
    )
    labels = [f.label for f in out]
    assert any("glioma" in lbl.lower() for lbl in labels)
    assert any(f.icd10_suggestion == "C71.9" for f in out)


def test_mock_lung_returns_nodule_finding():
    m = MockModel("CT", "CHEST")
    out = m.infer(
        StudyInput(
            study_instance_uid="1.2.3", modality="CT", body_part="CHEST", datasets=[], tempdir="/tmp"
        )
    )
    assert any("nodule" in f.label.lower() for f in out)
    assert any(f.icd10_suggestion == "R91.1" for f in out)


def test_mock_breast_returns_microcalc_finding():
    m = MockModel("MG", "BREAST")
    out = m.infer(
        StudyInput(
            study_instance_uid="1.2.3", modality="MG", body_part="BREAST", datasets=[], tempdir="/tmp"
        )
    )
    assert any("microcalc" in f.label.lower() for f in out)
