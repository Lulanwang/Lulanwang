"""Run the full pipeline against externally-sourced DICOMs.

Sources:
  1. pydicom 3.x ships 190+ DICOM samples covering CT/MR/CR/US/SEG/RTPLAN etc.
  2. Additional public DICOMs are fetched from well-known GitHub repos that
     host clinical-grade test data (jodogne/OrthancTests, etc.) — small files,
     unauthenticated, available over raw.githubusercontent.com.

For each input, we exercise:
  - DICOM parse + SOP class validation
  - PS3.15 Annex E de-identification
  - Modality + body-part routing to a Model adapter
  - Mock inference + ICD-10 suggestion

We emit a JSON + Markdown report so the user can audit what the system did
on each input.

Run:
    python -m seed.analyze_external_data --out /tmp/analysis
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass, field
from io import BytesIO
from pathlib import Path

import pydicom
from pydicom.data import get_testdata_file, get_testdata_files

from app.dicom.deidentify import deidentify
from app.dicom.parse import extract_study_meta
from app.dicom.validators import is_accepted_sop_class, model_key_for
from app.models.base import StudyInput
from app.models.registry import resolve_model
from app.services import icd10
from seed.huggingface_datasets import fetch_all as hf_fetch_all

log = logging.getLogger("analyze-external")


# pydicom 3.x ships a small subset bundled in the wheel and hosts the rest
# in the public pydicom/pydicom-data GitHub repository — these names trigger
# a one-time download into the user's pydicom cache via
# pydicom.data.get_testdata_file(name, download=True).
#
# Selected to broaden modality coverage beyond what's bundled (chest X-rays
# and additional MR/CT studies relevant to the brain/lung/breast pipeline).
PYDICOM_DOWNLOAD_NAMES: list[str] = [
    # MR brain — emri_small is a 10-frame multiframe brain MR;
    # the variants exercise different transfer syntaxes (JPEG-LS, JPEG-2K,
    # RLE, big-endian). All should route to brain_mri.
    "emri_small.dcm",
    "emri_small_RLE.dcm",
    "emri_small_big_endian.dcm",
    "emri_small_jpeg_2k_lossless.dcm",
    "emri_small_jpeg_ls_lossless.dcm",
    # Additional MR studies (exercise modality detection on different formats)
    "MR2_J2KI.dcm",
    "MR2_J2KR.dcm",
    "MR2_UNCI.dcm",
    "MR2_UNCR.dcm",
    "MR-SIEMENS-DICOM-WithOverlays.dcm",
    # CT
    "693_J2KI.dcm",
    "693_UNCR.dcm",
    "eCT_Supplemental.dcm",
    "CT_small.dcm",
    # CR (computed radiography — chest/extremity X-rays)
    "RG1_UNCR.dcm",
    "RG3_UNCR.dcm",
    # US / secondary capture (should be modality-routed or blocked)
    "US1_UNCR.dcm",
    "OBXXXX1A.dcm",
    "JPEG-LL.dcm",
    "color3d_jpeg_baseline.dcm",
    "JPGLosslessP14SV1_1s_1f_8b.dcm",
]


# pydicom samples with these substrings in the filename map to brain/lung/breast.
# (pydicom doesn't tag BodyPartExamined consistently in the bundled samples.)
BODY_PART_KEYWORDS = {
    "BRAIN": ("brain", "head", "skull", "cerebr", "glioma", "emri", "neuro"),
    "CHEST": ("chest", "lung", "thorax", "pulmonary", "pulmon", "nodule", "lid"),
    "BREAST": ("mammo", "breast", "mlo", "cc-view", "tomo"),
}


def _body_part_from_text(text: str) -> str | None:
    t = text.lower()
    for canonical, kws in BODY_PART_KEYWORDS.items():
        if any(kw in t for kw in kws):
            return canonical
    return None


@dataclass
class FileResult:
    source: str
    name: str
    sop_class_uid: str | None = None
    sop_class_accepted: bool = False
    modality: str | None = None
    body_part: str | None = None
    body_part_inferred: bool = False
    deid_ok: bool = False
    deid_blocked_reason: str | None = None
    pseudonym: str | None = None
    model_key: str | None = None
    model_name: str | None = None
    finding_count: int = 0
    findings: list[dict] = field(default_factory=list)
    icd10_codes: list[str] = field(default_factory=list)
    error: str | None = None


def _download(url: str, dest: Path) -> Path | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "lulan-mvp/0.1"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
        if len(data) < 256:
            log.warning("download too small (%d B) from %s — skipping", len(data), url)
            return None
        dest.write_bytes(data)
        log.info("downloaded %d B → %s", len(data), dest.name)
        return dest
    except Exception as exc:  # noqa: BLE001
        log.warning("download failed for %s: %s", url, exc)
        return None


def _infer_body_part(path: Path, ds: pydicom.Dataset) -> tuple[str, bool]:
    explicit = str(getattr(ds, "BodyPartExamined", "") or "").upper()
    if explicit and explicit != "UNKNOWN":
        # Map common synonyms to our canonical body part names
        if explicit in {"HEAD", "SKULL"}:
            return "BRAIN", False
        if explicit in {"LUNG", "THORAX"}:
            return "CHEST", False
        return explicit, False
    # Concatenate all text-typed tags that commonly carry the anatomical
    # context and search for keywords.
    text_sources = [path.name]
    for attr in (
        "StudyDescription",
        "SeriesDescription",
        "ProtocolName",
        "BodyPartExamined",
        "AcquisitionDeviceProcessingDescription",
        "PerformedProcedureStepDescription",
        "ImageComments",
    ):
        text_sources.append(str(getattr(ds, attr, "") or ""))
    inferred = _body_part_from_text(" ".join(text_sources))
    if inferred:
        return inferred, True
    return "UNKNOWN", False


def _analyze(path: Path, source: str) -> FileResult:
    r = FileResult(source=source, name=path.name)
    try:
        ds = pydicom.dcmread(str(path), force=True)
    except Exception as exc:  # noqa: BLE001
        r.error = f"read failed: {exc}"
        return r

    r.sop_class_uid = str(getattr(ds, "SOPClassUID", "") or "")
    r.sop_class_accepted = is_accepted_sop_class(ds)
    try:
        meta = extract_study_meta(ds)
    except Exception as exc:  # noqa: BLE001
        r.error = f"meta failed: {exc}"
        return r
    r.modality = meta.modality

    body_part, inferred = _infer_body_part(path, ds)
    r.body_part = body_part
    r.body_part_inferred = inferred

    # De-identify (mutates a copy so we don't break the source file)
    ds_copy = pydicom.dcmread(BytesIO(path.read_bytes()), force=True)
    deid = deidentify(ds_copy)
    r.deid_ok = deid.ok
    r.deid_blocked_reason = deid.blocked_reason
    r.pseudonym = deid.pseudonym or None

    # Route + infer (mock only — we don't need real weights here)
    key = model_key_for(meta.modality, body_part)
    r.model_key = key
    if key is None:
        return r
    model = resolve_model(meta.modality, body_part)
    if model is None:
        return r
    r.model_name = model.name
    findings = model.infer(
        StudyInput(
            study_instance_uid=meta.study_instance_uid,
            modality=meta.modality,
            body_part=body_part,
            datasets=[ds_copy],
            tempdir="/tmp",
        )
    )
    r.finding_count = len(findings)
    r.findings = [
        {
            "label": f.label,
            "confidence": round(f.confidence, 3),
            "icd10": f.icd10_suggestion or icd10.suggest_for(f.label, f.body_part),
        }
        for f in findings
    ]
    r.icd10_codes = sorted({c["icd10"] for c in r.findings if c["icd10"]})
    return r


def _markdown_report(results: list[FileResult]) -> str:
    by_source = Counter(r.source for r in results)
    accepted = sum(1 for r in results if r.sop_class_accepted)
    deid_ok = sum(1 for r in results if r.deid_ok)
    routed = sum(1 for r in results if r.model_key)
    with_findings = sum(1 for r in results if r.finding_count > 0)
    mod_counts = Counter(r.modality for r in results if r.modality)

    lines = [
        "# External DICOM data analysis",
        "",
        "Generated by `seed/analyze_external_data.py`. Mock inference;",
        "this report verifies the *plumbing*, not clinical accuracy.",
        "",
        "## Summary",
        f"- Total files analyzed: **{len(results)}**",
        "- By source: " + ", ".join(f"{s}={n}" for s, n in by_source.items()),
        f"- Accepted SOP class: {accepted}/{len(results)}",
        f"- De-identification succeeded: {deid_ok}/{len(results)}",
        f"- Routed to a model: {routed}/{len(results)}",
        f"- Produced findings: {with_findings}/{len(results)}",
        "- Modalities seen: " + ", ".join(f"{m}={n}" for m, n in mod_counts.most_common()),
        "",
        "## Per-file detail",
        "",
        "| Source | File | Modality | Body part | SOP ok | De-id | Model | Findings | ICD-10 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        icd = ", ".join(r.icd10_codes) if r.icd10_codes else "—"
        body = (r.body_part or "—") + (" (inferred)" if r.body_part_inferred else "")
        if r.error:
            deid_cell = f"error: {r.error[:40]}"
        elif r.deid_ok:
            deid_cell = "yes"
        else:
            deid_cell = f"blocked: {r.deid_blocked_reason or '—'}"
        lines.append(
            f"| {r.source} | `{r.name}` | {r.modality or '—'} | {body} | "
            f"{'yes' if r.sop_class_accepted else 'no'} | {deid_cell} | "
            f"{r.model_key or '—'} | {r.finding_count} | {icd} |"
        )
    if any(r.findings for r in results):
        lines += ["", "## Sample findings"]
        for r in results:
            if not r.findings:
                continue
            lines.append(f"\n### {r.name}  ({r.modality}/{r.body_part})")
            for f in r.findings:
                lines.append(
                    f"- **{f['label']}** — confidence {f['confidence']}"
                    + (f", ICD-10 `{f['icd10']}`" if f["icd10"] else "")
                )
    return "\n".join(lines) + "\n"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/lulan-analysis", help="output directory")
    ap.add_argument("--limit-pydicom", type=int, default=80, help="cap on pydicom samples")
    ap.add_argument("--skip-github", action="store_true", help="don't try GitHub downloads")
    ap.add_argument("--skip-hf", action="store_true", help="don't fetch Hugging Face datasets")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cache = out / "cache"
    cache.mkdir(exist_ok=True)

    results: list[FileResult] = []

    # 1) pydicom bundled samples
    pydicom_samples = get_testdata_files()
    log.info("found %d pydicom bundled samples; analyzing up to %d", len(pydicom_samples), args.limit_pydicom)
    for p in pydicom_samples[: args.limit_pydicom]:
        results.append(_analyze(Path(p), source="pydicom"))

    # 2) pydicom-data repo on GitHub — files not bundled in the wheel but
    #    fetched on demand from https://github.com/pydicom/pydicom-data.
    if not args.skip_github:
        for name in PYDICOM_DOWNLOAD_NAMES:
            try:
                path = get_testdata_file(name, download=True)
            except Exception as exc:  # noqa: BLE001
                log.warning("pydicom-data fetch failed for %s: %s", name, exc)
                results.append(FileResult(source="pydicom-data (github)", name=name, error=str(exc)[:160]))
                continue
            if path is None:
                results.append(FileResult(source="pydicom-data (github)", name=name, error="not found"))
                continue
            results.append(_analyze(Path(path), source="pydicom-data (github)"))

    # 3) Hugging Face datasets — real anonymized brain MR + chest CT + MR
    #    hippocampal studies. Cached so re-runs are fast.
    if not args.skip_hf:
        try:
            hf_files = hf_fetch_all(cache)
            log.info("hugging face: %d DICOMs available", len(hf_files))
            for path, src in hf_files:
                results.append(_analyze(path, source=f"hf:{src.repo}"))
        except Exception:  # noqa: BLE001
            log.exception("hugging face fetch failed")

    # Write JSON
    (out / "analysis.json").write_text(json.dumps([asdict(r) for r in results], indent=2))
    # Write Markdown
    md = _markdown_report(results)
    (out / "report.md").write_text(md)
    log.info("wrote %d results to %s", len(results), out)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
