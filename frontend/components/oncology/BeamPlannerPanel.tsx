"use client";

import { useState } from "react";
import { Plus, Radio, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, type Beam, type TreatmentPlan } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { BeamAngleVisualizer } from "./BeamAngleVisualizer";

export function BeamPlannerPanel({
  plan,
  onChanged,
}: {
  plan: TreatmentPlan;
  onChanged: () => void;
}) {
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState<Beam>({
    gantry_angle: 0,
    couch_angle: 0,
    collimator_angle: 0,
    energy_mev: plan.modality === "proton" ? 100 : 6,
    mu: 100,
    weight: 1,
  });

  const beams = plan.beams ?? [];

  async function add() {
    try {
      const next: Beam[] = [
        ...beams,
        { ...draft, id: crypto.randomUUID().slice(0, 8) },
      ];
      await api.patchPlan(plan.id, { beams: next });
      toast.success("Beam added");
      setAdding(false);
      onChanged();
    } catch (e) {
      toast.error("Add beam failed", {
        description: e instanceof Error ? e.message : String(e),
      });
    }
  }

  async function remove(i: number) {
    const next = beams.filter((_, idx) => idx !== i);
    try {
      await api.patchPlan(plan.id, { beams: next });
      toast.success("Beam removed");
      onChanged();
    } catch (e) {
      toast.error("Remove failed", {
        description: e instanceof Error ? e.message : String(e),
      });
    }
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 border-b">
        <CardTitle className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          <Radio className="h-3.5 w-3.5" />
          Beams · {plan.modality}
        </CardTitle>
        <Popover open={adding} onOpenChange={setAdding}>
          <PopoverTrigger asChild>
            <Button size="sm" variant="ghost" className="h-7 gap-1 px-2 text-[11px]">
              <Plus className="h-3 w-3" />
              Add
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-72 space-y-2">
            <NumField
              label="Gantry angle (°)"
              value={draft.gantry_angle}
              onChange={(v) => setDraft({ ...draft, gantry_angle: v })}
              min={0}
              max={359}
            />
            <NumField
              label="Couch angle (°)"
              value={draft.couch_angle ?? 0}
              onChange={(v) => setDraft({ ...draft, couch_angle: v })}
              min={-90}
              max={90}
            />
            <NumField
              label="Energy (MeV)"
              value={draft.energy_mev ?? 6}
              onChange={(v) => setDraft({ ...draft, energy_mev: v })}
              min={1}
            />
            <NumField
              label="MU"
              value={draft.mu ?? 100}
              onChange={(v) => setDraft({ ...draft, mu: v })}
              min={1}
            />
            <NumField
              label="Weight"
              value={draft.weight ?? 1}
              onChange={(v) => setDraft({ ...draft, weight: v })}
              min={0}
              step={0.1}
            />
            <Button size="sm" onClick={add} className="w-full">
              Add beam
            </Button>
          </PopoverContent>
        </Popover>
      </CardHeader>
      <CardContent className="space-y-3 p-3">
        <BeamAngleVisualizer beams={beams} />

        {beams.length === 0 ? (
          <p className="px-1 py-2 text-center text-[10px] text-muted-foreground">
            Add at least one beam, then Compute dose.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="border-b text-left text-[10px] uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-2 py-1 font-medium">Gantry</th>
                  <th className="px-2 py-1 font-medium">Couch</th>
                  <th className="px-2 py-1 font-medium">Energy</th>
                  <th className="px-2 py-1 font-medium">MU</th>
                  <th className="px-2 py-1 font-medium">Weight</th>
                  <th className="px-2 py-1" />
                </tr>
              </thead>
              <tbody>
                {beams.map((b, i) => (
                  <tr key={i} className="border-t">
                    <td className="px-2 py-1 font-mono tabular-nums">
                      {Math.round(b.gantry_angle)}°
                    </td>
                    <td className="px-2 py-1 font-mono tabular-nums">
                      {Math.round(b.couch_angle ?? 0)}°
                    </td>
                    <td className="px-2 py-1 font-mono tabular-nums">
                      {b.energy_mev ?? 0} MeV
                    </td>
                    <td className="px-2 py-1 font-mono tabular-nums">
                      {b.mu ?? 0}
                    </td>
                    <td className="px-2 py-1 font-mono tabular-nums">
                      {(b.weight ?? 1).toFixed(2)}
                    </td>
                    <td className="px-2 py-1 text-right">
                      <button
                        onClick={() => remove(i)}
                        className="text-muted-foreground hover:text-destructive"
                        aria-label="Remove beam"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function NumField({
  label,
  value,
  onChange,
  min,
  max,
  step,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
}) {
  return (
    <label className="block text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
      {label}
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step ?? 1}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-1 w-full rounded-md border border-input bg-background px-2 py-1 text-xs normal-case"
      />
    </label>
  );
}
