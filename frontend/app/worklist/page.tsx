"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpRight,
  Inbox,
  RefreshCcw,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusPill } from "@/components/StatusPill";
import {
  FilterSidebar,
  type WorklistFilters,
} from "@/components/worklist/FilterSidebar";
import { StudyThumbnail } from "@/components/worklist/StudyThumbnail";
import { cn } from "@/lib/cn";

type Study = Awaited<ReturnType<typeof api.listStudies>>[number];

type SortCol = "study_date" | "modality" | "body_part" | "state";

export default function WorklistPage() {
  const [filters, setFilters] = useState<WorklistFilters>({});
  const [sort, setSort] = useState<SortCol>("study_date");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const queryParams = useMemo(
    () => ({ ...filters, sort, order }),
    [filters, sort, order]
  );

  const { data, error, isLoading, mutate } = useSWR(
    ["studies", queryParams],
    () => api.listStudies(queryParams)
  );

  function toggleSort(col: SortCol) {
    if (sort === col) {
      setOrder((o) => (o === "asc" ? "desc" : "asc"));
    } else {
      setSort(col);
      setOrder("desc");
    }
  }

  function toggleSelected(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAll(visible: Study[]) {
    if (selected.size === visible.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(visible.map((s) => s.id)));
    }
  }

  async function rerunSelected() {
    if (selected.size === 0) return;
    const ids = [...selected];
    toast.info(`Re-running inference on ${ids.length} studies…`);
    const results = await Promise.allSettled(
      ids.map((id) => api.runInference(id))
    );
    const ok = results.filter((r) => r.status === "fulfilled").length;
    const failed = results.length - ok;
    if (failed === 0) {
      toast.success(`Queued ${ok} jobs`);
    } else {
      toast.warning(`Queued ${ok}, ${failed} failed`);
    }
    setSelected(new Set());
    mutate();
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
      <FilterSidebar filters={filters} onChange={setFilters} />

      <div className="space-y-3">
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-xl font-semibold">Worklist</h1>
            <p className="text-xs text-muted-foreground">
              Studies awaiting review or signoff.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {selected.size > 0 && (
              <Button
                size="sm"
                variant="default"
                onClick={rerunSelected}
                disabled={isLoading}
              >
                <RefreshCcw />
                Re-run ({selected.size})
              </Button>
            )}
            {data && (
              <span className="text-xs text-muted-foreground">
                {data.length} {data.length === 1 ? "study" : "studies"}
              </span>
            )}
          </div>
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
              Studies
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {isLoading && (
              <div className="space-y-2 p-4">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            )}
            {data && data.length === 0 && (
              <EmptyState
                icon={Inbox}
                title="No studies match"
                description={
                  Object.keys(filters).length
                    ? "Try widening or clearing the filters."
                    : "Run make seed in the repo root to ingest sample studies."
                }
                className="m-4"
              />
            )}
            {data && data.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b text-left text-[10px] uppercase tracking-wide text-muted-foreground">
                    <tr>
                      <th className="w-8 px-3 py-2">
                        <input
                          type="checkbox"
                          aria-label="Select all"
                          checked={
                            data.length > 0 && selected.size === data.length
                          }
                          onChange={() => selectAll(data)}
                          className="h-3.5 w-3.5 rounded border-border"
                        />
                      </th>
                      <th className="w-14 px-3 py-2">Thumb</th>
                      <th className="px-3 py-2 font-medium">Description</th>
                      <SortableTh
                        col="modality"
                        active={sort}
                        order={order}
                        onClick={() => toggleSort("modality")}
                      >
                        Modality
                      </SortableTh>
                      <SortableTh
                        col="body_part"
                        active={sort}
                        order={order}
                        onClick={() => toggleSort("body_part")}
                      >
                        Body part
                      </SortableTh>
                      <th className="px-3 py-2 font-medium">Findings</th>
                      <SortableTh
                        col="state"
                        active={sort}
                        order={order}
                        onClick={() => toggleSort("state")}
                      >
                        Status
                      </SortableTh>
                      <th className="px-3 py-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {data.map((r) => (
                      <tr
                        key={r.id}
                        className={cn(
                          "border-t hover:bg-muted/50",
                          selected.has(r.id) && "bg-primary/5"
                        )}
                      >
                        <td className="px-3 py-2">
                          <input
                            type="checkbox"
                            aria-label={`Select study ${r.id}`}
                            checked={selected.has(r.id)}
                            onChange={() => toggleSelected(r.id)}
                            className="h-3.5 w-3.5 rounded border-border"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <StudyThumbnail studyId={r.id} />
                        </td>
                        <td className="max-w-sm truncate px-3 py-2 font-medium">
                          {r.description || (
                            <span className="text-muted-foreground">
                              (no description)
                            </span>
                          )}
                          <div className="mt-0.5 font-mono text-[10px] text-muted-foreground">
                            {r.study_instance_uid.slice(0, 24)}…
                          </div>
                        </td>
                        <td className="px-3 py-2 text-muted-foreground">
                          {r.modality}
                        </td>
                        <td className="px-3 py-2 text-muted-foreground">
                          {r.body_part}
                        </td>
                        <td className="px-3 py-2 tabular-nums">
                          {r.finding_count}
                        </td>
                        <td className="px-3 py-2">
                          <StatusPill state={r.state} />
                        </td>
                        <td className="px-3 py-2 text-right">
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
    </div>
  );
}

function SortableTh({
  col,
  active,
  order,
  onClick,
  children,
}: {
  col: SortCol;
  active: SortCol;
  order: "asc" | "desc";
  onClick: () => void;
  children: React.ReactNode;
}) {
  const isActive = active === col;
  return (
    <th className="px-3 py-2 font-medium">
      <button
        onClick={onClick}
        className={cn(
          "inline-flex items-center gap-1 hover:text-foreground",
          isActive && "text-foreground"
        )}
      >
        {children}
        {isActive &&
          (order === "asc" ? (
            <ArrowUp className="h-3 w-3" />
          ) : (
            <ArrowDown className="h-3 w-3" />
          ))}
      </button>
    </th>
  );
}
