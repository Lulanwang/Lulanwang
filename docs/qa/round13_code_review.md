# Round 13 — Full code review + hardening, and Aidoc comparison

## Context

The user asked for a full-codebase review: confirm every button is functional as labelled, harden the pipeline, and benchmark the app against Aidoc's radiology-AI offering. Two review passes were run (backend pipeline/API, frontend buttons/wiring), the real issues were fixed, and the test suites were re-run to prove no regressions.

## Method

* **Backend review** — traced the study lifecycle (`study_pipeline.py`, `twin/pipeline.py`, `workers/background.py`), audited all 17 routers under `app/api/v1/`, de-identification, auth, and audit logging.
* **Frontend review** — inventoried every button/link/toggle/form across all 10 pages + components, cross-checked every `api.*` call against a backend endpoint, verified viewer-tool registration.
* **Dynamic verification** — `pytest` (full suite), `next build` (type-level button↔API check), and the Playwright button suite against the live stack (Postgres + Orthanc + uvicorn + Next).

## Frontend verdict: clean

**No dead buttons, no 404-bound calls.** Every interactive control across dashboard, worklist, study viewer, plan, twin, patients, timeline, analytics, audit, and login is wired to a real handler; every `api.*` method (and the one direct chat `fetch`) resolves to an existing backend route; all 9 Cornerstone tools are registered in the tool group; loading/empty/error states are handled; forms validate → call → toast → refresh.

Cosmetic notes only (not fixed — harmless): an unreachable `/studies/[studyUid]/viewer` placeholder route (the real viewer is the index page), two unused `Layout` union members (`2x1`, `1x3`), and a documented no-op effect in `FilterSidebar`.

## Backend findings + fixes

| ID | Severity | Issue | Fix |
|----|----------|-------|-----|
| C1 | **Critical** | `deidentify()` stripped only a hardcoded tag list — never `remove_private_tags()` and never the overlay/curve repeating groups, despite the docstring claiming PS3.15 Annex E Basic Profile. Vendor private blocks and overlay planes are routine PHI vectors → **real leak on every ingest**. | Added `ds.remove_private_tags()` + `_remove_repeating_groups()` (deletes groups `0x5000-0x50FF` and `0x6000-0x60FF`). New regression test `test_private_tags_and_overlays_removed`. |
| C2 | **Critical** | In `run_inference`, `generate_report()` ran **inside** the inference `try`. A report-draft error (disk, SR/FHIR builder) overwrote the just-committed `succeeded`/`inferred` state with `failed` — a successful inference reported as failed. | Moved `generate_report` outside the inference `try` into its own `try/except` that logs + rolls back but never regresses study/job state. Study stays `inferred`; Sign generates the report on demand. |
| H1 | **High** | `POST /studies/{id}/sign` had no role gate and no state guard — any authenticated user could force-sign a `failed`/`inferring`/already-`signed` study. Signing is the legal attestation step. | Gated with `require_role("clinician","admin")` + a state precondition (`409` unless `inferred`/`reported`). Frontend Sign button now disables + relabels to "Signed" once signed. |
| H2 | **High** | Clinical-decision write endpoints used bare `current_user` — a non-clinical role could accept/reject AI findings, set RADS, or approve a plan. | Gated `accept_finding`, `reject_finding`, `refine_finding`, `set_rads`, and `approve_plan` with `require_role("clinician","admin")`. Unit-tested via `test_authz.py`. |
| M1 | **Medium** | Crash recovery reset only `running` jobs/twins; a row stuck in `queued` (in-process BackgroundTask dropped before it started) stayed queued forever with a permanent UI spinner. | `recover_orphaned_jobs` now sweeps `running` **and** `queued` for both `jobs` and `organ_twins`. |

### Verified sound (no change needed)
* The `Study.state` machine has a single writer and consistent transitions; both BackgroundTask entry points catch all exceptions — no uncaught `raise` escapes a task.
* Audit logging **is** written on every PHI-access path (study view/list, report view/export, every DICOMweb QIDO/WADO/STOW, chat, login).
* No bare `except:`/`except Exception: pass` that swallow real errors (the two `pass` cases are deliberate fail-soft cache writes).
* Idempotency holds (patient/study by pseudonym/UID; twin by `(study, seg_config_version)` with a matching DB unique constraint).

### Known, intentional MVP gaps (documented, not fixed)
* `run_inference` passes an empty dataset list to the model — only `MockModel` (the default) tolerates this. The real MONAI adapters are stubs. This is the core "not FDA-cleared" boundary the README is explicit about.
* The SR is written to disk but not STOW'd back to Orthanc (`store_sr_file`/`qido_studies` are unused helpers). The SR is still downloadable via `/reports/{id}/sr`; PACS-round-trip is a future wiring task.
* `refine_finding` writes the NumPy-fallback SEG (empty source datasets) rather than a fully-referenced DICOM SEG.

## Test posture after hardening

* `pytest -q` → **117 passed / 1 skipped** (was 112; +5 tests: 1 de-id PHI-leak, 4 authz).
* `next build` → clean, 13 routes, 0 type errors.
* Playwright study + plan + twin specs → **29 passed / 1 skipped** against the live stack, including accept/reject/sign as a clinician through the new gates and the state-aware Sign button.
* De-id smoke on real `CT_small`/`MR_small`: private + overlay tags fully stripped, pseudonymization intact, no crash.

## Aidoc comparison (honest)

Aidoc's value is a broad catalogue of **FDA-cleared / CE-marked** triage + detection + quantification algorithms running at clinical scale with deep PACS/EHR/reporting integration and a unified care-team widget.

| Capability | This app | Aidoc |
|---|---|---|
| De-identification (PS3.15 Annex E) | ✅ Basic Profile + Clean Descriptors + date-shift, now incl. private/overlay stripping | handled by site infra |
| PACS / DICOMweb | ✅ Orthanc + authenticated QIDO/WADO/STOW proxy | ✅ deep PACS integration |
| AI findings + coding | ✅ findings → ICD-10, versioned, radiologist accept/reject/refine | ✅ FDA-cleared detection |
| Structured output | ✅ DICOM SR (TID 1500) + FHIR DiagnosticReport | ✅ reporting integration |
| Worklist / dashboard / analytics | ✅ filters, KPIs, accept-rate, latency, audit heatmap | ✅ unified widget |
| RADS scoring | ✅ BI-RADS / Lung-RADS / BT-RADS | partial |
| LLM narrative + chat | ✅ MedGemma narrative, chat, change report | not a focus |
| Treatment planning | ✅ research-only synthetic-dose workspace | ✗ |
| **3D digital twin** | ✅ organ mesh reconstruction from DICOM | ✗ |
| Audit / HIPAA technical safeguards | ✅ append-only audit on every PHI touch | ✅ enterprise |
| **FDA-cleared clinical algorithms** | ✗ MockModel by default; explicitly research-only | ✅ core strength |

**Assessment:** on workflow *breadth* the app meets or exceeds Aidoc in several areas (treatment planning, 3D twin, and LLM narratives are beyond Aidoc's scope), and the surrounding scaffolding — de-id, PACS, audit, SR/FHIR, worklist, RADS — is genuinely comparable. The one capability an MVP cannot match is Aidoc's regulatory core: validated, FDA-cleared detection algorithms. That gap is the `MockModel` placeholder and is called out unambiguously in the product's own "research use only — not FDA cleared" framing. To close it, the registered MONAI adapters would need real weights, clinical validation, and a 510(k) pathway — none of which is a code change.
