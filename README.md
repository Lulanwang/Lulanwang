# Lulan DICOM Analysis MVP

> **RESEARCH USE ONLY — NOT A MEDICAL DEVICE.**
> Not FDA cleared, not CE marked. Outputs must not be used for diagnosis,
> treatment, or clinical decision-making. All AI findings are unverified
> and require licensed-radiologist review before any clinical action.
>
> This repository is an MVP that demonstrates a clinical-grade *architecture*
> for DICOM analysis — HIPAA technical safeguards, DICOM PS3.15 Annex E
> de-identification, audit logging, ICD-10 coding, DICOM SR + FHIR
> reporting — but it has not been clinically validated and is not a
> substitute for a regulated, cleared medical device.

End-to-end imaging analysis MVP for brain, lung, and breast cancer
workflows. Ingests DICOM studies (X-ray, CT, MRI), de-identifies them,
stores them in an Orthanc PACS, runs AI inference, suggests ICD-10
codes, and exports DICOM SR + FHIR DiagnosticReport.

## Quick start

```bash
cp .env.example .env
docker compose up --build
# wait for all containers to report healthy, then:
make seed
```

Open <http://localhost> and sign in with the demo credentials printed
by `make seed`. The worklist will show the seeded studies.

## What's in the box

- **PACS**: Orthanc with DICOMweb + Postgres plugins
- **Backend**: FastAPI + pydicom + MONAI (mock inference by default)
- **Frontend**: Next.js 15 + OHIF Viewer (embedded) + shadcn/ui
- **DB**: Postgres 16 (one container, two DBs: `app` + `orthanc`)
- **Proxy**: Caddy single-origin (fixes CORS + mixed-content for OHIF)
- **De-identification**: pydicom-based, DICOM PS3.15 Annex E Basic Profile
- **ICD-10**: curated cancer-relevant subset (C50.x, C34.x, C71.x, etc.)
- **Reporting**: DICOM SR (TID 1500) + FHIR DiagnosticReport JSON
- **Audit**: append-only `audit_events` table, every PHI access logged

## Switching from mock to real AI

Mock inference is on by default so you can demo the pipeline without
GPUs or model downloads.

```bash
# Download MONAI bundles (~1.5 GB total, brain + lung)
make seed-models
# Edit .env: MOCK_INFERENCE=false
docker compose restart backend
```

Breast mammography has no clean open-weights model, so it stays on
the `MockModel` even when real inference is enabled. See `MODEL_CARDS.md`.

## Testing against external DICOM data

```bash
make analyze-external           # in docker
# or locally:
python -m seed.analyze_external_data --out /tmp/lulan-analysis
```

This pulls DICOMs from three sources and runs them through the
parse → de-id → route → infer → ICD-10 chain:

| Source | Files | Notes |
| --- | ---: | --- |
| `pydicom` (bundled) | 80 | CT/MR/CR/US/SEG/RTPLAN fixtures |
| `pydicom/pydicom-data` (GitHub, on-demand) | 21 | Brain MR variants across 5 transfer syntaxes |
| `UniqueData/dicom-brain-dataset` (HF) | 8 | Real anonymized brain MRI series |
| `ndonyapour/dicom-sample-files` (HF) | 40 | Chest CT series + MR hippocampal study |

Latest run: **149 files, 128 de-identified, 53 routed to a model** —
producing brain-tumour findings (ICD-10 `C71.9`, `G93.6`) on 33 real
brain MRs and lung-nodule findings (`C34.11`, `R91.1`) on 20 real chest
CT slices. Report committed at `docs/analysis/external_data_report.md`.

## Compliance posture

See **[COMPLIANCE.md](./COMPLIANCE.md)** for the HIPAA Security Rule
mapping (§164.308/310/312), the DICOM de-identification profile, and
the gap list between this MVP and a production deployment.

**Production deployment requires** a signed BAA with every infra
provider, encryption-at-rest review, KMS-backed key management, MFA
enforcement, an organizational HIPAA risk analysis per 45 CFR
164.308(a)(1)(ii)(A), and — for clinical use — FDA clearance, IRB
approval, and a documented Quality Management System.

## Roadmap (out of MVP scope)

KMS/HSM key management · MFA enforcement · WORM/signed audit log ·
FDA QMS process · clinical validation · IRB pipeline · multi-tenant
org isolation · MPR/fusion viewer tools · DICOM-TLS for DIMSE · full
ICD-10-CM ingestion · SNOMED-CT mapping · Epic/Cerner integration.

## Repo layout

```
backend/   FastAPI service + AI adapters + DICOM/FHIR/SR + Alembic
frontend/  Next.js 15 app + OHIF viewer route
infra/     orthanc.json, postgres init, caddy config
data/      curated ICD-10 cancer codes CSV
docs/      architecture notes
docker-compose.yml + Caddyfile + Makefile + .env.example
```

## License

MIT for code. Model weights downloaded by `make seed-models` carry
their own licenses — see `MODEL_CARDS.md`.
