# Round 10 — Real-data QA report

**Generated**: 2026-05-17T04:12:33+00:00  
**Git SHA**: `46a6171`  
**MedGemma backend**: `hf`  
**Result**: 40 PASS / 0 FAIL / 2 SKIP / 3 DEFERRED — 45 total

## Dataset summary

- **Postgres studies**: 5
- **Synthetic studies**: 3 (CT chest, MR brain, MG breast)
- **Pydicom bundled studies**: 2 (MR_small, CT_small re-uid'd)
- **Orthanc available**: no (Docker-in-Docker unavailable)
- **Backend base**: http://localhost:8000/api/v1

## Coverage matrix

| Round | Feature | Endpoint / call | Status | Evidence |
|---|---|---|---|---|
| 1-2 | List studies (real seed) | `GET /studies/` | ✅ PASS | 200 · list len=5 · first={"id": "9ab194dd-2de3-4225-80d7-13fd9747ad2f", "study_instance_uid": "1.2.826.0.1.3680043.8.498.790833669144712664364489 · 5 rows |
| 1-2 | Get one study (returns de-id pseudonym) | `GET /studies/{id}` | ✅ PASS | pseudonym=9c7202376188… |
| 3 | ICD-10 search returns breast codes | `GET /icd10/search?q=breast` | ✅ PASS | 200 · list len=25 · first={"code": "C50.011", "description": "Malignant neoplasm of nipple and areola right female breast", "category": "malignant · breast codes: ['C50.011', 'C50.012', 'C50.019', 'C50.111', 'C50.112'] |
| 4 | DICOMweb proxy (QIDO series) | `GET /dicom-web/studies/{uid}/series` | ⚠️ SKIP |  |
| 5 | List findings | `GET /studies/9ab194dd…/findings` | ✅ PASS | 5 current findings |
| 5 | Accept finding | `POST /findings/{id}/accept` | ✅ PASS | 200 · keys=['id', 'study_id', 'parent_finding_id', 'version', 'is_current', 'source'] |
| 5 | Reject finding | `POST /findings/{id}/reject` | ✅ PASS | 200 · keys=['id', 'study_id', 'parent_finding_id', 'version', 'is_current', 'source'] |
| 5 | Refine finding (new version row) | `POST /findings/{id}/refine` | ✅ PASS | v2, source=radiologist, parent=617555ab… |
| 5 | Version-chain history | `GET /findings/{id}/history` | ✅ PASS | 2 rows |
| 6 | External-data analyzer (Round 6 — pre-existing pytest suite) | `pytest tests/test_external_data_analyzer.py` | 🔒 DEFERRED | Covered by the existing 101-test pytest suite (102 with this run); the analyzer was last run during seed setup. |
| 7 | Sign report (regenerates narrative) | `POST /studies/{id}/sign` | ✅ PASS | 200 · keys=['report_id', 'signed_at'] |
| 7 | Report carries MedGemma narrative | `GET /reports/study/{id}.clinical_narrative` | ✅ PASS | backend=MedGemmaNarrator/hf:google/medgemma-27b-text-it · len=383 |
| 7 | DICOM SR carries narrative TEXT item | `GET /reports/{id}/sr` | ✅ PASS | sop_class=1.2.840.10008.5.1.4.1.1.… text_len=1169 missing=[] |
| 7 | FHIR DiagnosticReport carries narrative | `GET /reports/{id}/fhir` | ✅ PASS | status=preliminary concl_len=849 codes=1 missing=[] |
| 8.A | Design system + dark mode build | `cd frontend && npm run build` | 🔒 DEFERRED | `next build` verified green at end of Round 9 (11 routes, 0 type errors). |
| 8.B | Dashboard endpoint | `GET /dashboard/kpis` | ✅ PASS | 200 · keys=['studies_7d', 'signed_reports', 'mean_latency_ms', 'accept_rate', 'reviewed_findings'] |
| 8.B | Dashboard endpoint | `GET /dashboard/studies-per-day?days=30` | ✅ PASS | 200 · list len=30 · first={"date": "2026-04-18", "count": 0} |
| 8.B | Dashboard endpoint | `GET /dashboard/modality-breakdown` | ✅ PASS | 200 · list len=3 · first={"modality": "CT", "count": 2} |
| 8.B | Dashboard endpoint | `GET /dashboard/recent-activity?limit=10` | ✅ PASS | 200 · list len=10 · first={"id": "8d0b7e51-5d40-4430-a306-2864e24ef61f", "created_at": "2026-05-17T04:12:22.491637+00:00", "action": "dashboard.kp |
| 8.B | Dashboard endpoint | `GET /dashboard/unsigned-studies?limit=5` | ✅ PASS | 200 · list len=3 · first={"id": "fd739845-5c30-406b-8a4a-dec36235876a", "description": "", "modality": "MR", "body_part": "BRAIN", "state": "repo |
| 8.C | Worklist filter+sort (modality=MR) | `GET /studies/?modality=MR&sort=…&order=…` | ✅ PASS | 2 rows · ['MR', 'MR'] |
| 8.C | Worklist facets | `GET /studies/facets` | ✅ PASS | modalities=['CT', 'MG', 'MR'] body_parts=['BRAIN', 'BREAST', 'CHEST'] |
| 8.C | Study thumbnail (PNG) | `GET /studies/{id}/thumbnail` | ⚠️ SKIP |  |
| 8.C | Bulk re-run inference (3 studies) | `POST /studies/{id}/run-inference x3` | ✅ PASS | 3/3 returned 202 |
| 8.D | List patients | `GET /patients/` | ✅ PASS | 4 patients |
| 8.D | Patient longitudinal list | `GET /patients/{pseudonym}/studies` | ✅ PASS | 200 · list len=2 · first={"id": "77a70008-4190-4b61-a101-5916142ad0c3", "study_instance_uid": "1.2.826.0.1.3680043.8.498.762651248216224308801462 |
| 8.E | MedGemma chat (SSE) | `POST /studies/{id}/chat` | ✅ PASS | streamed 13 deltas · 87 chars total |
| 8.F | Patient change report | `POST /patients/{p}/change-report` | ✅ PASS | backend=hf text_len=546 |
| 8.G | Analytics endpoint | `GET /analytics/accept-rate?group_by=model` | ✅ PASS | 200 · list len=1 · first={"group": "MockModel", "accepted": 4, "rejected": 4, "modified": 0, "proposed": 26, "total": 34} |
| 8.G | Analytics endpoint | `GET /analytics/job-latency?days=30` | ✅ PASS | 200 · list len=30 · first={"date": "2026-04-18", "mean_ms": 0.0, "count": 0} |
| 8.G | Analytics endpoint | `GET /analytics/audit-heatmap?days=90` | ✅ PASS | 200 · list len=90 · first={"date": "2026-02-17", "count": 0} |
| 8.H | RADS scheme catalog | `GET /findings/rads/schemes` | ✅ PASS | schemes=['BI-RADS', 'Lung-RADS', 'BT-RADS'] |
| 8.H | Set BI-RADS 4B on breast finding | `POST /findings/{id}/rads` | ✅ PASS | 200 · keys=['id', 'study_id', 'parent_finding_id', 'version', 'is_current', 'source'] |
| 8.H | DICOM SR carries BI-RADS 4B | `GET /reports/{id}/sr` | ✅ PASS | missing=[] text_len=2539 |
| 9.A | Multi-viewport + cine controls (UI-only) | `ViewportGrid, CineControls, SeriesPanel` | 🔒 DEFERRED | User chose API-level coverage (no Playwright); next build verified the components compile + are dynamically imported on the study page. |
| 9.B | Create treatment plan | `POST /treatment-plans/` | ✅ PASS | 201 · keys=['id', 'study_id', 'name', 'intent', 'modality', 'prescription_dose_gy'] |
| 9.B | PATCH beams (4 cardinal) | `PATCH /treatment-plans/{id}` | ✅ PASS | 200 · keys=['id', 'study_id', 'name', 'intent', 'modality', 'prescription_dose_gy'] |
| 9.B | Add GTV contour | `POST /treatment-plans/{id}/contours` | ✅ PASS | 201 · keys=['id', 'study_id', 'plan_id', 'contour_type', 'name', 'color'] |
| 9.B | Add CTV contour | `POST /treatment-plans/{id}/contours` | ✅ PASS | 201 · keys=['id', 'study_id', 'plan_id', 'contour_type', 'name', 'color'] |
| 9.B | Add PTV contour | `POST /treatment-plans/{id}/contours` | ✅ PASS | 201 · keys=['id', 'study_id', 'plan_id', 'contour_type', 'name', 'color'] |
| 9.B | Add OAR contour | `POST /treatment-plans/{id}/contours` | ✅ PASS | 201 · keys=['id', 'study_id', 'plan_id', 'contour_type', 'name', 'color'] |
| 9.B | Compute synthetic dose (max≈prescription) | `POST /treatment-plans/{id}/compute-dose` | ✅ PASS | global.max=60.0 mean=2.92 v20=0.04 |
| 9.B | OAR constraint catalog | `GET /treatment-plans/constraints/oar` | ✅ PASS | 23 tissues, 24 constraints |
| 9.B | Evaluate brainstem constraint (max 30 → pass) | `POST /treatment-plans/constraints/evaluate` | ✅ PASS | [{'tissue': 'brainstem', 'metric': 'max', 'limit_gy': 54.0, 'observed': 30.0, 'status': 'pass', 'rationale': 'Max dose to brainstem ≤54 Gy', 'source': 'QUANTEC'}] |
| 9.B | Approve plan | `POST /treatment-plans/{id}/approve` | ✅ PASS | 200 · keys=['id', 'study_id', 'name', 'intent', 'modality', 'prescription_dose_gy'] |

## Skipped — reasons

- **4 · DICOMweb proxy (QIDO series)**: Orthanc not running in this environment (Docker-in-Docker unavailable). WADO/QIDO paths are exercised by docker-compose smoke; the proxy code itself is unchanged since Round 1.
- **8.C · Study thumbnail (PNG)**: Orthanc unavailable; thumbnail pulls WADO-RS pixels
