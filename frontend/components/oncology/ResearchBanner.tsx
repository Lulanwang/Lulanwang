import { ShieldAlert } from "lucide-react";

export function ResearchPlanBanner() {
  return (
    <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
      <div className="flex items-start gap-2">
        <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <p className="font-semibold uppercase tracking-wide">
            Research planning workspace
          </p>
          <p className="mt-0.5 leading-relaxed">
            NOT a treatment planning system. Doses are synthetic
            Gaussian-superposition illustrations — not Monte Carlo. Plans
            cannot be delivered to a real linac. Education / demonstration
            only.
          </p>
        </div>
      </div>
    </div>
  );
}
