"use client";

import { useState } from "react";
import { Award, Loader2 } from "lucide-react";
import useSWR from "swr";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

// Mirror of backend rads.applicable_scheme()
function schemeFor(modality: string, bodyPart: string): string | null {
  const m = (modality || "").toUpperCase();
  const bp = (bodyPart || "").toUpperCase();
  if (m === "MG" || bp === "BREAST") return "BI-RADS";
  if (m === "CT" && ["CHEST", "LUNG", "THORAX"].includes(bp))
    return "Lung-RADS";
  if (m === "MR" && ["BRAIN", "HEAD"].includes(bp)) return "BT-RADS";
  return null;
}

export function RadsPicker({
  findingId,
  modality,
  bodyPart,
  current,
  onUpdated,
}: {
  findingId: string;
  modality: string;
  bodyPart: string;
  current?: { scheme: string; code: string; descriptor: string } | null;
  onUpdated: () => void;
}) {
  const scheme = schemeFor(modality, bodyPart);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const { data: schemes } = useSWR(
    open ? "rads-schemes" : null,
    () => api.radsSchemes()
  );

  if (!scheme) return null;

  async function setCode(code: string) {
    setBusy(true);
    try {
      await api.setFindingRads(findingId, scheme!, code);
      toast.success(`${scheme} ${code} set`);
      setOpen(false);
      onUpdated();
    } catch (e) {
      toast.error("RADS update failed", {
        description: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setBusy(false);
    }
  }

  const isCurrent = current && current.scheme === scheme;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide transition-colors",
            isCurrent
              ? "border-warning bg-warning/15 text-warning"
              : "border-border text-muted-foreground hover:border-primary/40 hover:text-foreground"
          )}
        >
          <Award className="h-3 w-3" />
          {isCurrent
            ? `${current!.scheme} ${current!.code}`
            : `Score · ${scheme}`}
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-xs font-semibold">{scheme}</p>
          {busy && <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />}
        </div>
        <div className="space-y-1">
          {schemes && schemes[scheme]?.map((c) => {
            const active = current?.code === c.code && isCurrent;
            return (
              <Button
                key={c.code}
                variant={active ? "default" : "ghost"}
                size="sm"
                onClick={() => setCode(c.code)}
                disabled={busy}
                className="w-full justify-start gap-2 text-left"
              >
                <Badge
                  variant={active ? "secondary" : "outline"}
                  className="font-mono"
                >
                  {c.code}
                </Badge>
                <span className="text-[11px] font-normal">{c.descriptor}</span>
              </Button>
            );
          })}
          {!schemes && (
            <div className="text-[10px] text-muted-foreground">Loading…</div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
