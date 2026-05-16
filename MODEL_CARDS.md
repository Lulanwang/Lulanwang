# Model cards

> Every model below is **research use only**. None is FDA-cleared,
> CE-marked, or validated for clinical use. Outputs are unverified and
> must not influence patient care.

## 1. MockModel (default)

- **Purpose**: deterministic placeholder so the full pipeline (PACS →
  inference → ICD-10 → SR/FHIR → audit) runs without GPUs or weight
  downloads.
- **Inputs**: any DICOM study.
- **Outputs**: 1–3 fixed `Finding` objects keyed off modality + body
  part, with a fake confidence of 0.42.
- **Training data**: none.
- **Known failure modes**: it is fake. Do not interpret outputs.
- **Code**: `backend/app/models/mock.py`

## 2. Brain MRI — `brats_mri_segmentation` (MONAI Bundle)

- **Purpose**: whole-tumor / tumor-core / enhancing-tumor segmentation
  on multimodal brain MRI (T1, T1Gd, T2, FLAIR).
- **Training data**: BraTS challenge (adult glioma, multi-institutional).
- **License**: MONAI Bundle (Apache 2.0); BraTS data usage governed by
  the BraTS Data Use Agreement.
- **Architecture**: SegResNet or SwinUNETR variant (see bundle metadata).
- **Intended use (per bundle authors)**: research demonstration of
  glioma segmentation. Not a diagnostic tool.
- **Known failure modes**:
  - Trained on adult glioma — performance on pediatric tumors,
    metastases, meningiomas, or non-tumor lesions is undefined.
  - Sensitive to MR sequence selection and preprocessing; failures on
    non-BraTS-style preprocessing are common.
  - No uncertainty calibration.
- **Inputs**: 4-channel MR volume in BraTS preprocessing convention.
- **Outputs**: 3-class segmentation mask → simplified to a single
  `Finding` ("Suspected glioma, segmentation available") with volume
  in mL and a link to the saved DICOM SEG.
- **Code**: `backend/app/models/brain_mri.py`

## 3. Lung CT — `lung_nodule_ct_detection` (MONAI Bundle)

- **Purpose**: pulmonary nodule detection on non-contrast chest CT.
- **Training data**: LUNA16 (LIDC-IDRI subset, 888 scans).
- **License**: MONAI Bundle (Apache 2.0); LIDC-IDRI subject to TCIA
  data use restrictions.
- **Architecture**: RetinaNet-3D variant.
- **Intended use (per bundle authors)**: research demonstration of
  nodule detection.
- **Known failure modes**:
  - Trained on screening-style low-dose CT; performance on
    contrast-enhanced or non-screening scans is undefined.
  - Detection only — does not characterize benign vs. malignant.
  - No calibration on demographic subgroups documented.
  - Sensitive to slice thickness and reconstruction kernel.
- **Inputs**: axial chest CT volume, ≤ 2.5 mm slice thickness recommended.
- **Outputs**: list of 3D bounding boxes with confidence scores →
  one `Finding` per box ("Pulmonary nodule, X mm").
- **Code**: `backend/app/models/lung_ct.py`

## 4. Breast mammography — **MockModel** (no clean open-weights model shipped)

- **Purpose**: placeholder. There is no permissively-licensed,
  unencumbered open-weights mammography classifier of clinical
  relevance that we are willing to ship as a "real" demo.
- **What about other options?**
  - **Mirai (MIT/Harvard)**: 5-year breast cancer risk model, weights
    gated and require a registration agreement. Not suitable for an
    open MVP.
  - **TorchXRayVision**: chest X-ray, not mammography. Do not use.
  - **CBIS-DDSM fine-tunes**: feasible but require us to train and host
    weights with documented validation, which is out of MVP scope.
- **Adapter scaffolding**: `backend/app/models/breast_mammo.py`
  contains a `BreastMammoModel` class that loads `torchvision`
  `densenet121` weights if a path is provided via
  `BREAST_MAMMO_WEIGHTS=/path/to/weights.pt`. When unset (the default),
  it delegates to `MockModel` and the UI shows a clear "model not
  loaded — mock outputs" badge.

## 5. Narrative writer — MedGemma (`google/medgemma-4b-it`)

This is **not** a detector — it does not produce structured Findings.
It is a free-text narrative writer that runs *after* the detector(s)
above and converts the structured `Finding` list into a clinical
narrative paragraph attached to the report (DICOM SR + FHIR
`DiagnosticReport`).

- **Purpose**: turn the mechanical bulleted impression
  ("- Suspected glioma (confidence=0.42)") into a brief clinical
  narrative a radiologist can read, edit, and sign off on.
- **Inputs**: structured `Finding` rows (label, body part, confidence,
  ICD-10 suggestion, model name/version) + study metadata (modality,
  body part, description). **No pixel data is sent.**
- **Outputs**: free-text narrative, ≤ 512 tokens, always followed by
  the `RESEARCH USE ONLY` disclaimer.
- **Backends**:
  - `MEDGEMMA_BACKEND=mock` (default) — deterministic in-process
    template; no network egress. Safe for demos and tests.
  - `MEDGEMMA_BACKEND=hf` — POST to a Hugging Face Inference Endpoint
    at `MEDGEMMA_HF_ENDPOINT_URL` with `MEDGEMMA_HF_TOKEN`. See
    `COMPLIANCE.md` §5 for the data-egress implications.
- **Training data**: per Google's Health AI Developer Foundations
  documentation — de-identified medical text and imaging mix; full
  composition is published on the model's HuggingFace card.
- **License**: Google Health AI Developer Foundations Terms of Use.
  Requires acceptance on HuggingFace before pulling weights; **not** a
  standard OSI-approved open-source license.
- **Known failure modes**:
  - **Hallucination** — may invent findings not present in the
    structured input. Mitigation: prompt header explicitly forbids
    invention, but this is not 100% reliable.
  - **Published RadGraph F1 ≈ 30** untuned on chest-X-ray report
    generation; instruction-tuned variants tend to score lower.
    Google's published recommendation is institutional fine-tuning
    before any clinical-adjacent use.
  - **Treatment language** — may surface recommendations despite the
    prompt forbidding them.
  - **Calibration / bias** — no per-demographic calibration documented.
- **Inputs that DO NOT go to MedGemma in this MVP**:
  - DICOM pixel data
  - PatientID / PatientName / MRN / accession number
  - Date of birth, address, phone, or any direct identifier
- **Code**: `backend/app/services/medgemma.py`
- **Disclaimer (enforced in code; cannot be stripped)**:
  > "RESEARCH USE ONLY — NOT FOR DIAGNOSIS. Generated by AI; requires
  > licensed radiologist review before clinical use."

## 6. Adding your own model

Implement the `Model` interface in `backend/app/models/base.py`:

```python
class Model(Protocol):
    name: str
    version: str
    modality: str           # "MR" | "CT" | "MG" | ...
    body_part: str          # "BRAIN" | "CHEST" | "BREAST"

    def infer(self, study: Study) -> list[Finding]: ...
```

Register it in `backend/app/models/registry.py`. The pipeline will
route studies whose `(modality, body_part)` matches.

## 7. Output disclaimers (enforced in UI)

- Every finding rendered in the UI carries a `DisclaimerBadge`:
  > "AI-generated, unverified. Model: `<name>` v`<ver>`. Confidence: `<x>`."
- Every generated report (DICOM SR + FHIR DiagnosticReport) carries
  the footer:
  > "Generated `<ts>` by `<model>`. Requires licensed radiologist
  > review and signature before clinical use."
