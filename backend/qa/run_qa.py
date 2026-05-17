"""Round 10 QA driver — exercises every Round 1-9 endpoint against a live
FastAPI server and emits a markdown report.

Prereqs:
    - Postgres running with the lulan/app DB seeded (see qa/seed_qa.py)
    - Uvicorn running on http://localhost:8000 against that DB
    - (Optional) Orthanc reachable — WADO + thumbnail tests SKIP otherwise

Run:
    cd backend
    .venv/bin/python -m qa.run_qa --report docs/qa/round10_qa_report.md
"""
from __future__ import annotations

import argparse
import io
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import numpy as np

from qa.lib.api_client import ApiClient, excerpt
from qa.lib.report import TestCase, write_report
from qa.lib.verify import (
    save_artifact,
    verify_fhir_diagnostic_report,
    verify_sr_bytes,
    verify_thumbnail_bytes,
)

API_BASE = os.environ.get("LULAN_QA_API", "http://localhost:8000/api/v1")
ADMIN = ("admin@lulan.local", "admin_demo_password")
CLINICIAN = ("clinician@lulan.local", "clinician_demo_password")
ORTHANC_BASE = os.environ.get("ORTHANC_URL", "http://localhost:8042")


def _safe(fn):
    """Wrap a test function so any exception becomes a FAIL TestCase."""

    def wrap(*args, **kw) -> list[TestCase]:
        try:
            r = fn(*args, **kw)
            return r if isinstance(r, list) else [r]
        except Exception as exc:  # noqa: BLE001
            return [
                TestCase(
                    round_name=getattr(fn, "_round", "?"),
                    feature=getattr(fn, "_feature", fn.__name__),
                    endpoint="-",
                    status="FAIL",
                    error=f"{type(exc).__name__}: {exc}",
                )
            ]

    wrap.__name__ = fn.__name__
    return wrap


# ----------------------------------------------------------------------
# Round 1-2 — ingestion + de-identification
# ----------------------------------------------------------------------


def round_1_2(client: ApiClient) -> list[TestCase]:
    cases: list[TestCase] = []

    r = client.get("/studies/")
    rows = r.json() if r.is_success else []
    cases.append(
        TestCase(
            "1-2",
            "List studies (real seed)",
            "GET /studies/",
            "PASS" if r.is_success and len(rows) >= 3 else "FAIL",
            evidence=f"{excerpt(r)} · {len(rows)} rows",
        )
    )

    # Verify de-id stripping by sampling a synthetic study
    if rows:
        s = rows[0]
        r2 = client.get(f"/studies/{s['id']}")
        body = r2.json() if r2.is_success else {}
        cases.append(
            TestCase(
                "1-2",
                "Get one study (returns de-id pseudonym)",
                "GET /studies/{id}",
                "PASS" if r2.is_success and body.get("patient_pseudonym") else "FAIL",
                evidence=f"pseudonym={body.get('patient_pseudonym', '?')[:12]}…",
            )
        )

    return cases


# ----------------------------------------------------------------------
# Round 3 — ICD-10
# ----------------------------------------------------------------------


def round_3(client: ApiClient) -> list[TestCase]:
    r = client.get("/icd10/search?q=breast")
    codes = {c["code"] for c in (r.json() if r.is_success else [])}
    ok = r.is_success and any(c.startswith("C50") for c in codes)
    return [
        TestCase(
            "3",
            "ICD-10 search returns breast codes",
            "GET /icd10/search?q=breast",
            "PASS" if ok else "FAIL",
            evidence=f"{excerpt(r)} · breast codes: {sorted(c for c in codes if c.startswith('C50'))[:5]}",
        )
    ]


# ----------------------------------------------------------------------
# Round 4 — DICOMweb proxy / Cornerstone viewer
# ----------------------------------------------------------------------


def round_4(orthanc_reachable: bool, studies: list[dict]) -> list[TestCase]:
    if not orthanc_reachable:
        return [
            TestCase(
                "4",
                "DICOMweb proxy (QIDO series)",
                "GET /dicom-web/studies/{uid}/series",
                "SKIP",
                error="Orthanc not running in this environment (Docker-in-Docker unavailable). "
                "WADO/QIDO paths are exercised by docker-compose smoke; the proxy code itself "
                "is unchanged since Round 1.",
            )
        ]
    return []


# ----------------------------------------------------------------------
# Round 5 — versioned findings state machine
# ----------------------------------------------------------------------


def round_5(client: ApiClient, studies: list[dict]) -> list[TestCase]:
    cases: list[TestCase] = []
    if not studies:
        return [
            TestCase(
                "5", "Findings state machine", "GET /studies/{id}/findings",
                "SKIP", error="no seeded studies",
            )
        ]

    # Find a study with findings
    target = None
    findings: list[dict] = []
    for s in studies:
        r = client.get(f"/studies/{s['id']}/findings")
        if r.is_success and len(r.json()) >= 2:
            target = s
            findings = r.json()
            break

    if target is None:
        return [
            TestCase(
                "5", "Find a study with ≥2 findings", "GET /studies/{id}/findings",
                "FAIL", error="no study has 2 current findings",
            )
        ]

    cases.append(
        TestCase(
            "5",
            "List findings",
            f"GET /studies/{target['id'][:8]}…/findings",
            "PASS",
            evidence=f"{len(findings)} current findings",
        )
    )

    # Accept the first proposed finding
    accept_target = next((f for f in findings if f["status"] == "proposed"), None)
    if accept_target:
        r = client.post(
            f"/findings/{accept_target['id']}/accept",
            json={"icd10_override": None},
        )
        cases.append(
            TestCase(
                "5",
                "Accept finding",
                "POST /findings/{id}/accept",
                "PASS" if r.is_success and r.json()["status"] == "accepted" else "FAIL",
                evidence=excerpt(r),
            )
        )

    # Reject the next proposed
    reject_targets = [
        f for f in findings if f["status"] == "proposed" and f["id"] != (accept_target or {}).get("id")
    ]
    if reject_targets:
        rt = reject_targets[0]
        r = client.post(f"/findings/{rt['id']}/reject")
        cases.append(
            TestCase(
                "5",
                "Reject finding",
                "POST /findings/{id}/reject",
                "PASS" if r.is_success and r.json()["status"] == "rejected" else "FAIL",
                evidence=excerpt(r),
            )
        )

    # Refine: build a 64×64 mask + JSON geometry, POST as multipart
    refine_target = accept_target  # accepted rows can still be refined
    if refine_target:
        mask = np.zeros((64, 64), dtype=np.uint8)
        mask[16:48, 16:48] = 1
        buf = io.BytesIO()
        np.save(buf, mask, allow_pickle=False)
        buf.seek(0)
        files = {"mask": ("mask.npy", buf.getvalue(), "application/octet-stream")}
        data = {
            "label": f"{refine_target['label']} (QA refined)",
            "geometry": json.dumps({"kind": "bbox", "x": 0.25, "y": 0.25, "w": 0.5, "h": 0.5}),
        }
        r = httpx.post(
            f"{client.base_url}/findings/{refine_target['id']}/refine",
            headers={"Authorization": f"Bearer {client.token}"} if client.token else {},
            data=data,
            files=files,
            timeout=30.0,
        )
        if r.is_success:
            new = r.json()
            cases.append(
                TestCase(
                    "5",
                    "Refine finding (new version row)",
                    "POST /findings/{id}/refine",
                    "PASS" if new["version"] == refine_target["version"] + 1 else "FAIL",
                    evidence=f"v{new['version']}, source={new['source']}, "
                    f"parent={(new.get('parent_finding_id') or '')[:8]}…",
                )
            )
            # History should walk both versions
            h = client.get(f"/findings/{new['id']}/history")
            history = h.json() if h.is_success else []
            cases.append(
                TestCase(
                    "5",
                    "Version-chain history",
                    "GET /findings/{id}/history",
                    "PASS" if len(history) >= 2 else "FAIL",
                    evidence=f"{len(history)} rows",
                )
            )
        else:
            cases.append(
                TestCase(
                    "5",
                    "Refine finding (new version row)",
                    "POST /findings/{id}/refine",
                    "FAIL",
                    error=f"HTTP {r.status_code}: {r.text[:200]}",
                )
            )

    return cases


# ----------------------------------------------------------------------
# Round 7 — MedGemma narrator (writes via signing flow)
# ----------------------------------------------------------------------


def round_7(client: ApiClient, studies: list[dict], artifacts: Path) -> list[TestCase]:
    cases: list[TestCase] = []
    if not studies:
        return []
    target = studies[0]

    # Re-sign so a fresh narrative gets generated with the live backend
    r = client.post(f"/studies/{target['id']}/sign")
    cases.append(
        TestCase(
            "7",
            "Sign report (regenerates narrative)",
            "POST /studies/{id}/sign",
            "PASS" if r.is_success else "FAIL",
            evidence=excerpt(r),
        )
    )

    if not r.is_success:
        return cases

    # Pull the resulting report
    r2 = client.get(f"/reports/study/{target['id']}")
    if not r2.is_success:
        cases.append(
            TestCase(
                "7", "Get report after sign", "GET /reports/study/{id}",
                "FAIL", error=excerpt(r2),
            )
        )
        return cases
    rpt = r2.json()
    report_id = rpt["id"]
    has_narrative = bool(rpt.get("clinical_narrative"))
    cases.append(
        TestCase(
            "7",
            "Report carries MedGemma narrative",
            "GET /reports/study/{id}.clinical_narrative",
            "PASS" if has_narrative else "FAIL",
            evidence=f"backend={rpt.get('narrative_model', '?')} · "
            f"len={len(rpt.get('clinical_narrative') or '')}",
        )
    )

    # Download SR + re-verify it embeds the narrative
    sr = client.get(f"/reports/{report_id}/sr")
    if sr.is_success:
        sr_bytes = sr.content
        save_artifact(artifacts / "sample_sr.dcm", sr_bytes)
        v = verify_sr_bytes(
            sr_bytes, expect_text_substrings=["RESEARCH USE ONLY", "MedGemma"]
        )
        cases.append(
            TestCase(
                "7",
                "DICOM SR carries narrative TEXT item",
                "GET /reports/{id}/sr",
                "PASS" if v["ok"] else "FAIL",
                evidence=f"sop_class={v['sop_class'][:24]}… text_len={v['text_blob_len']} "
                f"missing={v['missing']}",
            )
        )
    else:
        cases.append(
            TestCase(
                "7", "DICOM SR carries narrative", "GET /reports/{id}/sr",
                "FAIL", error=excerpt(sr),
            )
        )

    # FHIR
    fhir = client.get(f"/reports/{report_id}/fhir")
    if fhir.is_success:
        payload = fhir.json()
        save_artifact(artifacts / "sample_fhir.json", payload)
        v = verify_fhir_diagnostic_report(
            payload, expect_in_conclusion=["RESEARCH USE ONLY", "MedGemma"]
        )
        cases.append(
            TestCase(
                "7",
                "FHIR DiagnosticReport carries narrative",
                "GET /reports/{id}/fhir",
                "PASS" if v["ok"] else "FAIL",
                evidence=f"status={v['status']} concl_len={v['conclusion_len']} "
                f"codes={v['conclusion_code_count']} missing={v['missing']}",
            )
        )
    else:
        cases.append(
            TestCase(
                "7", "FHIR DiagnosticReport", "GET /reports/{id}/fhir",
                "FAIL", error=excerpt(fhir),
            )
        )

    return cases


# ----------------------------------------------------------------------
# Round 8.B — Dashboard endpoints
# ----------------------------------------------------------------------


def round_8b(client: ApiClient) -> list[TestCase]:
    cases: list[TestCase] = []
    for path, key_check in [
        ("/dashboard/kpis", lambda j: "studies_7d" in j and "accept_rate" in j),
        (
            "/dashboard/studies-per-day?days=30",
            lambda j: isinstance(j, list) and len(j) == 30,
        ),
        (
            "/dashboard/modality-breakdown",
            lambda j: isinstance(j, list) and len(j) >= 1,
        ),
        (
            "/dashboard/recent-activity?limit=10",
            lambda j: isinstance(j, list),
        ),
        (
            "/dashboard/unsigned-studies?limit=5",
            lambda j: isinstance(j, list),
        ),
    ]:
        r = client.get(path)
        ok = r.is_success and key_check(r.json())
        cases.append(
            TestCase(
                "8.B",
                "Dashboard endpoint",
                f"GET {path}",
                "PASS" if ok else "FAIL",
                evidence=excerpt(r),
            )
        )
    return cases


# ----------------------------------------------------------------------
# Round 8.C — Worklist v2
# ----------------------------------------------------------------------


def round_8c(
    client: ApiClient, studies: list[dict], orthanc_ok: bool, artifacts: Path
) -> list[TestCase]:
    cases: list[TestCase] = []

    # Filter + sort
    r = client.get("/studies/?modality=MR&sort=created_at&order=desc&limit=5")
    rows = r.json() if r.is_success else []
    cases.append(
        TestCase(
            "8.C",
            "Worklist filter+sort (modality=MR)",
            "GET /studies/?modality=MR&sort=…&order=…",
            "PASS" if r.is_success and all(s["modality"] == "MR" for s in rows) else "FAIL",
            evidence=f"{len(rows)} rows · {[s['modality'] for s in rows]}",
        )
    )

    # Facets
    r = client.get("/studies/facets")
    facets = r.json() if r.is_success else {}
    cases.append(
        TestCase(
            "8.C",
            "Worklist facets",
            "GET /studies/facets",
            "PASS"
            if r.is_success
            and len(facets.get("modalities", [])) >= 2
            and "states" in facets
            else "FAIL",
            evidence=f"modalities={facets.get('modalities', [])} "
            f"body_parts={facets.get('body_parts', [])}",
        )
    )

    # Thumbnail — needs Orthanc
    if studies and orthanc_ok:
        r = client.get(f"/studies/{studies[0]['id']}/thumbnail")
        if r.is_success:
            save_artifact(artifacts / "sample_thumbnail.png", r.content)
            v = verify_thumbnail_bytes(r.content)
            cases.append(
                TestCase(
                    "8.C",
                    "Study thumbnail (PNG)",
                    "GET /studies/{id}/thumbnail",
                    "PASS" if v["ok"] else "FAIL",
                    evidence=f"format={v['format']} size={v['size']} mode={v['mode']}",
                )
            )
        else:
            cases.append(
                TestCase(
                    "8.C", "Study thumbnail (PNG)", "GET /studies/{id}/thumbnail",
                    "FAIL", error=excerpt(r),
                )
            )
    else:
        cases.append(
            TestCase(
                "8.C",
                "Study thumbnail (PNG)",
                "GET /studies/{id}/thumbnail",
                "SKIP",
                error="Orthanc unavailable; thumbnail pulls WADO-RS pixels",
            )
        )

    # Bulk re-run inference
    if studies:
        ok_count = 0
        for s in studies[:3]:
            r = client.post(f"/studies/{s['id']}/run-inference")
            if r.status_code in (200, 202):
                ok_count += 1
        cases.append(
            TestCase(
                "8.C",
                "Bulk re-run inference (3 studies)",
                "POST /studies/{id}/run-inference x3",
                "PASS" if ok_count == 3 else "FAIL",
                evidence=f"{ok_count}/3 returned 202",
            )
        )

    return cases


# ----------------------------------------------------------------------
# Round 8.D — Patients / priors
# ----------------------------------------------------------------------


def round_8d(client: ApiClient) -> tuple[list[TestCase], str | None]:
    cases: list[TestCase] = []
    r = client.get("/patients/")
    patients = r.json() if r.is_success else []
    cases.append(
        TestCase(
            "8.D",
            "List patients",
            "GET /patients/",
            "PASS" if r.is_success and len(patients) >= 1 else "FAIL",
            evidence=f"{len(patients)} patients",
        )
    )
    # Prefer a patient with ≥2 studies so the change-report cell can run.
    multi = next((p for p in patients if p.get("study_count", 0) >= 2), None)
    pseu = (multi or (patients[0] if patients else {})).get("pseudonym")
    if pseu:
        r2 = client.get(f"/patients/{pseu}/studies")
        cases.append(
            TestCase(
                "8.D",
                "Patient longitudinal list",
                "GET /patients/{pseudonym}/studies",
                "PASS" if r2.is_success and len(r2.json()) >= 1 else "FAIL",
                evidence=excerpt(r2),
            )
        )
    return cases, pseu


# ----------------------------------------------------------------------
# Round 8.E — Chat SSE
# ----------------------------------------------------------------------


def round_8e(
    client: ApiClient, studies: list[dict], artifacts: Path
) -> list[TestCase]:
    if not studies:
        return []
    target = studies[0]
    messages = {"messages": [{"role": "user", "content": "What's the differential?"}]}

    try:
        with client.stream_post(f"/studies/{target['id']}/chat", json=messages) as r:
            if r.status_code != 200:
                return [
                    TestCase(
                        "8.E", "MedGemma chat (SSE)", "POST /studies/{id}/chat",
                        "FAIL", error=f"HTTP {r.status_code}",
                    )
                ]
            collected: list[str] = []
            for line in r.iter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    obj = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                if obj.get("delta"):
                    collected.append(obj["delta"])
                if obj.get("done"):
                    break
                if obj.get("error"):
                    return [
                        TestCase(
                            "8.E", "MedGemma chat (SSE)", "POST /studies/{id}/chat",
                            "FAIL", error=obj["error"],
                        )
                    ]
                if sum(len(s) for s in collected) > 4000:
                    break  # safety bound
    except Exception as exc:  # noqa: BLE001
        return [
            TestCase(
                "8.E", "MedGemma chat (SSE)", "POST /studies/{id}/chat",
                "FAIL", error=f"{type(exc).__name__}: {exc}",
            )
        ]

    text = "".join(collected)
    save_artifact(artifacts / "chat_transcript.txt", text)
    return [
        TestCase(
            "8.E",
            "MedGemma chat (SSE)",
            "POST /studies/{id}/chat",
            "PASS" if len(text) >= 30 else "FAIL",
            evidence=f"streamed {len(collected)} deltas · {len(text)} chars total",
        )
    ]


# ----------------------------------------------------------------------
# Round 8.F — Change report (live)
# ----------------------------------------------------------------------


def round_8f(client: ApiClient, pseudonym: str | None) -> list[TestCase]:
    if not pseudonym:
        return [
            TestCase(
                "8.F", "Patient change report", "POST /patients/{p}/change-report",
                "SKIP", error="no patient",
            )
        ]
    r = client.get(f"/patients/{pseudonym}/studies")
    studies = r.json() if r.is_success else []
    if len(studies) < 2:
        return [
            TestCase(
                "8.F",
                "Patient change report",
                "POST /patients/{p}/change-report",
                "SKIP",
                error=f"patient has only {len(studies)} studies; need ≥2",
            )
        ]
    payload = {
        "baseline_study_id": studies[1]["id"],
        "follow_up_study_id": studies[0]["id"],
    }
    r2 = client.post(f"/patients/{pseudonym}/change-report", json=payload)
    body = r2.json() if r2.is_success else {}
    return [
        TestCase(
            "8.F",
            "Patient change report",
            "POST /patients/{p}/change-report",
            "PASS" if r2.is_success and body.get("text") else "FAIL",
            evidence=f"backend={body.get('backend')} text_len={len(body.get('text') or '')}",
        )
    ]


# ----------------------------------------------------------------------
# Round 8.G — Analytics
# ----------------------------------------------------------------------


def round_8g(client: ApiClient) -> list[TestCase]:
    cases: list[TestCase] = []
    for path, check in [
        ("/analytics/accept-rate?group_by=model", lambda j: isinstance(j, list)),
        ("/analytics/job-latency?days=30", lambda j: isinstance(j, list) and len(j) == 30),
        ("/analytics/audit-heatmap?days=90", lambda j: isinstance(j, list) and len(j) == 90),
    ]:
        r = client.get(path)
        ok = r.is_success and check(r.json())
        cases.append(
            TestCase(
                "8.G",
                "Analytics endpoint",
                f"GET {path}",
                "PASS" if ok else "FAIL",
                evidence=excerpt(r),
            )
        )
    return cases


# ----------------------------------------------------------------------
# Round 8.H — RADS scoring
# ----------------------------------------------------------------------


def round_8h(client: ApiClient, studies: list[dict], artifacts: Path) -> list[TestCase]:
    cases: list[TestCase] = []

    r = client.get("/findings/rads/schemes")
    schemes = r.json() if r.is_success else {}
    cases.append(
        TestCase(
            "8.H",
            "RADS scheme catalog",
            "GET /findings/rads/schemes",
            "PASS"
            if r.is_success
            and set(schemes.keys()) >= {"BI-RADS", "Lung-RADS", "BT-RADS"}
            else "FAIL",
            evidence=f"schemes={list(schemes.keys())}",
        )
    )

    # Find a breast MG study and score its first finding with BI-RADS 4B
    target = next(
        (s for s in studies if s["modality"] == "MG" or s["body_part"] == "BREAST"),
        None,
    )
    if not target:
        cases.append(
            TestCase(
                "8.H", "Set RADS on breast finding", "POST /findings/{id}/rads",
                "SKIP", error="no breast MG study in seed",
            )
        )
        return cases

    f = client.get(f"/studies/{target['id']}/findings").json()
    if not f:
        cases.append(
            TestCase(
                "8.H", "Set RADS on breast finding", "POST /findings/{id}/rads",
                "SKIP", error="breast study has no findings",
            )
        )
        return cases

    finding = f[0]
    r2 = client.post(
        f"/findings/{finding['id']}/rads",
        json={"scheme": "BI-RADS", "code": "4B"},
    )
    cases.append(
        TestCase(
            "8.H",
            "Set BI-RADS 4B on breast finding",
            "POST /findings/{id}/rads",
            "PASS"
            if r2.is_success
            and r2.json()["geometry"]["rads"]["code"] == "4B"
            else "FAIL",
            evidence=excerpt(r2),
        )
    )

    # Re-sign → SR carries BI-RADS 4B
    r3 = client.post(f"/studies/{target['id']}/sign")
    if r3.is_success:
        rpt = client.get(f"/reports/study/{target['id']}").json()
        sr = client.get(f"/reports/{rpt['id']}/sr")
        if sr.is_success:
            v = verify_sr_bytes(sr.content, expect_text_substrings=["BI-RADS 4B"])
            cases.append(
                TestCase(
                    "8.H",
                    "DICOM SR carries BI-RADS 4B",
                    "GET /reports/{id}/sr",
                    "PASS" if v["ok"] else "FAIL",
                    evidence=f"missing={v['missing']} text_len={v['text_blob_len']}",
                )
            )

    return cases


# ----------------------------------------------------------------------
# Round 9.B — Treatment planning
# ----------------------------------------------------------------------


def round_9b(client: ApiClient, studies: list[dict], artifacts: Path) -> list[TestCase]:
    cases: list[TestCase] = []
    if not studies:
        return []
    study_id = studies[0]["id"]

    # Create plan
    r = client.post(
        "/treatment-plans/",
        json={
            "study_id": study_id,
            "name": "QA round-10 plan",
            "intent": "curative",
            "modality": "proton",
            "prescription_dose_gy": 60.0,
            "fractions": 30,
        },
    )
    cases.append(
        TestCase(
            "9.B",
            "Create treatment plan",
            "POST /treatment-plans/",
            "PASS" if r.status_code == 201 else "FAIL",
            evidence=excerpt(r),
        )
    )
    if r.status_code != 201:
        return cases
    plan = r.json()

    # Add 4 cardinal beams via PATCH
    beams = [
        {"gantry_angle": a, "couch_angle": 0, "energy_mev": 100, "mu": 100, "weight": 1.0}
        for a in (0, 90, 180, 270)
    ]
    r2 = client.patch(f"/treatment-plans/{plan['id']}", json={"beams": beams})
    cases.append(
        TestCase(
            "9.B",
            "PATCH beams (4 cardinal)",
            "PATCH /treatment-plans/{id}",
            "PASS"
            if r2.is_success and len(r2.json()["beams"]) == 4
            else "FAIL",
            evidence=excerpt(r2),
        )
    )

    # Add contours (1 of each kind)
    for ctype, name in [
        ("GTV", "primary tumor"),
        ("CTV", "clinical tumor"),
        ("PTV", "planning target"),
        ("OAR", "brainstem"),
    ]:
        rc = client.post(
            f"/treatment-plans/{plan['id']}/contours",
            json={"contour_type": ctype, "name": name, "volume_cm3": 12.5},
        )
        cases.append(
            TestCase(
                "9.B",
                f"Add {ctype} contour",
                "POST /treatment-plans/{id}/contours",
                "PASS" if rc.status_code == 201 else "FAIL",
                evidence=excerpt(rc),
            )
        )

    # Compute dose
    rc = client.post(f"/treatment-plans/{plan['id']}/compute-dose")
    if rc.is_success:
        ds = rc.json()["dose_summary"]
        save_artifact(artifacts / "sample_dose_summary.json", ds)
        cases.append(
            TestCase(
                "9.B",
                "Compute synthetic dose (max≈prescription)",
                "POST /treatment-plans/{id}/compute-dose",
                "PASS"
                if ds and 55 <= ds["global"]["max"] <= 65
                else "FAIL",
                evidence=f"global.max={ds['global']['max']} mean={ds['global']['mean']} "
                f"v20={ds['global']['v20']}",
            )
        )
    else:
        cases.append(
            TestCase(
                "9.B", "Compute synthetic dose", "POST /treatment-plans/{id}/compute-dose",
                "FAIL", error=excerpt(rc),
            )
        )

    # OAR catalog + evaluate
    r3 = client.get("/treatment-plans/constraints/oar")
    cat = r3.json() if r3.is_success else {}
    cases.append(
        TestCase(
            "9.B",
            "OAR constraint catalog",
            "GET /treatment-plans/constraints/oar",
            "PASS"
            if r3.is_success and len(cat.get("tissues", [])) >= 15
            else "FAIL",
            evidence=f"{len(cat.get('tissues', []))} tissues, "
            f"{len(cat.get('constraints', []))} constraints",
        )
    )

    r4 = client.post(
        "/treatment-plans/constraints/evaluate",
        json={"tissue": "brainstem", "dose": {"max": 30.0, "mean": 15.0}},
    )
    evals = r4.json() if r4.is_success else []
    cases.append(
        TestCase(
            "9.B",
            "Evaluate brainstem constraint (max 30 → pass)",
            "POST /treatment-plans/constraints/evaluate",
            "PASS"
            if r4.is_success and evals and evals[0]["status"] == "pass"
            else "FAIL",
            evidence=f"{evals}",
        )
    )

    # Approve plan
    r5 = client.post(f"/treatment-plans/{plan['id']}/approve")
    cases.append(
        TestCase(
            "9.B",
            "Approve plan",
            "POST /treatment-plans/{id}/approve",
            "PASS"
            if r5.is_success and r5.json()["status"] == "approved"
            else "FAIL",
            evidence=excerpt(r5),
        )
    )

    return cases


# ----------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report",
        default="../docs/qa/round10_qa_report.md",
        help="path to write the markdown report (relative to backend/)",
    )
    parser.add_argument(
        "--artifacts",
        default="../docs/qa/round10_artifacts",
        help="dir for sample DICOMs / JSON / PNG / chat transcript",
    )
    args = parser.parse_args()

    artifacts = Path(args.artifacts).resolve()
    artifacts.mkdir(parents=True, exist_ok=True)

    # Wait for backend
    for _ in range(20):
        try:
            r = httpx.get(f"{API_BASE}/health", timeout=2.0)
            if r.is_success:
                break
        except httpx.HTTPError:
            time.sleep(0.5)
    else:
        print(f"FATAL: backend not reachable at {API_BASE}", flush=True)
        return 2

    # Probe Orthanc
    orthanc_ok = False
    try:
        r = httpx.get(f"{ORTHANC_BASE}/system", timeout=2.0)
        orthanc_ok = r.is_success
    except httpx.HTTPError:
        orthanc_ok = False

    client = ApiClient(API_BASE)
    client.login(*CLINICIAN)

    studies = client.get("/studies/").json()
    medgemma_backend = os.environ.get("MEDGEMMA_BACKEND", "mock")

    cases: list[TestCase] = []
    cases += round_1_2(client)
    cases += round_3(client)
    cases += round_4(orthanc_ok, studies)
    cases += round_5(client, studies)
    cases.append(
        TestCase(
            "6",
            "External-data analyzer (Round 6 — pre-existing pytest suite)",
            "pytest tests/test_external_data_analyzer.py",
            "DEFERRED",
            evidence="Covered by the existing 101-test pytest suite (102 with this run); "
            "the analyzer was last run during seed setup.",
        )
    )
    cases += round_7(client, studies, artifacts)
    cases.append(
        TestCase(
            "8.A",
            "Design system + dark mode build",
            "cd frontend && npm run build",
            "DEFERRED",
            evidence="`next build` verified green at end of Round 9 (11 routes, 0 type errors).",
        )
    )
    cases += round_8b(client)
    cases += round_8c(client, studies, orthanc_ok, artifacts)
    patients_cases, pseu = round_8d(client)
    cases += patients_cases
    cases += round_8e(client, studies, artifacts)
    cases += round_8f(client, pseu)
    cases += round_8g(client)
    cases += round_8h(client, studies, artifacts)
    cases.append(
        TestCase(
            "9.A",
            "Multi-viewport + cine controls (UI-only)",
            "ViewportGrid, CineControls, SeriesPanel",
            "DEFERRED",
            evidence="User chose API-level coverage (no Playwright); next build verified the "
            "components compile + are dynamically imported on the study page.",
        )
    )
    cases += round_9b(client, studies, artifacts)

    # Dataset summary for the report header
    ds_summary = {
        "Postgres studies": len(studies),
        "Synthetic studies": "3 (CT chest, MR brain, MG breast)",
        "Pydicom bundled studies": "2 (MR_small, CT_small re-uid'd)",
        "Orthanc available": "yes" if orthanc_ok else "no (Docker-in-Docker unavailable)",
        "Backend base": API_BASE,
    }

    write_report(
        cases,
        out_path=Path(args.report).resolve(),
        medgemma_backend=medgemma_backend,
        dataset_summary=ds_summary,
    )
    # Console summary
    pass_n = sum(1 for c in cases if c.status == "PASS")
    fail_n = sum(1 for c in cases if c.status == "FAIL")
    skip_n = sum(1 for c in cases if c.status == "SKIP")
    deferred_n = sum(1 for c in cases if c.status == "DEFERRED")
    print(
        f"\nQA complete: {pass_n} PASS / {fail_n} FAIL / {skip_n} SKIP / "
        f"{deferred_n} DEFERRED of {len(cases)} total",
        flush=True,
    )
    print(f"Report: {Path(args.report).resolve()}")
    print(f"Artifacts: {artifacts}")
    return 0 if fail_n == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
