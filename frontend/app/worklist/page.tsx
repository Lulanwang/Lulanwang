"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Inbox } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusPill } from "@/components/StatusPill";

type Study = Awaited<ReturnType<typeof api.listStudies>>[number];

export default function WorklistPage() {
  const [rows, setRows] = useState<Study[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listStudies()
      .then(setRows)
      .catch((e) => setError(e.message));
  }, []);

  if (error)
    return (
      <Card className="border-destructive/30">
        <CardContent className="pt-4 text-sm text-destructive">
          {error}
        </CardContent>
      </Card>
    );

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold">Worklist</h1>
          <p className="text-xs text-muted-foreground">
            Studies awaiting review or signoff.
          </p>
        </div>
        {rows && (
          <span className="text-xs text-muted-foreground">
            {rows.length} studies
          </span>
        )}
      </div>

      <Card>
        <CardHeader className="border-b">
          <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            All studies
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {!rows && (
            <div className="space-y-2 p-4">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          )}
          {rows && rows.length === 0 && (
            <EmptyState
              icon={Inbox}
              title="No studies yet"
              description="Run make seed in the repo root to ingest the pydicom sample studies."
              className="m-4"
            />
          )}
          {rows && rows.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b text-left text-[10px] uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 font-medium">Description</th>
                    <th className="px-4 py-2 font-medium">Modality</th>
                    <th className="px-4 py-2 font-medium">Body part</th>
                    <th className="px-4 py-2 font-medium">Findings</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr
                      key={r.id}
                      className={
                        i === 0
                          ? "border-t-0 hover:bg-muted/50"
                          : "border-t hover:bg-muted/50"
                      }
                    >
                      <td className="max-w-xs truncate px-4 py-2 font-medium">
                        {r.description || (
                          <span className="text-muted-foreground">
                            (no description)
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">
                        {r.modality}
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">
                        {r.body_part}
                      </td>
                      <td className="px-4 py-2 tabular-nums">
                        {r.finding_count}
                      </td>
                      <td className="px-4 py-2">
                        <StatusPill state={r.state} />
                      </td>
                      <td className="px-4 py-2 text-right">
                        <Link
                          href={`/studies/${r.id}`}
                          className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                        >
                          Open
                          <ArrowUpRight className="h-3 w-3" />
                        </Link>
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
