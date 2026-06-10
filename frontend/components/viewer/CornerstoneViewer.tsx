"use client";

import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import {
  Enums,
  RenderingEngine,
  Types,
  metaData,
} from "@cornerstonejs/core";
import {
  ensureCornerstone,
  getOrCreateToolGroup,
  setActiveTool,
  TOOL_NAMES,
  ToolName,
} from "@/lib/cornerstone-init";
import {
  buildStackImageIds,
  imageIdFor,
  listInstances,
  listSeries,
  Series,
} from "@/lib/wadors-loader";

/**
 * 2D stack viewer for a single study + optional explicit series.
 *
 * Each instance owns a unique cornerstone viewport so multiple viewers
 * can render side-by-side (Phase 9.A multi-viewport grid). Parents get
 * an imperative handle via forwardRef so cine controls + sync-scroll
 * can drive the viewer without prop churn.
 */

type Preset = { label: string; ww: number; wc: number };

const PRESETS: Record<string, Preset[]> = {
  CT: [
    { label: "Soft Tissue", ww: 400, wc: 40 },
    { label: "Lung", ww: 1500, wc: -600 },
    { label: "Bone", ww: 2000, wc: 300 },
    { label: "Brain", ww: 80, wc: 40 },
  ],
  MR: [
    { label: "Default", ww: 1200, wc: 600 },
    { label: "T1", ww: 1000, wc: 500 },
    { label: "T2", ww: 2000, wc: 1000 },
  ],
  MG: [
    { label: "Mammo", ww: 4096, wc: 2048 },
    { label: "Bright", ww: 2000, wc: 1500 },
  ],
};

const RENDERER_ID = "lulan-renderer";

export type ViewerHandle = {
  getSliceIndex: () => number;
  getTotalSlices: () => number;
  setSliceIndex: (idx: number) => void;
  jumpRelative: (delta: number) => void;
};

export type ViewerProps = {
  studyInstanceUID: string;
  activeTool: ToolName;
  /** Unique viewport id — distinguishes cells in a multi-viewport grid. */
  viewportId?: string;
  /** Pin this viewer to a specific series; if omitted, picks the longest imaging series. */
  seriesInstanceUID?: string;
  onSliceChange?: (idx: number, total: number) => void;
  onModalityDetected?: (modality: string) => void;
};

export const CornerstoneViewer = forwardRef<ViewerHandle, ViewerProps>(
  function CornerstoneViewer(
    {
      studyInstanceUID,
      activeTool,
      viewportId,
      seriesInstanceUID,
      onSliceChange,
      onModalityDetected,
    },
    ref
  ) {
    const elementRef = useRef<HTMLDivElement>(null);
    const engineRef = useRef<RenderingEngine | null>(null);
    const viewportIdRef = useRef(viewportId || "lulan-viewport");
    const totalRef = useRef(0);
    const [series, setSeries] = useState<Series[]>([]);
    const [primary, setPrimary] = useState<Series | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    useImperativeHandle(ref, () => ({
      getSliceIndex: () => {
        const engine = engineRef.current;
        if (!engine) return 0;
        const v = engine.getViewport(
          viewportIdRef.current
        ) as Types.IStackViewport;
        return v?.getCurrentImageIdIndex?.() ?? 0;
      },
      getTotalSlices: () => totalRef.current,
      setSliceIndex: (idx: number) => {
        const engine = engineRef.current;
        if (!engine || totalRef.current === 0) return;
        const v = engine.getViewport(
          viewportIdRef.current
        ) as Types.IStackViewport;
        const clamped = Math.max(0, Math.min(idx, totalRef.current - 1));
        v.setImageIdIndex(clamped);
        v.render();
      },
      jumpRelative: (delta: number) => {
        const engine = engineRef.current;
        if (!engine || totalRef.current === 0) return;
        const v = engine.getViewport(
          viewportIdRef.current
        ) as Types.IStackViewport;
        const cur = v.getCurrentImageIdIndex();
        const next = Math.max(
          0,
          Math.min(cur + delta, totalRef.current - 1)
        );
        v.setImageIdIndex(next);
        v.render();
      },
    }));

    // Initial mount + reload when study or pinned series changes
    useEffect(() => {
      let cancelled = false;
      (async () => {
        try {
          setLoading(true);
          setError(null);
          await ensureCornerstone();

          let resolvedSeries: Series[];
          let resolvedPrimary: Series | null;
          let imageIds: string[];

          if (seriesInstanceUID) {
            const allSeries = await listSeries(studyInstanceUID);
            resolvedSeries = allSeries;
            resolvedPrimary =
              allSeries.find(
                (s) => s.seriesInstanceUID === seriesInstanceUID
              ) ?? null;
            if (!resolvedPrimary) {
              if (!cancelled) {
                setError("Pinned series not found in study.");
                setLoading(false);
              }
              return;
            }
            const sops = await listInstances(
              studyInstanceUID,
              seriesInstanceUID
            );
            imageIds = sops.map((s) =>
              imageIdFor(studyInstanceUID, seriesInstanceUID, s)
            );
          } else {
            const built = await buildStackImageIds(studyInstanceUID);
            resolvedSeries = built.series;
            resolvedPrimary = built.primary;
            imageIds = built.imageIds;
          }

          if (cancelled) return;
          setSeries(resolvedSeries);
          setPrimary(resolvedPrimary);
          if (resolvedPrimary)
            onModalityDetected?.(resolvedPrimary.modality);
          if (!resolvedPrimary || imageIds.length === 0) {
            setError("Series has no readable frames.");
            setLoading(false);
            return;
          }
          if (!elementRef.current) return;

          if (!engineRef.current) {
            engineRef.current = new RenderingEngine(RENDERER_ID);
          }
          const engine = engineRef.current;

          try {
            engine.enableElement({
              viewportId: viewportIdRef.current,
              type: Enums.ViewportType.STACK,
              element: elementRef.current,
            } as Types.PublicViewportInput);
          } catch {
            // already enabled — reuse
          }

          const viewport = engine.getViewport(
            viewportIdRef.current
          ) as Types.IStackViewport;
          await viewport.setStack(
            imageIds,
            Math.floor(imageIds.length / 2)
          );
          viewport.render();
          totalRef.current = imageIds.length;

          const group = getOrCreateToolGroup();
          group.addViewport(viewportIdRef.current, RENDERER_ID);

          elementRef.current.addEventListener(
            "CORNERSTONE_NEW_IMAGE",
            () => {
              const idx = viewport.getCurrentImageIdIndex();
              onSliceChange?.(idx + 1, imageIds.length);
            }
          );
          onSliceChange?.(
            Math.floor(imageIds.length / 2) + 1,
            imageIds.length
          );
          setLoading(false);
        } catch (err) {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : String(err));
            setLoading(false);
          }
        }
      })();
      return () => {
        cancelled = true;
        try {
          engineRef.current?.disableElement(viewportIdRef.current);
        } catch {
          // ignore
        }
      };
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [studyInstanceUID, seriesInstanceUID]);

    useEffect(() => {
      setActiveTool(TOOL_NAMES[activeTool]);
    }, [activeTool]);

    function applyPreset(p: Preset) {
      const engine = engineRef.current;
      if (!engine) return;
      const v = engine.getViewport(
        viewportIdRef.current
      ) as Types.IStackViewport;
      v.setProperties({
        voiRange: { lower: p.wc - p.ww / 2, upper: p.wc + p.ww / 2 },
      });
      v.render();
    }

    return (
      <div className="relative h-full w-full bg-black text-white">
        <div
          ref={elementRef}
          className="h-full w-full"
          onContextMenu={(e) => e.preventDefault()}
        />
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center text-xs text-zinc-400">
            Loading via /dicom-web…
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center px-4 text-center text-xs text-red-300">
            {error}
          </div>
        )}
        {!error && primary && (
          <>
            <div className="pointer-events-none absolute left-2 top-2 rounded bg-black/60 px-2 py-1 text-[10px]">
              {primary.modality} ·{" "}
              {primary.seriesDescription || "(no description)"}
            </div>
            {PRESETS[primary.modality] && (
              <div className="absolute right-2 top-2 flex gap-1">
                {PRESETS[primary.modality].map((p) => (
                  <button
                    key={p.label}
                    onClick={() => applyPreset(p)}
                    className="rounded bg-black/60 px-2 py-0.5 text-[10px] hover:bg-black/80"
                    title={`WW ${p.ww} / WC ${p.wc}`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            )}
            <div className="pointer-events-none absolute bottom-2 left-2 rounded bg-black/60 px-2 py-1 text-[10px]">
              {series.length} series ·{" "}
              {primary.seriesInstanceUID.slice(0, 24)}…
            </div>
          </>
        )}
      </div>
    );
  }
);

export { metaData };
