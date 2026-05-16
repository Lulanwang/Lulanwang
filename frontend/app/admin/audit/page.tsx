"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Row = Awaited<ReturnType<typeof api.listAudit>>[number];

export default function AuditPage() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listAudit()
      .then(setRows)
      .catch((e) => setError(e.message));
  }, []);

  if (error)
    return (
      <div className="text-sm text-red-600">
        {error}
        <div className="text-gray-500 text-xs mt-1">Admin role required.</div>
      </div>
    );
  if (!rows) return <div className="text-sm text-gray-500">Loading audit log…</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h1 className="text-lg font-semibold">Audit log</h1>
        <span className="text-xs text-gray-500">{rows.length} recent events</span>
      </div>
      <div className="overflow-x-auto bg-white border rounded">
        <table className="w-full text-xs">
          <thead className="bg-gray-50 text-left uppercase text-gray-500">
            <tr>
              <th className="px-3 py-2">Time</th>
              <th className="px-3 py-2">Actor</th>
              <th className="px-3 py-2">Role</th>
              <th className="px-3 py-2">Action</th>
              <th className="px-3 py-2">Resource</th>
              <th className="px-3 py-2">IP</th>
              <th className="px-3 py-2">Details</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t">
                <td className="px-3 py-1 whitespace-nowrap text-gray-700">
                  {new Date(r.created_at).toLocaleString()}
                </td>
                <td className="px-3 py-1 font-mono">{r.actor_id?.slice(0, 8) || "—"}</td>
                <td className="px-3 py-1">{r.actor_role || "—"}</td>
                <td className="px-3 py-1 font-medium">{r.action}</td>
                <td className="px-3 py-1 truncate max-w-xs">
                  {r.resource_type ? `${r.resource_type}:${r.resource_id?.slice(0, 12)}` : "—"}
                </td>
                <td className="px-3 py-1">{r.ip || "—"}</td>
                <td className="px-3 py-1 text-gray-500 truncate max-w-md">
                  {r.details ? JSON.stringify(r.details) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
