"use client";

import { useState } from "react";
import {
  Check,
  History,
  Pencil,
  Sparkles,
  User,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { api, Finding } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RadsPicker } from "@/components/finding/RadsPicker";

const STATUS_VARIANT: Record<
  string,
  "warning" | "success" | "destructive" | "default"
> = {
  proposed: "warning",
  accepted: "success",
  rejected: "destructive",
  modified: "default",
};

export function FindingCard({
  finding,
  onChanged,
  onStartRefine,
  modality,
}: {
  finding: Finding;
  onChanged: () => void;
  onStartRefine: (f: Finding) => void;
  modality?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<Finding[] | null>(null);

  async function accept() {
    setBusy(true);
    try {
      await api.acceptFinding(finding.id);
      toast.success("Finding accepted", { description: finding.label });
      onChanged();
    } catch (e) {
      toast.error("Accept failed", {
        description: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setBusy(false);
    }
  }
  async function reject() {
    setBusy(true);
    try {
      await api.rejectFinding(finding.id);
      toast.success("Finding rejected", { description: finding.label });
      onChanged();
    } catch (e) {
      toast.error("Reject failed", {
        description: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setBusy(false);
    }
  }
  async function loadHistory() {
    if (history) {
      setShowHistory(!showHistory);
      return;
    }
    const h = await api.findingHistory(finding.id);
    setHistory(h);
    setShowHistory(true);
  }

  return (
    <div className="border-b py-3 last:border-0">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="text-sm font-medium">{finding.label}</div>
          <div className="mt-1.5 flex flex-wrap items-center gap-1">
            <Badge variant={finding.source === "ai" ? "ai" : "secondary"}>
              {finding.source === "ai" ? <Sparkles /> : <User />}
              {finding.source} v{finding.version}
            </Badge>
            <Badge variant={STATUS_VARIANT[finding.status] || "default"}>
              {finding.status}
            </Badge>
            {finding.confidence !== null && (
              <Badge variant="outline">
                {finding.model_name} · {finding.confidence.toFixed(2)}
              </Badge>
            )}
            {finding.icd10_suggestion && (
              <Badge variant="default">
                ICD-10 {finding.icd10_suggestion}
              </Badge>
            )}
            {finding.seg_sop_instance_uid && (
              <Badge
                variant="secondary"
                title={finding.seg_sop_instance_uid}
              >
                DICOM SEG
              </Badge>
            )}
            {finding.is_current && (
              <RadsPicker
                findingId={finding.id}
                modality={modality ?? ""}
                bodyPart={finding.body_part}
                current={
                  (finding.geometry as { rads?: { scheme: string; code: string; descriptor: string } } | null)?.rads ??
                  null
                }
                onUpdated={onChanged}
              />
            )}
          </div>
        </div>
      </div>

      {finding.status === "proposed" && finding.is_current && (
        <div className="mt-3 flex gap-1">
          <Button size="sm" variant="success" onClick={accept} disabled={busy}>
            <Check />
            Accept
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={reject}
            disabled={busy}
          >
            <X />
            Reject
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onStartRefine(finding)}
            disabled={busy}
          >
            <Pencil />
            Refine
          </Button>
        </div>
      )}

      {finding.status === "accepted" && finding.is_current && (
        <div className="mt-3 flex gap-1">
          <Button
            size="sm"
            variant="outline"
            onClick={() => onStartRefine(finding)}
            disabled={busy}
          >
            <Pencil />
            Refine further
          </Button>
        </div>
      )}

      <button
        onClick={loadHistory}
        className="mt-2 inline-flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground"
      >
        <History className="h-3 w-3" />
        {showHistory ? "Hide" : "Show"} version history (preserves AI original)
      </button>

      {showHistory && history && (
        <ol className="mt-2 space-y-1 border-l-2 border-border pl-3">
          {history.map((h) => (
            <li key={h.id} className="text-[11px]">
              <span className="font-mono text-muted-foreground">
                v{h.version}
              </span>{" "}
              <Badge variant={h.source === "ai" ? "ai" : "secondary"}>
                {h.source}
              </Badge>{" "}
              <Badge variant={STATUS_VARIANT[h.status] || "default"}>
                {h.status}
              </Badge>{" "}
              <span className="text-foreground">{h.label}</span>
              <div className="text-muted-foreground">
                {h.created_at && new Date(h.created_at).toLocaleString()}
                {h.actor_id ? ` · ${h.actor_id.slice(0, 8)}` : ""}
                {h.confidence !== null
                  ? ` · conf ${h.confidence.toFixed(2)}`
                  : ""}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
