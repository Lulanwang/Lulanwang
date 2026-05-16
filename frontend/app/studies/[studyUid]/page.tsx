"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { DisclaimerBadge } from "@/components/DisclaimerBadge";

type Study = Awaited<ReturnType<typeof api.getStudy>>;
type Finding = Awaited<ReturnType<typeof api.listFindings>>[number];
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

  async function refresh() {
    try {
      const [s, f] = await Promise.all([api.getStudy(studyId), api.listFindings(studyId)]);
      setStudy(s);
      setFindings(f);
      try {
        setReport(await api.getReport(studyId));
      } catch {
        setReport(null);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studyId]);

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
      // Poll briefly for completion
      for (let i = 0; i < 30; i++) {
        await new Promise((r) => setTimeout(r, 500));
        const s = await api.getStudy(studyId);
        if (s.state === "reported" || s.state === "signed" || s.state === "failed") break;
      }
      await refresh();
    } catch (e: unknown) {
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
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (error) return <div className="text-sm text-red-600">{error}</div>;
  if (!study) return <div className="text-sm text-gray-500">Loading…</div>;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <section className="lg:col-span-2 bg-black rounded overflow-hidden" style={{ minHeight: 600 }}>
        <div className="text-xs text-gray-300 p-2">DICOM viewer (OHIF-style placeholder)</div>
        <iframe
          src={`/studies/${studyId}/viewer`}
          className="w-full"
          style={{ height: 580, border: 0, background: "#000" }}
        />
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
          <h3 className="font-semibold text-sm mb-2">AI findings</h3>
          {findings.length === 0 && (
            <div className="text-xs text-gray-500">No findings yet.</div>
          )}
          <ul className="space-y-2">
            {findings.map((f) => (
              <li key={f.id} className="border-b last:border-0 pb-2">
                <div className="text-sm">{f.label}</div>
                <div className="mt-1 flex items-center gap-2 flex-wrap">
                  <DisclaimerBadge
                    modelName={f.model_name}
                    modelVersion={f.model_version}
                    confidence={f.confidence}
                  />
                  {f.icd10_suggestion && (
                    <span className="text-[10px] bg-blue-50 text-blue-700 border border-blue-200 rounded px-2 py-0.5">
                      ICD-10 {f.icd10_suggestion}
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div className="bg-white border rounded p-3">
          <h3 className="font-semibold text-sm mb-2">ICD-10 picker</h3>
          <input
            placeholder="Search code or description…"
            value={icdQuery}
            onChange={(e) => setIcdQuery(e.target.value)}
            className="w-full border rounded px-2 py-1 text-sm"
          />
          <ul className="mt-2 max-h-48 overflow-auto text-xs divide-y">
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
            <div className="mt-2 flex gap-2">
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
