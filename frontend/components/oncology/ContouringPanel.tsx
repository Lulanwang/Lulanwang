"use client";

import { useState } from "react";
import { Plus, Target, Trash2 } from "lucide-react";
import useSWR from "swr";
import { toast } from "sonner";
import { api, type Contour } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/cn";

const COLORS: Record<Contour["contour_type"], string> = {
  GTV: "#ef4444",
  CTV: "#f59e0b",
  PTV: "#10b981",
  OAR: "#3b82f6",
};

export function ContouringPanel({ planId }: { planId: string }) {
  const { data, isLoading, mutate } = useSWR(
    ["contours", planId],
    () => api.listContours(planId)
  );
  const [adding, setAdding] = useState(false);
  const [draftType, setDraftType] = useState<Contour["contour_type"]>("GTV");
  const [draftName, setDraftName] = useState("");
  const [draftVolume, setDraftVolume] = useState(0);

  async function add() {
    if (!draftName.trim()) {
      toast.warning("Name required");
      return;
    }
    try {
      await api.addContour(planId, {
        contour_type: draftType,
        name: draftName.trim(),
        color: COLORS[draftType],
        volume_cm3: draftVolume || null,
      });
      toast.success(`${draftType} added`);
      setAdding(false);
      setDraftName("");
      setDraftVolume(0);
      mutate();
    } catch (e) {
      toast.error("Failed to add", {
        description: e instanceof Error ? e.message : String(e),
      });
    }
  }

  async function remove(id: string) {
    try {
      await api.deleteContour(id);
      toast.success("Contour removed");
      mutate();
    } catch (e) {
      toast.error("Delete failed", {
        description: e instanceof Error ? e.message : String(e),
      });
    }
  }

  const grouped = (data ?? []).reduce<Record<string, Contour[]>>(
    (acc, c) => ({ ...acc, [c.contour_type]: [...(acc[c.contour_type] ?? []), c] }),
    {}
  );

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 border-b">
        <CardTitle className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          <Target className="h-3.5 w-3.5" />
          Contours
        </CardTitle>
        <Popover open={adding} onOpenChange={setAdding}>
          <PopoverTrigger asChild>
            <Button size="sm" variant="ghost" className="h-7 gap-1 px-2 text-[11px]">
              <Plus className="h-3 w-3" />
              Add
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-64 space-y-2">
            <div>
              <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                Type
              </div>
              <div className="flex gap-1">
                {(["GTV", "CTV", "PTV", "OAR"] as const).map((t) => (
                  <button
                    key={t}
                    onClick={() => setDraftType(t)}
                    className={cn(
                      "rounded-md border px-2 py-1 text-[10px] font-medium uppercase",
                      draftType === t
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border text-muted-foreground hover:bg-muted"
                    )}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
            <label className="block text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              Name
              <input
                value={draftName}
                onChange={(e) => setDraftName(e.target.value)}
                placeholder={
                  draftType === "OAR" ? "e.g. brainstem" : "e.g. primary tumor"
                }
                className="mt-1 w-full rounded-md border border-input bg-background px-2 py-1 text-xs normal-case"
              />
            </label>
            <label className="block text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              Volume cm³ (optional)
              <input
                type="number"
                step="0.1"
                value={draftVolume}
                onChange={(e) => setDraftVolume(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-input bg-background px-2 py-1 text-xs"
              />
            </label>
            <Button size="sm" onClick={add} className="w-full">
              Add contour
            </Button>
          </PopoverContent>
        </Popover>
      </CardHeader>
      <CardContent className="space-y-3 p-3">
        {isLoading && <Skeleton className="h-16 w-full" />}
        {!isLoading && data?.length === 0 && (
          <p className="px-1 py-3 text-center text-[10px] text-muted-foreground">
            No contours yet. Click + Add to start.
          </p>
        )}
        {(["GTV", "CTV", "PTV", "OAR"] as const).map(
          (t) =>
            grouped[t]?.length > 0 && (
              <div key={t}>
                <div className="mb-1 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                  <span
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ backgroundColor: COLORS[t] }}
                  />
                  {t}
                </div>
                <ul className="space-y-1">
                  {grouped[t].map((c) => (
                    <li
                      key={c.id}
                      className="flex items-center justify-between gap-2 rounded-md border bg-card px-2 py-1.5 text-xs"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-medium">{c.name}</div>
                        {c.volume_cm3 != null && c.volume_cm3 > 0 && (
                          <div className="text-[10px] text-muted-foreground">
                            {c.volume_cm3.toFixed(1)} cm³
                          </div>
                        )}
                      </div>
                      <Badge variant="outline" className="font-mono">
                        {t}
                      </Badge>
                      <button
                        onClick={() => remove(c.id)}
                        className="text-muted-foreground hover:text-destructive"
                        aria-label="Delete contour"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )
        )}
      </CardContent>
    </Card>
  );
}
