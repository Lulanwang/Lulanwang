"use client";

import { CheckCircle2, Edit3, Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { api, type TreatmentPlan } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const STATUS_VARIANT: Record<
  TreatmentPlan["status"],
  "secondary" | "success" | "warning"
> = {
  draft: "secondary",
  approved: "success",
  archived: "warning",
};

export function PlanHeader({
  plan,
  onChanged,
}: {
  plan: TreatmentPlan;
  onChanged: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState({
    name: plan.name,
    intent: plan.intent,
    modality: plan.modality,
    prescription_dose_gy: plan.prescription_dose_gy,
    fractions: plan.fractions,
  });

  async function save() {
    setBusy(true);
    try {
      await api.patchPlan(plan.id, draft);
      toast.success("Plan saved");
      setEditing(false);
      onChanged();
    } catch (e) {
      toast.error("Save failed", {
        description: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setBusy(false);
    }
  }

  async function approve() {
    setBusy(true);
    try {
      await api.approvePlan(plan.id);
      toast.success("Plan approved");
      onChanged();
    } catch (e) {
      toast.error("Approve failed", {
        description: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            {editing ? (
              <input
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-ring"
              />
            ) : (
              <h2 className="truncate text-sm font-semibold">{plan.name}</h2>
            )}
            <p className="mt-0.5 text-[10px] text-muted-foreground">
              Plan {plan.id.slice(0, 8)}
            </p>
          </div>
          <Badge variant={STATUS_VARIANT[plan.status]}>{plan.status}</Badge>
        </div>

        <div className="grid grid-cols-2 gap-3 text-xs">
          <Field label="Modality">
            {editing ? (
              <select
                value={draft.modality}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    modality: e.target.value as "proton" | "photon",
                  })
                }
                className="w-full rounded-md border border-input bg-background px-2 py-1 text-xs"
              >
                <option value="proton">proton</option>
                <option value="photon">photon</option>
              </select>
            ) : (
              <Badge variant="secondary">{plan.modality}</Badge>
            )}
          </Field>
          <Field label="Intent">
            {editing ? (
              <select
                value={draft.intent}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    intent: e.target.value as "curative" | "palliative",
                  })
                }
                className="w-full rounded-md border border-input bg-background px-2 py-1 text-xs"
              >
                <option value="curative">curative</option>
                <option value="palliative">palliative</option>
              </select>
            ) : (
              <Badge variant="secondary">{plan.intent}</Badge>
            )}
          </Field>
          <Field label="Prescription (Gy)">
            {editing ? (
              <input
                type="number"
                step="0.1"
                value={draft.prescription_dose_gy}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    prescription_dose_gy: Number(e.target.value),
                  })
                }
                className="w-full rounded-md border border-input bg-background px-2 py-1 text-xs"
              />
            ) : (
              <span className="font-mono tabular-nums">
                {plan.prescription_dose_gy.toFixed(1)} Gy
              </span>
            )}
          </Field>
          <Field label="Fractions">
            {editing ? (
              <input
                type="number"
                value={draft.fractions}
                onChange={(e) =>
                  setDraft({ ...draft, fractions: Number(e.target.value) })
                }
                className="w-full rounded-md border border-input bg-background px-2 py-1 text-xs"
              />
            ) : (
              <span className="font-mono tabular-nums">{plan.fractions}</span>
            )}
          </Field>
        </div>

        <div className="flex items-center gap-2">
          {editing ? (
            <>
              <Button size="sm" onClick={save} disabled={busy}>
                {busy ? <Loader2 className="animate-spin" /> : null}
                Save
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setEditing(false);
                  setDraft({
                    name: plan.name,
                    intent: plan.intent,
                    modality: plan.modality,
                    prescription_dose_gy: plan.prescription_dose_gy,
                    fractions: plan.fractions,
                  });
                }}
              >
                Cancel
              </Button>
            </>
          ) : (
            <>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setEditing(true)}
                disabled={plan.status === "archived"}
              >
                <Edit3 />
                Edit
              </Button>
              <Button
                size="sm"
                variant="success"
                onClick={approve}
                disabled={busy || plan.status === "approved"}
              >
                <CheckCircle2 />
                {plan.status === "approved" ? "Approved" : "Approve"}
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <div className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      {children}
    </div>
  );
}
