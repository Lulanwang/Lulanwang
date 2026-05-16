# Compliance posture

> This document describes how the MVP **implements** HIPAA technical
> safeguards in code, and what is **explicitly out of scope** and must
> be addressed organizationally before any production / clinical use.

## 1. HIPAA Security Rule — implemented controls

Mapped to 45 CFR Part 164 Subpart C.

### §164.312(a) — Access Control

| Requirement | Implementation | File |
| --- | --- | --- |
| (1) Unique user identification | Per-user accounts, bcrypt-hashed passwords, JWT subject = user UUID | `backend/app/core/security.py`, `backend/app/db/models/user.py` |
| (2)(i) Emergency access procedure | `admin` role can re-issue clinician credentials; documented in runbook | `backend/app/api/v1/auth.py` |
| (2)(ii) Automatic logoff | JWT TTL 30 min; frontend redirects on 401 | `backend/app/core/security.py` |
| (2)(iii) Encryption / decryption | TLS at the edge (Caddy auto-TLS); Postgres + Orthanc volumes on encrypted host FS in prod (out of MVP — see gaps) | `Caddyfile` |

### §164.312(b) — Audit Controls

| Requirement | Implementation | File |
| --- | --- | --- |
| Hardware/software/procedural mechanisms recording PHI access | `audit_events` append-only table; middleware logs every authenticated request; DICOMweb proxy logs every WADO/QIDO/STOW pull with study UID + actor + timestamp + request ID | `backend/app/core/audit.py`, `backend/app/api/v1/dicomweb_proxy.py` |

### §164.312(c) — Integrity

| Requirement | Implementation | File |
| --- | --- | --- |
| Mechanism to authenticate ePHI (not improperly altered/destroyed) | SHA-256 of each ingested instance recorded in `instances.sha256`; verified on retrieve | `backend/app/dicom/parse.py` |

### §164.312(d) — Person or Entity Authentication

| Requirement | Implementation | File |
| --- | --- | --- |
| Verify identity of person seeking access | Password + JWT; `mfa_secret` column reserved for TOTP (not enforced in MVP) | `backend/app/db/models/user.py` |

### §164.312(e) — Transmission Security

| Requirement | Implementation | File |
| --- | --- | --- |
| (1) Integrity controls | TLS at edge | `Caddyfile` |
| (2) Encryption | HTTPS via Caddy auto-TLS for any real hostname; localhost demo is HTTP only | `Caddyfile` |

## 2. DICOM de-identification

Implements **DICOM PS3.15 Annex E — Basic Application Level
Confidentiality Profile** (a.k.a. NEMA Sup 142), with these options:

- **Basic Profile** (mandatory): all listed tags removed/replaced
- **Clean Descriptors Option**: study/series/image description fields scrubbed
- **Retain Longitudinal Temporal Information with Modified Dates Option**: date-shift per patient (preserves intervals)

Code: `backend/app/dicom/deidentify.py`.

Burned-in pixel PHI: tags `BurnedInAnnotation=YES`,
`RecognizableVisualFeatures=YES`, or modality `SC`/`OT` will **block
ingestion** and surface a manual-QA warning. The MVP does NOT perform
OCR-based pixel redaction.

## 3. ICD-10 coding

Bundled CSV under `data/icd10/cancer_codes.csv` covers brain (C71.x,
D33.x), lung (C34.x, D14.3x, R91.x), breast (C50.x, D24.x, N63), plus
the unspecified and "uncertain behavior" adjuncts most likely to be
used in oncology reporting. Full ICD-10-CM ingestion is on the roadmap.

## 4. Audit log

`audit_events`: append-only at the application layer (no UPDATE/DELETE
endpoints; no ORM exposure for mutation). A database trigger enforcing
this is documented in `infra/postgres/init.sql` as a TODO for
production. Each row: `actor_id`, `actor_role`, `action`,
`resource_type`, `resource_id`, `request_id`, `ip`, `user_agent`,
`created_at`, optional `details` (JSONB).

## 5. Gaps — must be closed before production / clinical use

| Gap | Owner | Notes |
| --- | --- | --- |
| KMS-backed key management | Infra | Use AWS KMS / GCP KMS / Vault; rotate; envelope-encrypt DB + object store |
| MFA enforcement | Product + Backend | TOTP column is reserved; enforce in `auth.py` |
| WORM / signed audit log | Backend + Infra | Either DB trigger blocking mutations + nightly hash chain, or ship to immutable object store (S3 Object Lock) |
| Encryption at rest review | Infra | LUKS / EBS-encrypted volumes for Postgres + Orthanc storage |
| BAA coverage | Legal | Signed BAA with every infra provider (cloud, monitoring, email, SMS, etc.) |
| HIPAA risk analysis | Compliance | Per 45 CFR 164.308(a)(1)(ii)(A); annual cadence |
| FDA clearance for AI outputs | Regulatory | 510(k) or De Novo for any AI/CAD claim; until then, "Research Use Only" must remain on all surfaces |
| Clinical validation | Clinical Affairs | Per-indication validation on a held-out, multi-site dataset; performance bounds documented |
| IRB approval for any prospective data | Research | If collecting/using real patient data for model improvement |
| DICOM-TLS for DIMSE | Infra | If exposing any C-STORE/C-MOVE listener outside the cluster |
| Multi-tenant org isolation | Backend | Row-level security per organization |
| Penetration test | Security | Annual minimum |
| SOC 2 Type II | Compliance | Audit artifact; out of scope for the code MVP |
| Third-party LLM data egress (MedGemma) | Legal + Infra | Default `MEDGEMMA_BACKEND=mock` has no egress. When `MEDGEMMA_BACKEND=hf`, AI-generated finding labels + ICD-10 suggestions + study modality/body-part are sent to a Hugging Face Inference Endpoint. **No raw PHI / pixel data is sent** (Findings carry AI-derived semantic content only; the pipeline strips direct identifiers before pseudonymization), but the AI-derived content may still be considered PHI under §164.514. Production deployments using the `hf` backend need a signed BAA with HuggingFace **or** a self-hosted MedGemma endpoint inside the BAA-covered perimeter. |

## 6. Data flow summary

```
[Clinician browser]
    │  HTTPS (Caddy auto-TLS)
    ▼
[Caddy] ──/──▶ [Next.js]
        ──/api/*──▶ [FastAPI]
        ──/dicom-web/*──▶ [FastAPI DICOMweb proxy] ──▶ [Orthanc]
                                                          │
                                                          ▼
                                                     [Postgres: orthanc]
[FastAPI] ──▶ [Postgres: app]  (users, studies, jobs, findings, reports, audit_events)
         ──▶ [/data/artifacts] (segmentations, thumbnails, PDFs)
         ──▶ [BackgroundTasks worker] ──▶ [Model registry] ──▶ Findings → ICD-10 → SR/FHIR
```

Every arrow into Orthanc is logged in `audit_events`.
