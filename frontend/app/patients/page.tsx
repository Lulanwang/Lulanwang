"use client";

import Link from "next/link";
import useSWR from "swr";
import { ArrowUpRight, Users } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";

export default function PatientsPage() {
  const { data, error, isLoading } = useSWR("patients", () => api.listPatients());

  return (
    <div className="space-y-4">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold">
          <Users className="h-5 w-5 text-primary" /> Patients
        </h1>
        <p className="text-xs text-muted-foreground">
          De-identified pseudonyms — no PatientID is stored or surfaced.
        </p>
      </div>

      {error && (
        <Card className="border-destructive/30">
          <CardContent className="pt-4 text-sm text-destructive">
            {error instanceof Error ? error.message : String(error)}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="border-b">
          <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Cohort
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading && (
            <div className="space-y-2 p-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          )}
          {data && data.length === 0 && (
            <EmptyState
              icon={Users}
              title="No patients yet"
              description="Run make seed to ingest sample studies."
              className="m-4"
            />
          )}
          {data && data.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b text-left text-[10px] uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 font-medium">Pseudonym</th>
                    <th className="px-4 py-2 font-medium">Studies</th>
                    <th className="px-4 py-2 font-medium">First study</th>
                    <th className="px-4 py-2 font-medium">Last study</th>
                    <th className="px-4 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {data.map((p) => (
                    <tr
                      key={p.pseudonym}
                      className="border-t hover:bg-muted/50"
                    >
                      <td className="px-4 py-2 font-mono text-xs">
                        {p.pseudonym.slice(0, 16)}…
                      </td>
                      <td className="px-4 py-2 tabular-nums">
                        <Badge variant="secondary">{p.study_count}</Badge>
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">
                        {p.first_study_at
                          ? new Date(p.first_study_at).toLocaleDateString()
                          : "—"}
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">
                        {p.last_study_at
                          ? new Date(p.last_study_at).toLocaleDateString()
                          : "—"}
                      </td>
                      <td className="px-4 py-2 text-right">
                        <Link
                          href={`/patients/${encodeURIComponent(p.pseudonym)}`}
                          className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                        >
                          Timeline
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
