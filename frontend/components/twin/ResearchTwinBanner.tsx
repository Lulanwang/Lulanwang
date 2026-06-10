import { ShieldAlert } from "lucide-react";

export function ResearchTwinBanner() {
  return (
    <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
      <div className="flex items-start gap-2">
        <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <p className="font-semibold uppercase tracking-wide">
            Research-only digital twin
          </p>
          <p className="mt-0.5 leading-relaxed">
            NOT a validated anatomical model. The organ surface is built
            by classical computer vision (HU thresholds + Otsu +
            morphology + marching cubes) on the source DICOMs. Bbox-only
            lesions are shown as <em>synthesized ellipsoid markers</em>,
            not real segmentations. Use for visual demonstration only.
          </p>
        </div>
      </div>
    </div>
  );
}
