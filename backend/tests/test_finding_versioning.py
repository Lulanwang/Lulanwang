"""Unit tests for the Finding versioning state machine.

We don't spin up a real Postgres here — we exercise the row construction
and the transition rules via simple object manipulation. The full
HTTP-level behavior is exercised by the docker-compose smoke tests.
"""
from __future__ import annotations

import json
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


def _refine(prev: Finding, actor: uuid.UUID, label: str, geom: dict) -> Finding:
    """Reproduces the row math of POST /findings/{id}/refine without a DB.

    Note: SQLAlchemy's `default=uuid.uuid4` on the id column only fires on
    INSERT — when we construct rows in memory we have to set id explicitly,
    otherwise multiple rows share id=None and the chain walk gets confused.
    """
    new = Finding(
        id=uuid.uuid4(),
        study_id=prev.study_id,
        job_id=prev.job_id,
        parent_finding_id=prev.id,
        version=prev.version + 1,
        is_current=True,
        source="radiologist",
        status="modified",
        actor_id=actor,
        label=label,
        body_part=prev.body_part,
        confidence=None,
        icd10_suggestion=prev.icd10_suggestion,
        geometry=geom,
        model_name=prev.model_name,
        model_version=prev.model_version,
    )
    prev.is_current = False
    return new


def test_three_version_chain_history_order():
    """Build v1 (AI) → v2 (refine) → v3 (refine of refine); verify the
    parent chain walks in version order and only v3 is_current."""
    v1 = _ai_row()
    actor = uuid.uuid4()
    v2 = _refine(v1, actor, "tighten boundary", {"kind": "polygon", "points": [[0, 0]]})
    v3 = _refine(v2, actor, "redo with smart paint", {"kind": "mask", "ref": "seg-uid-1"})

    rows_by_id = {v1.id: v1, v2.id: v2, v3.id: v3}

    # Walk descendant chain from v1
    chain = [v1]
    cursor = v1
    while True:
        child = next(
            (r for r in rows_by_id.values() if r.parent_finding_id == cursor.id), None
        )
        if child is None:
            break
        chain.append(child)
        cursor = child

    assert [r.version for r in chain] == [1, 2, 3]
    assert [r.source for r in chain] == ["ai", "radiologist", "radiologist"]
    current_rows = [r for r in chain if r.is_current]
    assert current_rows == [v3], "only v3 should be is_current"
    assert v1.geometry == {"kind": "bbox", "x": 0.4, "y": 0.4, "w": 0.2, "h": 0.2}
    assert v2.geometry == {"kind": "polygon", "points": [[0, 0]]}


def test_report_filters_rejected_and_non_current():
    """Reproduce app.services.study_pipeline.generate_report's filter:
        is_current AND status IN ('proposed','accepted','modified')
    on a mixed population, including a rejected v1 with a refined v2 child.
    """
    study_id = uuid.uuid4()
    actor = uuid.uuid4()

    proposed_ai = _ai_row(study_id=study_id)            # is_current=True, proposed
    accepted_ai = _ai_row(study_id=study_id, status="accepted")  # is_current=True, accepted

    rejected_ai = _ai_row(study_id=study_id)
    rejected_ai.status = "rejected"
    rejected_ai.is_current = False                       # rejected → excluded

    refined_parent = _ai_row(study_id=study_id)          # will become non-current
    refined_v2 = _refine(refined_parent, actor, "edit", {"kind": "polygon"})

    population = [proposed_ai, accepted_ai, rejected_ai, refined_parent, refined_v2]
    visible = [
        r for r in population
        if r.is_current and r.status in ("proposed", "accepted", "modified")
    ]
    ids = {r.id for r in visible}

    assert proposed_ai.id in ids
    assert accepted_ai.id in ids
    assert refined_v2.id in ids
    assert refined_parent.id not in ids, "v1 should drop out after refinement"
    assert rejected_ai.id not in ids, "rejected should never reach the report"
    assert len(ids) == 3


def test_refine_preserves_parent_geometry_byte_identical():
    """Stronger version of the earlier test: after a refinement is built,
    the parent row's geometry dict must be **bit-identical** to before."""
    parent = _ai_row(geometry={"kind": "bbox", "x": 0.4, "y": 0.4, "w": 0.2, "h": 0.2})
    before = json.dumps(parent.geometry, sort_keys=True)
    _refine(parent, uuid.uuid4(), "refined", {"kind": "polygon", "points": [[1, 1]]})
    after = json.dumps(parent.geometry, sort_keys=True)
    assert before == after
    # Also: parent's status should NOT have been touched by refinement
    assert parent.status == "proposed"
    assert parent.source == "ai"
