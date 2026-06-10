"use client";

import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";

type Row = Awaited<ReturnType<typeof api.listAudit>>[number];

const ACTION_VARIANT: Record<string, "success" | "warning" | "destructive" | "secondary" | "ai"> =
  {
    "auth.login": "success",
    "auth.failed": "destructive",
    "study.view": "secondary",
    "report.view": "secondary",
    "report.signed": "success",
    "report.narrative_generated": "ai",
    "inference.completed": "ai",
    "inference.failed": "destructive",
  };

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
      <Card className="border-destructive/30">
        <CardContent className="pt-4 text-sm text-destructive">
          {error}
          <div className="mt-1 text-xs text-muted-foreground">
            Admin role required.
          </div>
        </CardContent>
      </Card>
    );

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <ShieldCheck className="h-5 w-5 text-primary" /> Audit log
          </h1>
          <p className="text-xs text-muted-foreground">
            Append-only record of every authenticated action.
          </p>
        </div>
        {rows && (
          <span className="text-xs text-muted-foreground">
            {rows.length} recent events
          </span>
        )}
      </div>

      <Card>
        <CardHeader className="border-b">
          <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Events
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {!rows && (
            <div className="space-y-2 p-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          )}
          {rows && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="border-b text-left uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 font-medium">Time</th>
                    <th className="px-4 py-2 font-medium">Actor</th>
                    <th className="px-4 py-2 font-medium">Role</th>
                    <th className="px-4 py-2 font-medium">Action</th>
                    <th className="px-4 py-2 font-medium">Resource</th>
                    <th className="px-4 py-2 font-medium">IP</th>
                    <th className="px-4 py-2 font-medium">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id} className="border-t hover:bg-muted/50">
                      <td className="whitespace-nowrap px-4 py-1.5 text-muted-foreground">
                        {new Date(r.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-1.5 font-mono">
                        {r.actor_id?.slice(0, 8) || "—"}
                      </td>
                      <td className="px-4 py-1.5">{r.actor_role || "—"}</td>
                      <td className="px-4 py-1.5">
                        <Badge
                          variant={ACTION_VARIANT[r.action] || "secondary"}
                        >
                          {r.action}
                        </Badge>
                      </td>
                      <td className="max-w-xs truncate px-4 py-1.5 font-mono text-muted-foreground">
                        {r.resource_type
                          ? `${r.resource_type}:${r.resource_id?.slice(0, 12)}`
                          : "—"}
                      </td>
                      <td className="px-4 py-1.5 text-muted-foreground">
                        {r.ip || "—"}
                      </td>
                      <td className="max-w-md truncate px-4 py-1.5 font-mono text-muted-foreground">
                        {r.details ? JSON.stringify(r.details) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
