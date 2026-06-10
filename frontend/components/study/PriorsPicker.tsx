"use client";

import { useEffect, useState } from "react";
import { ArrowUpRight, History } from "lucide-react";
import useSWR from "swr";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";

export function PriorsPicker({
  open,
  onOpenChange,
  pseudonym,
  currentStudyId,
  onSelect,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  pseudonym: string | null;
  currentStudyId: string;
  onSelect: (studyId: string) => void;
}) {
  const { data, isLoading, error } = useSWR(
    open && pseudonym ? ["priors", pseudonym] : null,
    () => api.patientStudies(pseudonym!)
  );

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <History className="h-4 w-4 text-primary" />
            Prior studies
          </SheetTitle>
          <SheetDescription>
            All studies for patient pseudonym{" "}
            <code className="font-mono">{pseudonym?.slice(0, 12)}…</code>
          </SheetDescription>
        </SheetHeader>
        <div className="space-y-2 p-4">
          {isLoading &&
            Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          {error && (
            <div className="text-xs text-destructive">
              {error instanceof Error ? error.message : String(error)}
            </div>
          )}
          {data && data.length === 0 && (
            <EmptyState
              icon={History}
              title="No priors"
              description="This patient has no other studies in the system."
            />
          )}
          {data &&
            data.map((s) => (
              <div
                key={s.id}
                className="rounded-md border bg-card p-3 text-xs"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate font-medium">
                      {s.description || "(no description)"}
                    </div>
                    <div className="mt-0.5 text-muted-foreground">
                      {s.study_date
                        ? new Date(s.study_date).toLocaleDateString()
                        : "no date"}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-1">
                      <Badge variant="secondary">{s.modality}</Badge>
                      <span className="text-muted-foreground">
                        {s.body_part}
                      </span>
                      <span className="text-muted-foreground">·</span>
                      <span className="tabular-nums text-muted-foreground">
                        {s.finding_count} findings
                      </span>
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant={s.id === currentStudyId ? "secondary" : "outline"}
                    onClick={() => onSelect(s.id)}
                    disabled={s.id === currentStudyId}
                  >
                    {s.id === currentStudyId ? (
                      "current"
                    ) : (
                      <>
                        Compare
                        <ArrowUpRight />
                      </>
                    )}
                  </Button>
                </div>
              </div>
            ))}
        </div>
      </SheetContent>
    </Sheet>
  );
}
