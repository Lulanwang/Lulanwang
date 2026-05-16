"""Network-gated tests for the Hugging Face DICOM fetcher.

These hit huggingface.co so they're skipped by default. Run with
`LULAN_NETWORK_TESTS=1 pytest -q tests/test_huggingface_datasets.py`
to actually exercise them.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from seed.huggingface_datasets import SOURCES, _hf_raw_url, fetch_all


def test_source_definitions_are_reasonable():
    assert len(SOURCES) >= 2
    for src in SOURCES:
        assert src.repo.count("/") == 1, f"bad repo: {src.repo}"
        assert src.description
        # Either individual files or zips must be configured
        assert src.files or src.zips
        for path_in_repo, local_name in src.files:
            assert path_in_repo.endswith(".dcm")
            assert local_name.endswith(".dcm")
        for zip_path, subdir, max_extract in src.zips:
            assert zip_path.endswith(".zip")
            assert subdir and "/" not in subdir
            assert max_extract > 0


def test_hf_raw_url_format():
    assert (
        _hf_raw_url("UniqueData/dicom-brain-dataset", "ST000001/SE000002/IM000001.dcm")
        == "https://huggingface.co/datasets/UniqueData/dicom-brain-dataset/resolve/main/ST000001/SE000002/IM000001.dcm"
    )


@pytest.mark.skipif(
    not os.environ.get("LULAN_NETWORK_TESTS"),
    reason="set LULAN_NETWORK_TESTS=1 to run network-bound HF fetch tests",
)
def test_fetch_all_returns_at_least_one_dicom(tmp_path: Path):
    files = fetch_all(tmp_path)
    assert files, "expected at least one DICOM from at least one source"
    for path, src in files:
        assert path.exists()
        assert path.stat().st_size > 256
        assert src in SOURCES
