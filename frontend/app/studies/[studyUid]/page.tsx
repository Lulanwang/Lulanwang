"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import dynamic from "next/dynamic";
import { api, Finding } from "@/lib/api";
import { Toolbar } from "@/components/viewer/Toolbar";
import { FindingCard } from "@/components/viewer/FindingActions";
import type { ToolName } from "@/lib/cornerstone-init";

// Cornerstone3D depends on browser APIs (WebGL, Web Workers, WASM) so
// it MUST be loaded client-side only.
const CornerstoneViewer = dynamic(
  () => import("@/components/viewer/CornerstoneViewer").then((m) => m.CornerstoneViewer),
  { ssr: false, loading: () => <div className="text-xs text-gray-300 p-4">Loading viewer…</div> }
);

type Study = Awaited<ReturnType<typeof api.getStudy>>;
type Report = Awaited<ReturnType<typeof api.getReport>>;
type ICD = Awaited<ReturnType<typeof api.searchIcd10>>[number];

export default function StudyPage() {
  const params = useParams<{ studyUid: string }>();
  const studyId = params.studyUid;
  const [study, setStudy] = useState<Study | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [icdQuery, setIcdQuery] = useState("");
  const [icdResults, setIcdResults] = useState<ICD[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTool, setActiveTool] = useState<ToolName>("WindowLevel");
  const [slice, setSlice] = useState<{ idx: number; total: number } | null>(null);
  const [refining, setRefining] = useState<Finding | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [s, f] = await Promise.all([api.getStudy(studyId), api.listFindings(studyId)]);
      setStudy(s);
      setFindings(f);
      try {
        setReport(await api.getReport(studyId));
      } catch {
        setReport(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [studyId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const t = setTimeout(() => {
      api.searchIcd10(icdQuery).then(setIcdResults).catch(() => setIcdResults([]));
    }, 150);
    return () => clearTimeout(t);
  }, [icdQuery]);

  async function rerun() {
    setBusy(true);
    try {
      await api.runInference(studyId);
      for (let i = 0; i < 30; i++) {
        await new Promise((r) => setTimeout(r, 500));
        const s = await api.getStudy(studyId);
        if (["reported", "signed", "failed"].includes(s.state)) break;
      }
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function sign() {
    setBusy(true);
    try {
      await api.signReport(studyId);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function startRefine(f: Finding) {
    setRefining(f);
    setActiveTool("Brush");
  }

  async function saveRefinement() {
    if (!refining) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.set("label", `${refining.label} (refined)`);
      fd.set(
        "geometry",
        JSON.stringify({
          kind: "polygon",
          // Real implementation would extract the brush segmentation mask
          // from cornerstone-tools and append it as a .npy file. For this
          // skeleton we save the geometry sketch only; the backend's SEG
          // writer will fall back to the JSON sidecar if no mask is sent.
          ...(refining.geometry ?? {}),
          refined: true,
          tool: "brush",
        })
      );
      if (refining.icd10_suggestion) fd.set("icd10_suggestion", refining.icd10_suggestion);
      await api.refineFinding(refining.id, fd);
      setRefining(null);
      setActiveTool("WindowLevel");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (error) return <div className="text-sm text-red-600">{error}</div>;
  if (!study) return <div className="text-sm text-gray-500">Loading…</div>;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <section className="lg:col-span-2 bg-black rounded overflow-hidden flex flex-col" style={{ minHeight: 640 }}>
        <Toolbar active={activeTool} onChange={setActiveTool} />
        <div className="relative flex-1">
          <CornerstoneViewer
            studyInstanceUID={study.study_instance_uid}
            activeTool={activeTool}
            onSliceChange={(idx, total) => setSlice({ idx, total })}
          />
          {slice && (
            <div className="absolute right-2 bottom-2 text-[10px] bg-black/60 text-white rounded px-2 py-1">
              slice {slice.idx} / {slice.total}
            </div>
          )}
          {refining && (
            <div className="absolute left-2 top-12 right-2 bg-blue-900/80 text-white text-xs rounded px-3 py-2 flex items-center justify-between">
              <span>
                Refining <b>{refining.label}</b> · paint with the Brush tool, then save.
              </span>
              <div className="flex gap-1">
                <button
                  onClick={saveRefinement}
                  disabled={busy}
                  className="bg-emerald-600 hover:bg-emerald-700 rounded px-2 py-0.5"
                >
                  Save refinement
                </button>
                <button
                  onClick={() => {
                    setRefining(null);
                    setActiveTool("WindowLevel");
                  }}
                  className="bg-gray-700 hover:bg-gray-600 rounded px-2 py-0.5"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </section>

      <section className="space-y-4">
        <div className="bg-white border rounded p-3">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-sm">{study.description || "(no description)"}</h2>
            <span className="text-[10px] uppercase text-gray-500">{study.state}</span>
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {study.modality} · {study.body_part} · UID {study.study_instance_uid.slice(0, 24)}…
          </div>
          <div className="flex gap-2 mt-3">
            <button
              onClick={rerun}
              disabled={busy}
              className="text-xs bg-gray-900 text-white px-2 py-1 rounded disabled:opacity-50"
            >
              {busy ? "Working…" : "Re-run inference"}
            </button>
            <button
              onClick={sign}
              disabled={busy || !report}
              className="text-xs bg-emerald-700 text-white px-2 py-1 rounded disabled:opacity-50"
            >
              Sign report
            </button>
          </div>
        </div>

        <div className="bg-white border rounded p-3">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-semibold text-sm">Findings (current)</h3>
            <span className="text-[10px] text-gray-500">{findings.length}</span>
          </div>
          {findings.length === 0 && (
            <div className="text-xs text-gray-500">No findings yet.</div>
          )}
          {findings.map((f) => (
            <FindingCard
              key={f.id}
              finding={f}
              onChanged={refresh}
              onStartRefine={startRefine}
            />
          ))}
        </div>

        <div className="bg-white border rounded p-3">
          <h3 className="font-semibold text-sm mb-2">ICD-10 picker</h3>
          <input
            placeholder="Search code or description…"
            value={icdQuery}
            onChange={(e) => setIcdQuery(e.target.value)}
            className="w-full border rounded px-2 py-1 text-sm"
          />
          <ul className="mt-2 max-h-40 overflow-auto text-xs divide-y">
            {icdResults.slice(0, 20).map((c) => (
              <li key={c.code} className="py-1">
                <span className="font-mono text-gray-900">{c.code}</span>{" "}
                <span className="text-gray-600">{c.description}</span>
              </li>
            ))}
          </ul>
        </div>

        {report && (
          <div className="bg-white border rounded p-3">
            <h3 className="font-semibold text-sm mb-2">Draft report</h3>
            <pre className="whitespace-pre-wrap text-xs text-gray-800">{report.impression}</pre>
            <div className="mt-2 flex gap-2 flex-wrap">
              {report.sr_available && (
                <a
                  href={`/api/v1/reports/${report.id}/sr`}
                  className="text-xs bg-gray-100 px-2 py-1 rounded hover:bg-gray-200"
                >
                  Download DICOM SR
                </a>
              )}
              <a
                href={`/api/v1/reports/${report.id}/fhir`}
                className="text-xs bg-gray-100 px-2 py-1 rounded hover:bg-gray-200"
              >
                Download FHIR JSON
              </a>
            </div>
            <div className="mt-3 text-[10px] text-warn-700">
              Generated by AI. Requires licensed radiologist review and signature before clinical use.
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
