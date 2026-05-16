"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

type Study = Awaited<ReturnType<typeof api.listStudies>>[number];

const STATE_BADGES: Record<string, string> = {
  received: "bg-gray-100 text-gray-700",
  deidentified: "bg-blue-100 text-blue-700",
  queued: "bg-amber-100 text-amber-700",
  inferring: "bg-amber-100 text-amber-700 animate-pulse",
  inferred: "bg-emerald-100 text-emerald-700",
  reported: "bg-emerald-100 text-emerald-700",
  signed: "bg-emerald-200 text-emerald-800",
  failed: "bg-red-100 text-red-700",
};

export default function WorklistPage() {
  const [rows, setRows] = useState<Study[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listStudies()
      .then(setRows)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="text-sm text-red-600">{error}</div>;
  if (!rows) return <div className="text-sm text-gray-500">Loading worklist…</div>;
  if (rows.length === 0)
    return (
      <div className="text-sm text-gray-500">
        No studies yet. Run <code className="bg-gray-100 px-1 rounded">make seed</code> in the
        repo root to ingest pydicom sample studies.
      </div>
    );

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h1 className="text-lg font-semibold">Worklist</h1>
        <span className="text-xs text-gray-500">{rows.length} studies</span>
      </div>
      <table className="w-full text-sm bg-white border rounded">
        <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
          <tr>
            <th className="px-3 py-2">Description</th>
            <th className="px-3 py-2">Modality</th>
            <th className="px-3 py-2">Body part</th>
            <th className="px-3 py-2">Findings</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2" />
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-t">
              <td className="px-3 py-2 truncate max-w-xs">
                {r.description || (
                  <span className="text-gray-400">(no description)</span>
                )}
              </td>
              <td className="px-3 py-2">{r.modality}</td>
              <td className="px-3 py-2">{r.body_part}</td>
              <td className="px-3 py-2">{r.finding_count}</td>
              <td className="px-3 py-2">
                <span
                  className={`inline-block rounded px-2 py-0.5 text-[10px] font-medium ${
                    STATE_BADGES[r.state] || "bg-gray-100 text-gray-700"
                  }`}
                >
                  {r.state}
                </span>
              </td>
              <td className="px-3 py-2 text-right">
                <Link
                  href={`/studies/${r.id}`}
                  className="text-blue-700 hover:underline text-xs"
                >
                  Open →
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
