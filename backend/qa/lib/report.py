"""TestCase record + markdown report writer."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

Status = Literal["PASS", "FAIL", "SKIP", "DEFERRED"]
EMOJI = {"PASS": "✅", "FAIL": "❌", "SKIP": "⚠️", "DEFERRED": "🔒"}


@dataclass
class TestCase:
    round_name: str
    feature: str
    endpoint: str
    status: Status
    evidence: str = ""
    error: str | None = None
    detail: dict = field(default_factory=dict)


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def write_report(
    cases: list[TestCase],
    *,
    out_path: Path,
    medgemma_backend: str,
    dataset_summary: dict,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[Status, int] = {"PASS": 0, "FAIL": 0, "SKIP": 0, "DEFERRED": 0}
    for c in cases:
        counts[c.status] = counts.get(c.status, 0) + 1
    total = len(cases)

    lines: list[str] = []
    lines.append("# Round 10 — Real-data QA report")
    lines.append("")
    lines.append(
        f"**Generated**: {datetime.now(timezone.utc).isoformat(timespec='seconds')}  "
    )
    lines.append(f"**Git SHA**: `{_git_sha()}`  ")
    lines.append(f"**MedGemma backend**: `{medgemma_backend}`  ")
    lines.append(
        f"**Result**: {counts['PASS']} PASS / {counts['FAIL']} FAIL / "
        f"{counts['SKIP']} SKIP / {counts['DEFERRED']} DEFERRED — {total} total"
    )
    lines.append("")

    lines.append("## Dataset summary")
    lines.append("")
    for k, v in dataset_summary.items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")

    lines.append("## Coverage matrix")
    lines.append("")
    lines.append("| Round | Feature | Endpoint / call | Status | Evidence |")
    lines.append("|---|---|---|---|---|")
    for c in cases:
        evidence = (c.evidence or "").replace("|", "\\|").replace("\n", "<br>")
        lines.append(
            f"| {c.round_name} | {c.feature} | `{c.endpoint}` | "
            f"{EMOJI[c.status]} {c.status} | {evidence} |"
        )
    lines.append("")

    # Per-failure detail blocks
    failures = [c for c in cases if c.status == "FAIL"]
    if failures:
        lines.append("## Failures — detail")
        lines.append("")
        for c in failures:
            lines.append(f"### {c.round_name} · {c.feature}")
            lines.append("")
            lines.append(f"- **Endpoint**: `{c.endpoint}`")
            if c.error:
                lines.append(f"- **Error**: {c.error}")
            if c.detail:
                lines.append("- **Detail**:")
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(c.detail, indent=2, default=str)[:2000])
                lines.append("```")
            lines.append("")

    skips = [c for c in cases if c.status == "SKIP"]
    if skips:
        lines.append("## Skipped — reasons")
        lines.append("")
        for c in skips:
            lines.append(f"- **{c.round_name} · {c.feature}**: {c.error or c.evidence}")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
