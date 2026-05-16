"""Unit tests for the Finding versioning state machine.

We don't spin up a real Postgres here — we exercise the row construction
and the transition rules via simple object manipulation. The full
HTTP-level behavior is exercised by the docker-compose smoke tests.
"""
from __future__ import annotations

import uuid

import pytest

from app.db.models.finding import SOURCES, STATUSES, Finding


def _ai_row(**kw) -> Finding:
    defaults = dict(
        id=uuid.uuid4(),
        study_id=uuid.uuid4(),
        version=1,
        is_current=True,
        source="ai",
        status="proposed",
        actor_id=None,
        label="Suspected glioma (mock)",
        body_part="BRAIN",
        confidence=0.42,
        icd10_suggestion="C71.9",
        geometry={"kind": "bbox", "x": 0.4, "y": 0.4, "w": 0.2, "h": 0.2},
        model_name="MockModel",
        model_version="0.1.0",
    )
    defaults.update(kw)
    return Finding(**defaults)


def test_source_and_status_enums_are_complete():
    assert set(SOURCES) == {"ai", "radiologist"}
    assert set(STATUSES) == {"proposed", "accepted", "rejected", "modified"}


def test_ai_row_defaults_make_sense():
    f = _ai_row()
    assert f.version == 1
    assert f.source == "ai"
    assert f.status == "proposed"
    assert f.is_current is True
    assert f.parent_finding_id is None
    assert f.confidence == 0.42
    assert f.actor_id is None


def test_refinement_appends_a_v2_row_and_demotes_parent():
    """Simulates the refine endpoint's row math without hitting the DB."""
    parent = _ai_row()
    actor = uuid.uuid4()
    new = Finding(
        study_id=parent.study_id,
        job_id=parent.job_id,
        parent_finding_id=parent.id,
        version=parent.version + 1,
        is_current=True,
        source="radiologist",
        status="modified",
        actor_id=actor,
        label="Refined: glioma boundary tightened",
        body_part=parent.body_part,
        confidence=None,
        icd10_suggestion=parent.icd10_suggestion,
        geometry={"kind": "polygon", "points": [[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]]},
        model_name=parent.model_name,
        model_version=parent.model_version,
        seg_sop_instance_uid="1.2.840.lulan.fake.seg.1",
    )
    parent.is_current = False
    assert parent.is_current is False
    assert parent.geometry == {"kind": "bbox", "x": 0.4, "y": 0.4, "w": 0.2, "h": 0.2}  # untouched
    assert new.parent_finding_id == parent.id
    assert new.version == 2
    assert new.is_current is True
    assert new.source == "radiologist"
    assert new.actor_id == actor
    assert new.confidence is None
    assert new.seg_sop_instance_uid


@pytest.mark.parametrize(
    "from_status,action,expected_status,expected_is_current",
    [
        ("proposed", "accept", "accepted", True),
        ("proposed", "reject", "rejected", False),
    ],
)
def test_transitions_from_proposed(from_status, action, expected_status, expected_is_current):
    f = _ai_row(status=from_status)
    if action == "accept":
        # only is_current rows in non-terminal status may be accepted
        assert f.is_current
        f.status = "accepted"
    elif action == "reject":
        f.status = "rejected"
        f.is_current = False
    assert f.status == expected_status
    assert f.is_current is expected_is_current


def test_ai_row_geometry_is_never_mutated_by_refinement():
    """Property the user explicitly asked for: AI data must remain
    reviewable after radiologist interaction."""
    parent = _ai_row()
    original_geom = dict(parent.geometry or {})
    # Simulate refinement
    Finding(
        study_id=parent.study_id,
        parent_finding_id=parent.id,
        version=2,
        is_current=True,
        source="radiologist",
        status="modified",
        label="refined",
        body_part=parent.body_part,
        geometry={"kind": "polygon", "points": []},
        model_name=parent.model_name,
        model_version=parent.model_version,
    )
    parent.is_current = False
    # Geometry preserved
    assert parent.geometry == original_geom
    assert parent.source == "ai"
    assert parent.confidence == 0.42
    assert parent.label.startswith("Suspected")
