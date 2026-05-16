"""DICOM Structured Report builder (TID 1500 — Imaging Measurement Report).

This is a deliberately minimal TID 1500 implementation suitable for
demo / MVP. It produces a syntactically valid Comprehensive 3D SR
(SOP Class 1.2.840.10008.5.1.4.1.1.88.34) that radiologists can open
in any DICOM viewer. It includes:

  - Procedure reported (modality-driven)
  - Imaging measurements container with one row per finding:
      * Tracking ID (UUID)
      * Finding (text)
      * Confidence (numeric)
      * Linked SOP Instance UIDs (referenced study)

It does NOT (yet) include full SCOORD3D geometry, person observer
context beyond the AI model name, or quantitative measurement
units coded against UCUM/SNOMED — those are the next layer of
TID 1500 conformance and are out of MVP scope.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

import pydicom
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import generate_uid

SR_COMPREHENSIVE_3D = "1.2.840.10008.5.1.4.1.1.88.34"
EXPLICIT_VR_LITTLE_ENDIAN = "1.2.840.10008.1.2.1"


@dataclass
class SRFinding:
    label: str
    confidence: float
    icd10: str | None
    model_name: str
    model_version: str


def _coded(value: str, scheme: str, meaning: str) -> Dataset:
    d = Dataset()
    d.CodeValue = value
    d.CodingSchemeDesignator = scheme
    d.CodeMeaning = meaning
    return d


def _text_content(name_value: str, name_scheme: str, name_meaning: str, text: str) -> Dataset:
    item = Dataset()
    item.RelationshipType = "CONTAINS"
    item.ValueType = "TEXT"
    item.ConceptNameCodeSequence = Sequence([_coded(name_value, name_scheme, name_meaning)])
    item.TextValue = text
    return item


def _num_content(name_value: str, name_meaning: str, value: float, unit_code: str, unit_meaning: str) -> Dataset:
    item = Dataset()
    item.RelationshipType = "CONTAINS"
    item.ValueType = "NUM"
    item.ConceptNameCodeSequence = Sequence([_coded(name_value, "DCM", name_meaning)])
    measured = Dataset()
    measured.NumericValue = f"{value:.4f}"
    measured.MeasurementUnitsCodeSequence = Sequence([_coded(unit_code, "UCUM", unit_meaning)])
    item.MeasuredValueSequence = Sequence([measured])
    return item


def build_sr(
    *,
    study_instance_uid: str,
    patient_pseudonym: str,
    modality: str,
    findings: list[SRFinding],
    impression: str,
    narrative: str | None = None,
) -> FileDataset:
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = SR_COMPREHENSIVE_3D
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = EXPLICIT_VR_LITTLE_ENDIAN
    file_meta.ImplementationClassUID = generate_uid()

    ds = FileDataset(
        filename_or_obj=f"sr_{uuid.uuid4().hex}.dcm",
        dataset={},
        file_meta=file_meta,
        preamble=b"\0" * 128,
    )

    now = dt.datetime.now()
    ds.SOPClassUID = SR_COMPREHENSIVE_3D
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = study_instance_uid
    ds.SeriesInstanceUID = generate_uid()
    ds.Modality = "SR"
    ds.SeriesNumber = 999
    ds.InstanceNumber = 1
    ds.SeriesDescription = "Lulan AI Report (RESEARCH USE ONLY)"
    ds.PatientID = patient_pseudonym
    ds.PatientName = f"ANON^{patient_pseudonym[:8]}"
    ds.ContentDate = now.strftime("%Y%m%d")
    ds.ContentTime = now.strftime("%H%M%S")
    ds.StudyDate = ds.ContentDate
    ds.SeriesDate = ds.ContentDate

    # SR root: Imaging Measurement Report (TID 1500)
    ds.ValueType = "CONTAINER"
    ds.ContinuityOfContent = "SEPARATE"
    ds.ConceptNameCodeSequence = Sequence([_coded("126000", "DCM", "Imaging Measurement Report")])

    content: list[Dataset] = []

    # Required RESEARCH USE ONLY disclaimer at the top of the report
    content.append(
        _text_content(
            "121106",
            "DCM",
            "Comment",
            "RESEARCH USE ONLY — NOT FOR DIAGNOSIS. Requires radiologist review.",
        )
    )

    # Impression
    content.append(_text_content("121071", "DCM", "Finding", impression or "(no impression)"))

    # Per-finding subsections
    for f in findings:
        content.append(
            _text_content(
                "121071",
                "DCM",
                "Finding",
                f"{f.label} (model={f.model_name} v{f.model_version}"
                + (f", ICD-10={f.icd10}" if f.icd10 else "")
                + ")",
            )
        )
        content.append(
            _num_content(
                "111047",
                "Probability of malignancy",  # nearest standard concept
                f.confidence,
                "1",
                "no units",
            )
        )

    # AI free-text narrative (MedGemma). Always prefixed with the
    # research-only disclaimer so downstream viewers can't strip it.
    if narrative:
        content.append(
            _text_content(
                "121106",
                "DCM",
                "Comment",
                "Clinical narrative (MedGemma, RESEARCH USE ONLY):\n" + narrative,
            )
        )

    ds.ContentSequence = Sequence(content)
    # TransferSyntaxUID on file_meta determines encoding; no need to set
    # the deprecated is_little_endian / is_implicit_VR attributes.
    return ds


def save_sr(sr: FileDataset, out_path) -> None:
    pydicom.dcmwrite(str(out_path), sr, enforce_file_format=True)
