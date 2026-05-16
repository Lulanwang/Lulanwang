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

## 5. Adding your own model

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

## 6. Output disclaimers (enforced in UI)

- Every finding rendered in the UI carries a `DisclaimerBadge`:
  > "AI-generated, unverified. Model: `<name>` v`<ver>`. Confidence: `<x>`."
- Every generated report (DICOM SR + FHIR DiagnosticReport) carries
  the footer:
  > "Generated `<ts>` by `<model>`. Requires licensed radiologist
  > review and signature before clinical use."
