"""Tests for the OAR constraint catalog and evaluation logic."""
from __future__ import annotations

from app.services import oar_constraints


def test_catalog_covers_common_organs():
    tissues = set(oar_constraints.supported_tissues())
    # Spot-check a representative slice
    assert "brainstem" in tissues
    assert "lung_left" in tissues
    assert "heart" in tissues
    assert "kidney_left" in tissues
    assert "spinal_cord" in tissues


def test_lookup_is_case_insensitive():
    by_lower = oar_constraints.lookup("heart")
    by_upper = oar_constraints.lookup("HEART")
    by_mixed = oar_constraints.lookup("Heart")
    assert len(by_lower) > 0
    assert len(by_lower) == len(by_upper) == len(by_mixed)


def test_evaluate_pass_when_observed_well_under_limit():
    # spinal cord max ≤50 Gy → 30 is comfortably under
    evals = oar_constraints.evaluate("spinal_cord", {"max": 30.0})
    assert len(evals) == 1
    assert evals[0].status == "pass"
    assert evals[0].observed == 30.0


def test_evaluate_warn_at_85_percent_of_limit():
    # spinal cord max ≤50 → 45 (90%) → warn
    evals = oar_constraints.evaluate("spinal_cord", {"max": 45.0})
    assert evals[0].status == "warn"


def test_evaluate_fail_when_observed_at_or_above_limit():
    # spinal cord max ≤50 → 55 → fail
    evals = oar_constraints.evaluate("spinal_cord", {"max": 55.0})
    assert evals[0].status == "fail"


def test_evaluate_missing_metric_returns_empty():
    # spinal cord has only a "max" constraint; "mean" alone returns nothing
    evals = oar_constraints.evaluate("spinal_cord", {"mean": 20.0})
    assert evals == []


def test_evaluate_unknown_tissue_returns_empty():
    assert oar_constraints.evaluate("not_a_real_organ", {"mean": 5.0}) == []


def test_lung_uses_v20_metric():
    # lung_left has both a v20 constraint (≤0.30) and mean lung_total (≤20)
    evals = oar_constraints.evaluate(
        "lung_left", {"v20": 0.25, "max": 50.0, "mean": 10.0}
    )
    assert any(e.constraint.metric == "v20" for e in evals)
    v20_eval = next(e for e in evals if e.constraint.metric == "v20")
    assert v20_eval.status == "pass"


def test_heart_has_both_mean_and_v30():
    metrics = {e.constraint.metric for e in oar_constraints.evaluate(
        "heart", {"mean": 22.0, "v30": 0.30}
    )}
    assert "mean" in metrics
    assert "v30" in metrics
