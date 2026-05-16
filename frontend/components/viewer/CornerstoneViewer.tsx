"use client";

import { useEffect, useRef, useState } from "react";
import {
  Enums,
  RenderingEngine,
  Types,
  imageLoader,
  metaData,
} from "@cornerstonejs/core";
import {
  ensureCornerstone,
  getOrCreateToolGroup,
  setActiveTool,
  TOOL_GROUP_ID,
  TOOL_NAMES,
  ToolName,
} from "@/lib/cornerstone-init";
import { buildStackImageIds, Series } from "@/lib/wadors-loader";

/**
 * 2D stack viewer for a single study.
 *
 * Pulls the longest imaging series via QIDO, then loads frames via
 * WADO-RS (every request goes through our authenticated /dicom-web
 * proxy, so the audit log captures the pull). Tools are bound to the
 * "lulan-default" tool group; the parent component drives the active
 * tool via setActiveTool().
 *
 * Implementation note: cornerstone3D is strictly client-side. We
 * dynamic-import this component (ssr:false) from the page so Next.js
 * never tries to render it during SSR.
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

export function CornerstoneViewer({
  studyInstanceUID,
  activeTool,
  onSliceChange,
  onModalityDetected,
}: {
  studyInstanceUID: string;
  activeTool: ToolName;
  onSliceChange?: (idx: number, total: number) => void;
  onModalityDetected?: (modality: string) => void;
}) {
  const elementRef = useRef<HTMLDivElement>(null);
  const engineRef = useRef<RenderingEngine | null>(null);
  const viewportIdRef = useRef("lulan-viewport");
  const [series, setSeries] = useState<Series[]>([]);
  const [primary, setPrimary] = useState<Series | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Initial mount: ensure cornerstone is ready, build image ids, render
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await ensureCornerstone();
        const { series, primary, imageIds } = await buildStackImageIds(studyInstanceUID);
        if (cancelled) return;
        setSeries(series);
        setPrimary(primary);
        if (primary) onModalityDetected?.(primary.modality);
        if (!primary || imageIds.length === 0) {
          setError("Study has no readable imaging series.");
          setLoading(false);
          return;
        }
        if (!elementRef.current) return;

        // Create / re-use rendering engine
        if (!engineRef.current) {
          engineRef.current = new RenderingEngine("lulan-renderer");
        }
        const engine = engineRef.current;

        engine.enableElement({
          viewportId: viewportIdRef.current,
          type: Enums.ViewportType.STACK,
          element: elementRef.current,
        } as Types.PublicViewportInput);

        const viewport = engine.getViewport(viewportIdRef.current) as Types.IStackViewport;
        await viewport.setStack(imageIds, Math.floor(imageIds.length / 2));
        viewport.render();

        // Attach tool group to this viewport
        const group = getOrCreateToolGroup();
        group.addViewport(viewportIdRef.current, "lulan-renderer");

        // Wire slice-change callback
        elementRef.current.addEventListener("CORNERSTONE_NEW_IMAGE", () => {
          const idx = viewport.getCurrentImageIdIndex();
          onSliceChange?.(idx + 1, imageIds.length);
        });
        onSliceChange?.(Math.floor(imageIds.length / 2) + 1, imageIds.length);
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
      } catch {}
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studyInstanceUID]);

  // Active-tool prop drives the cornerstone toolgroup
  useEffect(() => {
    setActiveTool(TOOL_NAMES[activeTool]);
  }, [activeTool]);

  function applyPreset(p: Preset) {
    const engine = engineRef.current;
    if (!engine) return;
    const v = engine.getViewport(viewportIdRef.current) as Types.IStackViewport;
    v.setProperties({ voiRange: { lower: p.wc - p.ww / 2, upper: p.wc + p.ww / 2 } });
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
        <div className="absolute inset-0 flex items-center justify-center text-xs text-gray-300">
          Loading study via /dicom-web…
        </div>
      )}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center text-xs text-red-300 px-4 text-center">
          {error}
        </div>
      )}
      {!error && primary && (
        <>
          <div className="absolute left-2 top-2 text-[10px] bg-black/60 rounded px-2 py-1">
            {primary.modality} · {primary.seriesDescription || "(no description)"} ·{" "}
            {primary.instanceCount} frames
          </div>
          {PRESETS[primary.modality] && (
            <div className="absolute right-2 top-2 flex gap-1">
              {PRESETS[primary.modality].map((p) => (
                <button
                  key={p.label}
                  onClick={() => applyPreset(p)}
                  className="text-[10px] bg-black/60 hover:bg-black/80 rounded px-2 py-0.5"
                  title={`WW ${p.ww} / WC ${p.wc}`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          )}
          <div className="absolute left-2 bottom-2 text-[10px] bg-black/60 rounded px-2 py-1">
            {series.length} series · {primary.seriesInstanceUID.slice(0, 24)}…
          </div>
        </>
      )}
    </div>
  );
}
