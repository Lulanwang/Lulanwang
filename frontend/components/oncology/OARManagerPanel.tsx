"use client";

import { useState } from "react";
import { Activity, Plus, Trash2 } from "lucide-react";
import useSWR from "swr";
import { toast } from "sonner";
import { api, type Contour, type TreatmentPlan } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";

const STATUS_BG: Record<"pass" | "warn" | "fail", string> = {
  pass: "bg-success/10 text-success",
  warn: "bg-warning/15 text-warning",
  fail: "bg-destructive/15 text-destructive",
};

export function OARManagerPanel({ plan }: { plan: TreatmentPlan }) {
  const { data: catalog } = useSWR("oar-catalog", () => api.oarConstraints());
  const contours = useSWR(["contours", plan.id], () =>
    api.listContours(plan.id)
  );
  const oarContours = (contours.data ?? []).filter(
    (c) => c.contour_type === "OAR"
  );

  const [adding, setAdding] = useState(false);
  const [draftTissue, setDraftTissue] = useState("");

  async function addOarFromCatalog(tissue: string) {
    try {
      await api.addContour(plan.id, {
        contour_type: "OAR",
        name: tissue,
        color: "#3b82f6",
      });
      toast.success(`${tissue} added`);
      contours.mutate();
    } catch (e) {
      toast.error("Failed", {
        description: e instanceof Error ? e.message : String(e),
      });
    }
  }

  async function remove(id: string) {
    try {
      await api.deleteContour(id);
      contours.mutate();
    } catch (e) {
      toast.error("Delete failed", {
        description: e instanceof Error ? e.message : String(e),
      });
    }
  }

  const dose = plan.dose_summary;

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 border-b">
        <CardTitle className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          <Activity className="h-3.5 w-3.5" />
          OAR constraints
        </CardTitle>
        <Popover open={adding} onOpenChange={setAdding}>
          <PopoverTrigger asChild>
            <Button size="sm" variant="ghost" className="h-7 gap-1 px-2 text-[11px]">
              <Plus className="h-3 w-3" /> Add OAR
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-72 space-y-2">
            <input
              placeholder="Filter tissues…"
              value={draftTissue}
              onChange={(e) => setDraftTissue(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-2 py-1 text-xs"
              autoFocus
            />
            <div className="max-h-56 space-y-1 overflow-y-auto">
              {(catalog?.tissues ?? [])
                .filter((t) =>
                  t.toLowerCase().includes(draftTissue.toLowerCase())
                )
                .map((t) => (
                  <button
                    key={t}
                    onClick={() => {
                      addOarFromCatalog(t);
                      setAdding(false);
                    }}
                    className="w-full rounded px-2 py-1 text-left text-xs hover:bg-muted"
                  >
                    {t}
                  </button>
                ))}
            </div>
          </PopoverContent>
        </Popover>
      </CardHeader>
      <CardContent className="p-0">
        {contours.isLoading && <Skeleton className="m-3 h-16" />}
        {!contours.isLoading && oarContours.length === 0 && (
          <p className="px-3 py-4 text-center text-[10px] text-muted-foreground">
            No OARs yet. Add organs to evaluate constraints.
          </p>
        )}
        {oarContours.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="border-b text-left text-[10px] uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Tissue</th>
                  <th className="px-3 py-2 font-medium">Constraint</th>
                  <th className="px-3 py-2 font-medium">Observed</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {oarContours.map((c) => (
                  <OarRow
                    key={c.id}
                    contour={c}
                    doseSummary={dose?.global ?? null}
                    onRemove={() => remove(c.id)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!dose && oarContours.length > 0 && (
          <p className="border-t bg-muted/30 px-3 py-2 text-[10px] text-muted-foreground">
            Compute dose to see constraint evaluations. Using global dose
            summary as a fallback — assign per-OAR masks for accurate
            results.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function OarRow({
  contour,
  doseSummary,
  onRemove,
}: {
  contour: Contour;
  doseSummary: { mean: number; max: number; v20: number; v30: number } | null;
  onRemove: () => void;
}) {
  const { data: evaluations } = useSWR(
    doseSummary ? ["eval", contour.name, JSON.stringify(doseSummary)] : null,
    () =>
      api.evaluateConstraint(contour.name, {
        mean: doseSummary!.mean,
        max: doseSummary!.max,
        v20: doseSummary!.v20,
        v30: doseSummary!.v30,
      })
  );

  if (!evaluations || evaluations.length === 0) {
    return (
      <tr className="border-t">
        <td className="px-3 py-1.5">{contour.name}</td>
        <td className="px-3 py-1.5 text-muted-foreground">—</td>
        <td className="px-3 py-1.5 text-muted-foreground">—</td>
        <td className="px-3 py-1.5">
          <Badge variant="secondary">no constraint</Badge>
        </td>
        <td className="px-3 py-1.5 text-right">
          <button
            onClick={onRemove}
            className="text-muted-foreground hover:text-destructive"
            aria-label="Remove"
          >
            <Trash2 className="h-3 w-3" />
          </button>
        </td>
      </tr>
    );
  }

  return (
    <>
      {evaluations.map((e, i) => (
        <tr key={`${e.metric}-${i}`} className="border-t">
          {i === 0 ? (
            <td
              rowSpan={evaluations.length}
              className="px-3 py-1.5 align-top font-medium"
            >
              {contour.name}
            </td>
          ) : null}
          <td className="px-3 py-1.5">
            <span className="font-mono uppercase">{e.metric}</span> ≤{" "}
            <span className="tabular-nums">{e.limit_gy}</span>
            <span className="ml-1 text-[10px] text-muted-foreground">
              ({e.source})
            </span>
          </td>
          <td className="px-3 py-1.5 font-mono tabular-nums">{e.observed}</td>
          <td className="px-3 py-1.5">
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[10px] font-medium uppercase",
                STATUS_BG[e.status]
              )}
            >
              {e.status}
            </span>
          </td>
          {i === 0 ? (
            <td rowSpan={evaluations.length} className="px-3 py-1.5 text-right align-top">
              <button
                onClick={onRemove}
                className="text-muted-foreground hover:text-destructive"
                aria-label="Remove"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </td>
          ) : null}
        </tr>
      ))}
    </>
  );
}
