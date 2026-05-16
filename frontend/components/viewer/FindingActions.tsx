"use client";

import { useState } from "react";
import { api, Finding } from "@/lib/api";
import { DisclaimerBadge } from "@/components/DisclaimerBadge";

const STATUS_BADGE: Record<string, string> = {
  proposed: "bg-amber-100 text-amber-800 border-amber-300",
  accepted: "bg-emerald-100 text-emerald-800 border-emerald-300",
  rejected: "bg-red-100 text-red-700 border-red-300",
  modified: "bg-blue-100 text-blue-700 border-blue-300",
};

const SOURCE_BADGE: Record<string, string> = {
  ai: "bg-violet-100 text-violet-700 border-violet-300",
  radiologist: "bg-teal-100 text-teal-700 border-teal-300",
};

export function FindingCard({
  finding,
  onChanged,
  onStartRefine,
}: {
  finding: Finding;
  onChanged: () => void;
  onStartRefine: (f: Finding) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<Finding[] | null>(null);

  async function accept() {
    setBusy(true);
    try {
      await api.acceptFinding(finding.id);
      onChanged();
    } finally {
      setBusy(false);
    }
  }
  async function reject() {
    setBusy(true);
    try {
      await api.rejectFinding(finding.id);
      onChanged();
    } finally {
      setBusy(false);
    }
  }
  async function loadHistory() {
    if (history) {
      setShowHistory(!showHistory);
      return;
    }
    const h = await api.findingHistory(finding.id);
    setHistory(h);
    setShowHistory(true);
  }

  return (
    <div className="border-b last:border-0 py-2">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="text-sm">{finding.label}</div>
          <div className="mt-1 flex flex-wrap gap-1 items-center">
            <span
              className={`text-[10px] border rounded px-1.5 py-0.5 ${SOURCE_BADGE[finding.source]}`}
              title={`Source: ${finding.source}`}
            >
              {finding.source} v{finding.version}
            </span>
            <span
              className={`text-[10px] border rounded px-1.5 py-0.5 ${STATUS_BADGE[finding.status]}`}
            >
              {finding.status}
            </span>
            {finding.confidence !== null && (
              <DisclaimerBadge
                modelName={finding.model_name}
                modelVersion={finding.model_version}
                confidence={finding.confidence}
              />
            )}
            {finding.icd10_suggestion && (
              <span className="text-[10px] bg-blue-50 text-blue-700 border border-blue-200 rounded px-2 py-0.5">
                ICD-10 {finding.icd10_suggestion}
              </span>
            )}
            {finding.seg_sop_instance_uid && (
              <span
                className="text-[10px] bg-gray-100 text-gray-700 border border-gray-300 rounded px-2 py-0.5"
                title={finding.seg_sop_instance_uid}
              >
                DICOM SEG
              </span>
            )}
          </div>
        </div>
      </div>

      {finding.status === "proposed" && finding.is_current && (
        <div className="mt-2 flex gap-1">
          <button
            onClick={accept}
            disabled={busy}
            className="text-[11px] bg-emerald-700 hover:bg-emerald-800 text-white rounded px-2 py-0.5 disabled:opacity-50"
          >
            Accept
          </button>
          <button
            onClick={reject}
            disabled={busy}
            className="text-[11px] bg-red-700 hover:bg-red-800 text-white rounded px-2 py-0.5 disabled:opacity-50"
          >
            Reject
          </button>
          <button
            onClick={() => onStartRefine(finding)}
            disabled={busy}
            className="text-[11px] bg-blue-700 hover:bg-blue-800 text-white rounded px-2 py-0.5 disabled:opacity-50"
          >
            Refine
          </button>
        </div>
      )}

      {finding.status === "accepted" && finding.is_current && (
        <div className="mt-2 flex gap-1">
          <button
            onClick={() => onStartRefine(finding)}
            disabled={busy}
            className="text-[11px] bg-blue-700 hover:bg-blue-800 text-white rounded px-2 py-0.5 disabled:opacity-50"
          >
            Refine further
          </button>
        </div>
      )}

      <button
        onClick={loadHistory}
        className="mt-2 text-[10px] text-gray-500 hover:text-gray-800 underline"
      >
        {showHistory ? "Hide" : "Show"} version history (preserves AI original)
      </button>

      {showHistory && history && (
        <ol className="mt-2 border-l-2 border-gray-200 pl-3 space-y-1">
          {history.map((h) => (
            <li key={h.id} className="text-[11px]">
              <span className="font-mono text-gray-500">v{h.version}</span>{" "}
              <span
                className={`border rounded px-1 ${SOURCE_BADGE[h.source]} text-[10px]`}
              >
                {h.source}
              </span>{" "}
              <span
                className={`border rounded px-1 ${STATUS_BADGE[h.status]} text-[10px]`}
              >
                {h.status}
              </span>{" "}
              <span className="text-gray-700">{h.label}</span>
              <div className="text-gray-400">
                {new Date(h.created_at).toLocaleString()}
                {h.actor_id ? ` · ${h.actor_id.slice(0, 8)}` : ""}
                {h.confidence !== null ? ` · conf ${h.confidence.toFixed(2)}` : ""}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
