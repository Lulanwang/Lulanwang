"use client";

import { Calculator, Loader2, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { api, type TreatmentPlan } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function DoseSummaryCard({
  plan,
  onChanged,
}: {
  plan: TreatmentPlan;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const dose = plan.dose_summary;

  async function compute() {
    setBusy(true);
    try {
      await api.computeDose(plan.id);
      toast.success("Synthetic dose computed");
      onChanged();
    } catch (e) {
      toast.error("Compute failed", {
        description: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 border-b">
        <CardTitle className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          <Calculator className="h-3.5 w-3.5" />
          Dose summary
        </CardTitle>
        <Button
          size="sm"
          variant="default"
          onClick={compute}
          disabled={busy || (plan.beams ?? []).length === 0}
        >
          {busy ? <Loader2 className="animate-spin" /> : <Calculator />}
          Compute
        </Button>
      </CardHeader>
      <CardContent className="space-y-3 p-3">
        {!dose ? (
          <p className="px-1 py-2 text-center text-[10px] text-muted-foreground">
            No dose yet. Add beams and click Compute.
          </p>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <Metric label="Mean (Gy)" value={dose.global.mean.toFixed(1)} />
              <Metric label="Max (Gy)" value={dose.global.max.toFixed(1)} />
              <Metric
                label="V20 (%)"
                value={(dose.global.v20 * 100).toFixed(0)}
              />
              <Metric
                label="V30 (%)"
                value={(dose.global.v30 * 100).toFixed(0)}
              />
            </div>
            <div className="flex items-center justify-between gap-2 text-[10px] text-muted-foreground">
              <span>
                <Badge variant="ai">{dose.modality}</Badge>{" "}
                {dose.prescription_dose_gy} Gy ·{" "}
                {dose.grid_shape.join("×")} @ {dose.spacing_cm}cm
              </span>
              <span>
                {new Date(dose.computed_at).toLocaleTimeString()}
              </span>
            </div>
            <div className="rounded-md border border-warning/40 bg-warning/5 p-2 text-[10px] text-warning">
              <span className="inline-flex items-center gap-1">
                <ShieldAlert className="h-3 w-3" />
                {dose.disclaimer}
              </span>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-card p-2">
      <div className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="mt-0.5 text-base font-semibold tabular-nums">{value}</div>
    </div>
  );
}
