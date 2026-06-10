"use client";

import { useEffect, useState } from "react";
import { GripVertical, Layers } from "lucide-react";
import useSWR from "swr";
import { listSeries, type Series } from "@/lib/wadors-loader";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";

export function SeriesPanel({
  studyInstanceUID,
  activeSeriesUid,
  onSelect,
}: {
  studyInstanceUID: string;
  activeSeriesUid?: string;
  onSelect: (uid: string) => void;
}) {
  const { data, isLoading } = useSWR(
    studyInstanceUID ? ["series", studyInstanceUID] : null,
    () => listSeries(studyInstanceUID)
  );

  return (
    <Card className="h-fit">
      <CardHeader className="border-b">
        <CardTitle className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          <Layers className="h-3.5 w-3.5" /> Series
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-1.5 p-2">
        {isLoading && (
          <>
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </>
        )}
        {!isLoading && data && data.length === 0 && (
          <p className="px-2 py-3 text-[10px] text-muted-foreground">
            No series in this study.
          </p>
        )}
        {data?.map((s) => (
          <button
            key={s.seriesInstanceUID}
            draggable
            onDragStart={(e) =>
              e.dataTransfer.setData("text/x-series-uid", s.seriesInstanceUID)
            }
            onClick={() => onSelect(s.seriesInstanceUID)}
            className={cn(
              "group flex w-full items-center gap-2 rounded-md border bg-card p-2 text-left text-xs transition-colors",
              s.seriesInstanceUID === activeSeriesUid
                ? "border-primary/60 bg-primary/5"
                : "border-border hover:border-primary/30 hover:bg-muted"
            )}
            title="Drag onto a viewport, or click to load into the active cell"
          >
            <GripVertical className="h-3 w-3 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium">
                {s.seriesDescription || "(no description)"}
              </div>
              <div className="mt-0.5 flex items-center gap-1.5 text-muted-foreground">
                <Badge variant="secondary">{s.modality}</Badge>
                <span className="tabular-nums">{s.instanceCount} frames</span>
              </div>
            </div>
          </button>
        ))}
      </CardContent>
    </Card>
  );
}
