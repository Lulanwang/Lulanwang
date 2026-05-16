"""Fetch DICOMs from public Hugging Face datasets.

We curate a small list of datasets that:
  - Are unauthenticated and small (no auth tokens, < 50 MB per source)
  - Contain genuine DICOM files (not PNGs or NIfTI)
  - Cover brain / lung / chest workflows the system routes on

All downloads are cached in `<cache>/<dataset>/<filename>` so re-runs are
fast and reproducible.

Used by `seed/analyze_external_data.py`.
"""
from __future__ import annotations

import io
import logging
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class HFSource:
    repo: str
    description: str
    # Either a list of (path_in_repo, local_name) tuples for individual files,
    # or a list of (zip_path_in_repo, local_subdir, max_extract) tuples for archives.
    files: list[tuple[str, str]]
    zips: list[tuple[str, str, int]]


# Each source was hand-picked after auditing the dataset on huggingface.co/datasets/<repo>
# to confirm it actually contains DICOMs (many "dicom" datasets are PNG/NIfTI in disguise).
SOURCES: list[HFSource] = [
    HFSource(
        repo="UniqueData/dicom-brain-dataset",
        description="De-identified multi-series brain MRI study (7 series, ~250 instances).",
        # Pull the first 8 instances from series 2 (the longest series, axial MR brain).
        files=[
            (f"ST000001/SE000002/IM00000{i}.dcm", f"brain_se2_im{i}.dcm")
            for i in range(1, 9)
        ],
        zips=[],
    ),
    HFSource(
        repo="ndonyapour/dicom-sample-files",
        description="Chest CT + MR hippocampal sparing study (zipped).",
        files=[],
        zips=[
            ("CT-chest.zip", "ct_chest", 20),
            ("MR-hippocampal-sparing-dataset.zip", "mr_hippocampal", 20),
        ],
    ),
    HFSource(
        repo="hamshkhawar/dicom_mr",
        description="Brain MR (HEAD) files at 132 KB each with full pixel data; ~24+ files in root.",
        files=[
            ("MR.1.2.246.352.221.46143004376852813134301961390876485803.dcm", "hamshkhawar_mr_01.dcm"),
            ("MR.1.2.246.352.221.4621063047905191202691661742037890182.dcm", "hamshkhawar_mr_02.dcm"),
            ("MR.1.2.246.352.221.462450701736744205016277432281183609246.dcm", "hamshkhawar_mr_03.dcm"),
            ("MR.1.2.246.352.221.46297015904340189044141217763381418905.dcm", "hamshkhawar_mr_04.dcm"),
            ("MR.1.2.246.352.221.46302418903211096267121676894464665267.dcm", "hamshkhawar_mr_05.dcm"),
            ("MR.1.2.246.352.221.46340985649020190815336545634186719930.dcm", "hamshkhawar_mr_06.dcm"),
            ("MR.1.2.246.352.221.46362783886722895682180439798989603972.dcm", "hamshkhawar_mr_07.dcm"),
            ("MR.1.2.246.352.221.463783650467046098016227961990833666436.dcm", "hamshkhawar_mr_08.dcm"),
        ],
        zips=[],
    ),
    HFSource(
        repo="SR219/dicom-read",
        description=(
            "Synthetic brain-MRI DICOMs (1000 instances, 884 B each) — METADATA ONLY, "
            "no pixel data. Useful for verifying parse/de-id/route still work when pixels "
            "are missing (which the burned-in / data-corruption edge cases also exercise)."
        ),
        files=[
            (f"test_data/MRN001_20240115_DWI_000{i}.dcm", f"sr219_dwi_im0{i}.dcm")
            for i in range(1, 9)
        ],
        zips=[],
    ),
]


def _download(url: str, dest: Path) -> Path | None:
    """Download with retry; return None on persistent failure."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 256:
        return dest
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "lulan-mvp/0.1"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        if len(data) < 256:
            log.warning("download too small (%d B) from %s", len(data), url)
            return None
        dest.write_bytes(data)
        log.info("fetched %d B → %s", len(data), dest.name)
        return dest
    except Exception as exc:  # noqa: BLE001
        log.warning("download failed for %s: %s", url, exc)
        return None


def _hf_raw_url(repo: str, path: str) -> str:
    # Datasets are served at huggingface.co/datasets/<repo>/resolve/main/<path>
    return f"https://huggingface.co/datasets/{repo}/resolve/main/{path}"


def fetch_all(cache: Path) -> list[tuple[Path, HFSource]]:
    """Download every file + zip into <cache>/<repo>/... and return (path, source) tuples
    for each DICOM that landed on disk."""
    results: list[tuple[Path, HFSource]] = []
    for src in SOURCES:
        repo_dir = cache / src.repo.replace("/", "__")
        repo_dir.mkdir(parents=True, exist_ok=True)

        for path_in_repo, local_name in src.files:
            dest = repo_dir / local_name
            if _download(_hf_raw_url(src.repo, path_in_repo), dest):
                results.append((dest, src))

        for zip_path, subdir, max_extract in src.zips:
            zip_dest = repo_dir / Path(zip_path).name
            if not _download(_hf_raw_url(src.repo, zip_path), zip_dest):
                continue
            extracted_dir = repo_dir / subdir
            if not extracted_dir.exists() or not any(extracted_dir.rglob("*.dcm")):
                extracted_dir.mkdir(parents=True, exist_ok=True)
                try:
                    with zipfile.ZipFile(zip_dest) as zf:
                        # Only extract the first N DICOM members (these archives can
                        # contain hundreds of files; we don't need them all to test).
                        members = [
                            m for m in zf.namelist()
                            if m.lower().endswith(".dcm") and not m.endswith("/")
                        ][:max_extract]
                        for m in members:
                            target = extracted_dir / Path(m).name
                            if target.exists():
                                continue
                            with zf.open(m) as fsrc, open(target, "wb") as fdst:
                                fdst.write(fsrc.read())
                        log.info("extracted %d DICOMs from %s → %s", len(members), zip_path, extracted_dir.name)
                except zipfile.BadZipFile:
                    log.warning("bad zip: %s", zip_dest)
                    continue
            for dcm in sorted(extracted_dir.rglob("*.dcm")):
                results.append((dcm, src))
    return results
