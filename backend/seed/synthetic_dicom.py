"""Synthetic DICOM generator.

pydicom's bundled samples are tiny (single-slice 128x128 toy data) and
don't exercise multi-slice volumes, realistic pixel statistics, or the
three modalities we care about (CT chest, MR brain, MG mammography).
This module generates synthetic studies that:

  * have correct DICOM file_meta + dataset alignment for STOW
  * carry realistic modality / body-part / SOP-class tags
  * include procedurally-generated pixel data with a visible "lesion"
    (a small intensity peak) so a real reviewer can spot it in any
    viewer — this makes the demo visually convincing
  * cover the three target cancer workflows: brain MRI, lung CT,
    breast mammography

The generated images are NOT clinically realistic. They look like noisy
phantoms with a bright spot, which is enough to exercise the pipeline
end-to-end. Real validation needs real data with IRB approval.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pydicom
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid


@dataclass
class SyntheticStudy:
    """A generated study, ready to STOW into Orthanc."""

    modality: str
    body_part: str
    description: str
    datasets: list[FileDataset]


# SOP Class UIDs for each generated modality
_SOP_CLASS = {
    "CT": "1.2.840.10008.5.1.4.1.1.2",  # CT Image Storage
    "MR": "1.2.840.10008.5.1.4.1.1.4",  # MR Image Storage
    "MG": "1.2.840.10008.5.1.4.1.1.1.2",  # Digital Mammography X-Ray Image Storage - For Presentation
}


def _make_file_meta(sop_class_uid: str, sop_instance_uid: str) -> FileMetaDataset:
    fm = FileMetaDataset()
    fm.MediaStorageSOPClassUID = sop_class_uid
    fm.MediaStorageSOPInstanceUID = sop_instance_uid
    fm.TransferSyntaxUID = ExplicitVRLittleEndian
    fm.ImplementationClassUID = generate_uid()
    fm.ImplementationVersionName = "LULAN_MVP_0.1"
    return fm


def _synthetic_pixels(
    shape: tuple[int, int],
    *,
    background_mean: float,
    background_std: float,
    lesion_center: tuple[float, float] | None,
    lesion_radius: int,
    lesion_intensity: float,
    seed: int,
) -> np.ndarray:
    """Generate a 2D image with Gaussian noise + an optional bright spot."""
    rng = np.random.default_rng(seed)
    h, w = shape
    img = rng.normal(background_mean, background_std, size=(h, w))

    # Add a soft elliptical "body" so it doesn't look uniformly noisy
    yy, xx = np.ogrid[:h, :w]
    cy, cx = h / 2, w / 2
    body = np.exp(-(((yy - cy) / (h * 0.4)) ** 2 + ((xx - cx) / (w * 0.35)) ** 2))
    img = img + body * (background_mean * 0.5)

    if lesion_center is not None:
        ly, lx = lesion_center
        mask = (yy - ly) ** 2 + (xx - lx) ** 2 <= lesion_radius**2
        img = img + mask * lesion_intensity

    # Clamp to 16-bit unsigned range
    img = np.clip(img, 0, 4095)
    return img.astype(np.uint16)


def _base_dataset(
    *,
    modality: str,
    body_part: str,
    study_uid: str,
    series_uid: str,
    instance_uid: str,
    instance_number: int,
    description: str,
    patient_id: str,
    patient_name: str,
    rows: int,
    cols: int,
) -> FileDataset:
    sop_class = _SOP_CLASS[modality]
    fm = _make_file_meta(sop_class, instance_uid)
    ds = FileDataset(
        filename_or_obj=f"{modality}_{instance_number}.dcm",
        dataset={},
        file_meta=fm,
        preamble=b"\0" * 128,
    )

    now = dt.datetime.now()
    ds.SOPClassUID = sop_class
    ds.SOPInstanceUID = instance_uid
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid

    ds.Modality = modality
    ds.BodyPartExamined = body_part
    ds.StudyDescription = description
    ds.SeriesDescription = f"{modality} {body_part} (synthetic, research only)"
    ds.PatientName = patient_name
    ds.PatientID = patient_id
    ds.PatientBirthDate = "19700101"
    ds.PatientSex = "F"

    ds.StudyDate = now.strftime("%Y%m%d")
    ds.StudyTime = now.strftime("%H%M%S")
    ds.ContentDate = ds.StudyDate
    ds.ContentTime = ds.StudyTime
    ds.SeriesDate = ds.StudyDate

    ds.AccessionNumber = f"SYN{instance_number:06d}"
    ds.ReferringPhysicianName = "REFERRING^Synthetic"
    ds.InstitutionName = "Synthetic Demo Clinic"
    ds.Manufacturer = "Lulan-MVP-Generator"

    ds.InstanceNumber = instance_number
    ds.Rows = rows
    ds.Columns = cols
    ds.BitsAllocated = 16
    ds.BitsStored = 12
    ds.HighBit = 11
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelSpacing = [0.7, 0.7]

    ds.BurnedInAnnotation = "NO"

    return ds


def _ct_chest(patient_id: str = "SYN-LUNG-001", slices: int = 20) -> SyntheticStudy:
    study_uid = generate_uid()
    series_uid = generate_uid()
    rows, cols = 256, 256

    # Place a 3D nodule near the right upper lobe in the middle of the series.
    nodule_z = slices // 2
    datasets = []
    for i in range(slices):
        # 5-slice tall nodule
        in_nodule = abs(i - nodule_z) <= 2
        ds = _base_dataset(
            modality="CT",
            body_part="CHEST",
            study_uid=study_uid,
            series_uid=series_uid,
            instance_uid=generate_uid(),
            instance_number=i + 1,
            description="Chest CT, synthetic (RESEARCH USE ONLY)",
            patient_id=patient_id,
            patient_name="SYNTHETIC^Lung",
            rows=rows,
            cols=cols,
        )
        # CT-specific tags
        ds.RescaleSlope = 1
        ds.RescaleIntercept = -1024  # so 0 → -1024 HU (air-like)
        ds.SliceThickness = 1.25
        ds.SliceLocation = i * 1.25
        ds.ImagePositionPatient = [-128.0, -128.0, i * 1.25]
        ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        ds.KVP = 120
        pixels = _synthetic_pixels(
            (rows, cols),
            background_mean=1200,  # post-intercept ~ 176 HU; noisy "soft-tissue-ish"
            background_std=120,
            lesion_center=(int(rows * 0.4), int(cols * 0.6)) if in_nodule else None,
            lesion_radius=6,
            lesion_intensity=600,
            seed=hash((patient_id, i)) & 0xFFFFFFFF,
        )
        ds.PixelData = pixels.tobytes()
        datasets.append(ds)

    return SyntheticStudy(
        modality="CT",
        body_part="CHEST",
        description="Chest CT, synthetic (RESEARCH USE ONLY)",
        datasets=datasets,
    )


def _mr_brain(patient_id: str = "SYN-BRAIN-001", slices: int = 16) -> SyntheticStudy:
    study_uid = generate_uid()
    series_uid = generate_uid()
    rows, cols = 192, 192

    tumor_z = slices // 2
    datasets = []
    for i in range(slices):
        in_tumor = abs(i - tumor_z) <= 2
        ds = _base_dataset(
            modality="MR",
            body_part="BRAIN",
            study_uid=study_uid,
            series_uid=series_uid,
            instance_uid=generate_uid(),
            instance_number=i + 1,
            description="Brain MRI, synthetic (RESEARCH USE ONLY)",
            patient_id=patient_id,
            patient_name="SYNTHETIC^Brain",
            rows=rows,
            cols=cols,
        )
        ds.SliceThickness = 4.0
        ds.SliceLocation = i * 4.0
        ds.ImagePositionPatient = [-96.0, -96.0, i * 4.0]
        ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        ds.MagneticFieldStrength = 3.0
        ds.SequenceName = "T1_SE"
        ds.RepetitionTime = "500"
        ds.EchoTime = "12"
        pixels = _synthetic_pixels(
            (rows, cols),
            background_mean=800,
            background_std=80,
            lesion_center=(int(rows * 0.35), int(cols * 0.55)) if in_tumor else None,
            lesion_radius=8,
            lesion_intensity=900,
            seed=hash((patient_id, i)) & 0xFFFFFFFF,
        )
        ds.PixelData = pixels.tobytes()
        datasets.append(ds)

    return SyntheticStudy(
        modality="MR",
        body_part="BRAIN",
        description="Brain MRI, synthetic (RESEARCH USE ONLY)",
        datasets=datasets,
    )


def _mg_breast(patient_id: str = "SYN-BREAST-001") -> SyntheticStudy:
    """Single-view mammogram with a cluster of bright microcalcifications."""
    study_uid = generate_uid()
    series_uid = generate_uid()
    rows, cols = 1024, 768  # higher resolution for mammography

    ds = _base_dataset(
        modality="MG",
        body_part="BREAST",
        study_uid=study_uid,
        series_uid=series_uid,
        instance_uid=generate_uid(),
        instance_number=1,
        description="Mammogram (CC), synthetic (RESEARCH USE ONLY)",
        patient_id=patient_id,
        patient_name="SYNTHETIC^Breast",
        rows=rows,
        cols=cols,
    )
    ds.ViewPosition = "CC"
    ds.ImageLaterality = "L"
    ds.PixelSpacing = [0.1, 0.1]
    ds.PresentationIntentType = "FOR PRESENTATION"

    # Background tissue
    rng = np.random.default_rng(hash(patient_id) & 0xFFFFFFFF)
    pixels = rng.normal(2200, 200, size=(rows, cols))
    # Soft breast silhouette (right-side weighted)
    yy, xx = np.ogrid[:rows, :cols]
    silhouette = np.clip(1.0 - ((xx - cols * 0.85) / (cols * 0.6)) ** 2 - ((yy - rows / 2) / (rows / 2)) ** 2, 0, None)
    pixels += silhouette * 600

    # Microcalcification cluster: 6 bright pinpoints in the upper-outer quadrant
    cluster_y, cluster_x = int(rows * 0.30), int(cols * 0.40)
    for dy, dx in [(0, 0), (3, 4), (-2, 6), (5, -3), (-4, -2), (1, -7)]:
        y, x = cluster_y + dy * 2, cluster_x + dx * 2
        pixels[y - 1 : y + 2, x - 1 : x + 2] += 2500

    pixels = np.clip(pixels, 0, 4095).astype(np.uint16)
    ds.PixelData = pixels.tobytes()

    return SyntheticStudy(
        modality="MG",
        body_part="BREAST",
        description="Mammogram (CC), synthetic (RESEARCH USE ONLY)",
        datasets=[ds],
    )


def generate_demo_studies() -> list[SyntheticStudy]:
    """The three studies the worklist will show after seeding."""
    return [_mr_brain(), _ct_chest(), _mg_breast()]


def generate_burned_in_study() -> SyntheticStudy:
    """A CT with BurnedInAnnotation=YES — used to exercise the de-id block path."""
    s = _ct_chest(patient_id="SYN-BURNED-001", slices=3)
    for ds in s.datasets:
        ds.BurnedInAnnotation = "YES"
    s.description = "Chest CT with burned-in PHI (should be blocked)"
    return s


def write_to_disk(study: SyntheticStudy, out_dir) -> list[str]:
    """Persist datasets to a directory; useful for manual testing and seed scripts."""
    from pathlib import Path

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for ds in study.datasets:
        p = out / f"{study.modality}_{ds.InstanceNumber:04d}.dcm"
        pydicom.dcmwrite(str(p), ds, enforce_file_format=True)
        paths.append(str(p))
    return paths
