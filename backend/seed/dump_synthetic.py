"""Dump synthetic DICOMs to a directory.

Useful for manually testing the upload endpoint or for inspecting the
generated images in a DICOM viewer outside the stack.

Run:
  docker compose exec backend python -m seed.dump_synthetic /data/artifacts/synthetic
  # or, locally:
  python -m seed.dump_synthetic ./out
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from seed.synthetic_dicom import generate_demo_studies, write_to_disk

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("dump-synthetic")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m seed.dump_synthetic <output_dir>", file=sys.stderr)
        return 2
    out_root = Path(argv[1])
    out_root.mkdir(parents=True, exist_ok=True)

    total = 0
    for synth in generate_demo_studies():
        sub = out_root / f"{synth.modality}_{synth.body_part}"
        paths = write_to_disk(synth, sub)
        total += len(paths)
        log.info("wrote %d %s/%s instances → %s", len(paths), synth.modality, synth.body_part, sub)
    log.info("done: %d files in %s", total, out_root)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
