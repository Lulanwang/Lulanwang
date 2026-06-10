"""Tests for the RADS scoring service."""
from __future__ import annotations

import pytest

from app.services import rads


def test_applicable_scheme_breast_mg():
    assert rads.applicable_scheme("MG", "BREAST") == "BI-RADS"
    assert rads.applicable_scheme("CR", "BREAST") == "BI-RADS"  # body_part wins


def test_applicable_scheme_lung_ct():
    assert rads.applicable_scheme("CT", "CHEST") == "Lung-RADS"
    assert rads.applicable_scheme("CT", "LUNG") == "Lung-RADS"
    assert rads.applicable_scheme("CT", "THORAX") == "Lung-RADS"


def test_applicable_scheme_brain_mr():
    assert rads.applicable_scheme("MR", "BRAIN") == "BT-RADS"
    assert rads.applicable_scheme("MR", "HEAD") == "BT-RADS"


def test_applicable_scheme_none_for_unrecognized():
    assert rads.applicable_scheme("US", "ABDOMEN") is None
    assert rads.applicable_scheme("XA", "CHEST") is None


def test_validate_returns_matched_code():
    c = rads.validate("BI-RADS", "4B")
    assert c.code == "4B"
    assert c.scheme == "BI-RADS"
    assert "suspicion" in c.descriptor.lower()


def test_validate_rejects_wrong_code_for_scheme():
    # Lung-RADS doesn't have 4C; BI-RADS does
    with pytest.raises(ValueError):
        rads.validate("Lung-RADS", "4C")
    rads.validate("BI-RADS", "4C")  # should pass


def test_validate_rejects_unknown_scheme():
    with pytest.raises(ValueError):
        rads.validate("FOO-RADS", "1")  # type: ignore[arg-type]


def test_build_score_emits_full_record():
    score = rads.build_score(scheme="Lung-RADS", code="4A", scored_by="user-1")
    assert score["scheme"] == "Lung-RADS"
    assert score["code"] == "4A"
    assert score["scored_by"] == "user-1"
    assert "scored_at" in score
    assert "Suspicious" in score["descriptor"]


def test_coded_value_shape():
    score = rads.build_score(scheme="BT-RADS", code="3c")
    cv = rads.coded_value(score)
    assert cv == {
        "CodeValue": "3c",
        "CodingSchemeDesignator": "BT-RADS",
        "CodeMeaning": "Worsening — probable tumor progression",
    }


def test_all_schemes_have_codes():
    for scheme, codes in rads.ALL.items():
        assert len(codes) > 0
        for c in codes:
            assert c.scheme == scheme
            assert c.code
            assert c.descriptor
