"use client";

import { useState } from "react";
import { Loader2, ShieldAlert, Sparkles } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";

export function ChangeReportDrawer({
  open,
  onOpenChange,
  pseudonym,
  baselineId,
  followUpId,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  pseudonym: string;
  baselineId: string;
  followUpId: string;
}) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{
    text: string | null;
    model_id: string;
    backend: string;
    error: string | null;
  } | null>(null);

  async function generate() {
    setBusy(true);
    setResult(null);
    try {
      const r = await api.patientChangeReport(pseudonym, baselineId, followUpId);
      setResult(r);
    } catch (e) {
      setResult({
        text: null,
        model_id: "",
        backend: "?",
        error: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-lg">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" /> Longitudinal change
            report
          </SheetTitle>
          <SheetDescription>
            MedGemma compares the two selected timepoints.
          </SheetDescription>
        </SheetHeader>
        <div className="space-y-3 p-4">
          <div className="rounded-md bg-warning/10 px-3 py-2 text-[10px] text-warning">
            <span className="inline-flex items-center gap-1">
              <ShieldAlert className="h-3 w-3" /> RESEARCH ONLY — unverified
              AI-generated comparison.
            </span>
          </div>
          <Button
            onClick={generate}
            disabled={busy}
            className="w-full"
            variant="default"
          >
            {busy ? (
              <Loader2 className="animate-spin" />
            ) : (
              <Sparkles />
            )}
            {busy ? "Generating…" : "Generate change report"}
          </Button>

          {result?.text && (
            <div className="rounded-md border border-warning/40 bg-warning/5 p-3">
              <div className="mb-2 flex items-center gap-2 text-xs">
                <Badge variant="ai">MedGemma · {result.backend}</Badge>
              </div>
              <pre className="whitespace-pre-wrap font-sans text-xs">
                {result.text}
              </pre>
              <div className="mt-3 border-t border-warning/30 pt-2 text-[10px] text-muted-foreground">
                <code className="font-mono">{result.model_id}</code>
              </div>
            </div>
          )}
          {result?.error && (
            <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
              {result.error}
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
