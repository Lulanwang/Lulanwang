"use client";

import { Eye, EyeOff, Sparkles } from "lucide-react";
import type { TwinStructure } from "@/lib/api";
import { cn } from "@/lib/cn";

export type StructureUIState = {
  visible: boolean;
  opacity: number;
};

type Props = {
  structures: TwinStructure[];
  state: Record<string, StructureUIState>;
  onChange: (name: string, patch: Partial<StructureUIState>) => void;
};

export function StructurePanel({ structures, state, onChange }: Props) {
  return (
    <div className="space-y-1">
      {structures.map((s) => {
        const st = state[s.name] ?? { visible: true, opacity: s.kind === "organ" ? 0.35 : 1 };
        const synthetic = s.synthetic_marker || s.synthetic_extrusion;
        return (
          <div
            key={s.name}
            className={cn(
              "flex items-center gap-2 rounded-md border bg-card p-2 text-xs",
              !st.visible && "opacity-60"
            )}
          >
            <button
              type="button"
              aria-label={st.visible ? `Hide ${s.name}` : `Show ${s.name}`}
              onClick={() => onChange(s.name, { visible: !st.visible })}
              className="rounded-md p-1 hover:bg-muted"
            >
              {st.visible ? (
                <Eye className="h-3.5 w-3.5" />
              ) : (
                <EyeOff className="h-3.5 w-3.5" />
              )}
            </button>
            <span
              className="inline-block h-3 w-3 shrink-0 rounded-sm border"
              style={{ background: s.color }}
              title={s.color}
            />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1">
                <span className="font-medium truncate">{prettyName(s)}</span>
                {synthetic && (
                  <Sparkles
                    className="h-3 w-3 text-amber-500"
                    aria-label="Synthesized marker"
                  />
                )}
              </div>
              <div className="text-[10px] text-muted-foreground">
                {s.volume_cm3.toFixed(1)} cm³ · {s.faces.toLocaleString()} faces
              </div>
            </div>
            <input
              type="range"
              aria-label={`${s.name} opacity`}
              min={0.05}
              max={1}
              step={0.05}
              value={st.opacity}
              onChange={(e) => onChange(s.name, { opacity: Number(e.target.value) })}
              className="w-16 accent-primary"
            />
          </div>
        );
      })}
    </div>
  );
}

function prettyName(s: TwinStructure): string {
  if (s.kind === "organ") return "Organ envelope";
  if (s.name.startsWith("lesion_")) {
    return `Lesion ${s.name.slice(7, 13)}…`;
  }
  return s.name;
}
