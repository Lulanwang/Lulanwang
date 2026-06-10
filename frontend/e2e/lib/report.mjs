#!/usr/bin/env node
/**
 * Convert a Playwright JSON report into the round-11 markdown verification
 * report. Reads stdin or --in <path>, writes to --out <path>.
 *
 * Usage:
 *   cat results.json | node report.mjs --out report.md
 *   node report.mjs --in results.json --out report.md
 */
import fs from "node:fs";

const argv = process.argv.slice(2);
function arg(flag) {
  const i = argv.indexOf(flag);
  return i >= 0 ? argv[i + 1] : null;
}

const inPath = arg("--in");
const outPath = arg("--out") ?? "round11_ui_qa_report.md";
const raw = inPath ? fs.readFileSync(inPath, "utf-8") : fs.readFileSync(0, "utf-8");
const data = JSON.parse(raw);

const EMOJI = {
  passed: "✅",
  expected: "✅",
  failed: "❌",
  timedOut: "❌",
  unexpected: "❌",
  skipped: "⚠️",
};

function* walkSpecs(suites, parents = []) {
  for (const s of suites ?? []) {
    const trail = [...parents, s.title].filter(Boolean);
    for (const spec of s.specs ?? []) {
      for (const test of spec.tests ?? []) {
        const last = test.results?.[test.results.length - 1] ?? {};
        yield {
          file: spec.file ?? "?",
          suite: trail.join(" > "),
          name: spec.title,
          status: last.status ?? "unknown",
          durationMs: last.duration ?? 0,
          error: last.error?.message ?? null,
        };
      }
    }
    yield* walkSpecs(s.suites, trail);
  }
}

const tests = Array.from(walkSpecs(data.suites));
const counts = { passed: 0, failed: 0, skipped: 0, other: 0 };
for (const t of tests) {
  if (t.status === "passed" || t.status === "expected") counts.passed++;
  else if (t.status === "skipped") counts.skipped++;
  else if (t.status === "failed" || t.status === "timedOut" || t.status === "unexpected")
    counts.failed++;
  else counts.other++;
}

const byFile = new Map();
for (const t of tests) {
  const k = t.file;
  if (!byFile.has(k)) byFile.set(k, []);
  byFile.get(k).push(t);
}

const lines = [];
lines.push("# Round 11 — UI button QA report");
lines.push("");
lines.push(`**Generated**: ${new Date().toISOString()}  `);
lines.push(`**Total**: ${tests.length} button-level tests across 9 spec files  `);
lines.push(
  `**Result**: ${counts.passed} PASS / ${counts.failed} FAIL / ${counts.skipped} SKIP` +
    (counts.other ? ` / ${counts.other} OTHER` : "")
);
lines.push("");
lines.push("## Coverage by page");
lines.push("");

for (const [file, group] of [...byFile.entries()].sort()) {
  const pass = group.filter((t) => t.status === "passed" || t.status === "expected").length;
  const skip = group.filter((t) => t.status === "skipped").length;
  const fail = group.length - pass - skip;
  lines.push(`### \`${file}\` — ${pass} pass / ${fail} fail / ${skip} skip`);
  lines.push("");
  lines.push("| Status | Test | Duration |");
  lines.push("|---|---|---|");
  for (const t of group) {
    const emoji = EMOJI[t.status] ?? "❓";
    const dur = `${(t.durationMs / 1000).toFixed(1)}s`;
    lines.push(`| ${emoji} ${t.status} | ${t.name} | ${dur} |`);
  }
  lines.push("");
}

const fails = tests.filter(
  (t) => !["passed", "expected", "skipped"].includes(t.status)
);
if (fails.length) {
  lines.push("## Failures — detail");
  lines.push("");
  for (const t of fails) {
    lines.push(`### ${t.name}`);
    lines.push("");
    lines.push("```");
    lines.push((t.error ?? "").slice(0, 1500));
    lines.push("```");
    lines.push("");
  }
}

const skips = tests.filter((t) => t.status === "skipped");
if (skips.length) {
  lines.push("## Skipped — reasons");
  lines.push("");
  for (const t of skips) {
    lines.push(`- **${t.name}** — \`test.skip()\` invoked (no seeded data, no Orthanc-side resource, or guard branch).`);
  }
  lines.push("");
}

fs.writeFileSync(outPath, lines.join("\n"));
console.log(`Wrote ${outPath} (${tests.length} tests)`);
