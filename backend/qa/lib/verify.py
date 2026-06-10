"""Re-verify generated artifacts (SR, FHIR, thumbnail, dose summary)."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pydicom
from PIL import Image


def verify_sr_bytes(sr_bytes: bytes, *, expect_text_substrings: list[str]) -> dict:
    """Re-read DICOM SR bytes via pydicom and assert every expected substring
    is in some TextValue. Returns {ok, found, missing, sop_class}."""
    ds = pydicom.dcmread(io.BytesIO(sr_bytes), force=True)
    text_blob = ""
    for item in ds.ContentSequence:
        v = getattr(item, "TextValue", None)
        if v:
            text_blob += "\n" + str(v)
    found, missing = [], []
    for s in expect_text_substrings:
        (found if s in text_blob else missing).append(s)
    return {
        "ok": not missing,
        "found": found,
        "missing": missing,
        "sop_class": str(ds.SOPClassUID),
        "text_blob_len": len(text_blob),
    }


def verify_fhir_diagnostic_report(payload: dict, *, expect_in_conclusion: list[str]) -> dict:
    """Lightweight FHIR DiagnosticReport shape check."""
    conclusion = payload.get("conclusion", "")
    found, missing = [], []
    for s in expect_in_conclusion:
        (found if s in conclusion else missing).append(s)
    return {
        "ok": (
            payload.get("resourceType") == "DiagnosticReport"
            and not missing
        ),
        "found": found,
        "missing": missing,
        "status": payload.get("status"),
        "conclusion_len": len(conclusion),
        "conclusion_code_count": len(payload.get("conclusionCode", []) or []),
    }


def verify_thumbnail_bytes(png_bytes: bytes) -> dict:
    """Decode bytes as a PNG and assert it's a reasonable thumbnail."""
    img = Image.open(io.BytesIO(png_bytes))
    img.load()
    return {
        "ok": (
            img.format == "PNG"
            and max(img.size) <= 512
            and img.mode in ("L", "RGB", "RGBA")
        ),
        "format": img.format,
        "size": img.size,
        "mode": img.mode,
    }


def save_artifact(path: Path, data: bytes | str | dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    elif isinstance(data, dict):
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    else:
        path.write_text(str(data), encoding="utf-8")
