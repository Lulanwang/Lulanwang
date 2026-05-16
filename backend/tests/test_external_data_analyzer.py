"""Tests for seed/analyze_external_data.py.

We exercise the analyzer on a small, deterministic subset of pydicom's
bundled samples — no network — to assert:

  - It analyzes every input without raising
  - Real anatomical tags (BodyPartExamined=HEAD on emri_small) route to the
    expected model and produce findings with the expected ICD-10 codes
  - Malformed/test-fixture inputs are reported, not crashed on
  - Synonym mapping (HEAD → BRAIN, LUNG/THORAX → CHEST) routes correctly

The full analyzer (which also downloads from pydicom-data on GitHub) is
exercised via `python -m seed.analyze_external_data` and not in unit
tests, to keep CI offline.
"""
from __future__ import annotations

from pathlib import Path

from pydicom.data import get_testdata_files

from seed.analyze_external_data import _analyze, _body_part_from_text, _markdown_report


def _bundled_paths() -> list[Path]:
    return [Path(p) for p in get_testdata_files() if p.lower().endswith(".dcm")][:30]


def test_analyzer_does_not_crash_on_bundled_samples():
    results = [_analyze(p, source="test") for p in _bundled_paths()]
    assert len(results) > 0
    # No uncaught exceptions; analyzer wraps every input in a FileResult.
    for r in results:
        assert r.name
        assert r.source == "test"


def test_brain_keyword_inference():
    assert _body_part_from_text("Brain MRI with glioma") == "BRAIN"
    assert _body_part_from_text("emri_small.dcm") == "BRAIN"
    assert _body_part_from_text("Neuro routine T1") == "BRAIN"


def test_chest_keyword_inference():
    assert _body_part_from_text("Chest CT screening") == "CHEST"
    assert _body_part_from_text("LDCT pulmonary nodule eval") == "CHEST"
    assert _body_part_from_text("Thorax routine") == "CHEST"


def test_breast_keyword_inference():
    assert _body_part_from_text("Screening mammogram CC view") == "BREAST"
    assert _body_part_from_text("Breast tomosynthesis") == "BREAST"


def test_synonym_head_routes_to_brain():
    # emri_small.dcm explicitly tags BodyPartExamined=HEAD → must route to BRAIN.
    from pydicom.data import get_testdata_file

    path = get_testdata_file("emri_small.dcm")
    assert path is not None
    r = _analyze(Path(path), source="test")
    assert r.body_part == "BRAIN", f"expected BRAIN, got {r.body_part}"
    assert r.model_key == "brain_mri"
    assert r.finding_count >= 1
    # Mock model returns C71.9 for brain glioma
    assert any(c == "C71.9" for c in r.icd10_codes)


def test_markdown_report_renders_without_errors_on_mixed_inputs():
    results = [_analyze(p, source="test") for p in _bundled_paths()]
    md = _markdown_report(results)
    assert "# External DICOM data analysis" in md
    assert "## Summary" in md
    # Markdown table header
    assert "| Source |" in md
