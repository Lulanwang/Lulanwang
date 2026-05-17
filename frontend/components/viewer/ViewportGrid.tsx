"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Grid2x2, Grid3x3, Link as LinkIcon, Rows2, Square } from "lucide-react";
import { CornerstoneViewer, ViewerHandle } from "./CornerstoneViewer";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/cn";
import type { ToolName } from "@/lib/cornerstone-init";

export type Layout = "1x1" | "1x2" | "2x1" | "2x2" | "1x3" | "3x3";

const LAYOUTS: { id: Layout; cells: number; cols: number; rows: number; icon: typeof Square }[] = [
  { id: "1x1", cells: 1, cols: 1, rows: 1, icon: Square },
  { id: "1x2", cells: 2, cols: 2, rows: 1, icon: Rows2 },
  { id: "2x2", cells: 4, cols: 2, rows: 2, icon: Grid2x2 },
  { id: "3x3", cells: 9, cols: 3, rows: 3, icon: Grid3x3 },
];

export type ViewportSlot = {
  id: string;
  seriesInstanceUID?: string;
  /** Override study UID for prior-study comparison; falls back to the grid's default. */
  studyInstanceUID?: string;
  /** Optional label rendered in the cell's top-left corner. */
  label?: string;
};

export function ViewportGrid({
  studyInstanceUID,
  activeTool,
  layout,
  onLayoutChange,
  slots,
  setSlots,
  activeSlotIdx,
  setActiveSlotIdx,
  sync,
  setSync,
  registerHandle,
}: {
  studyInstanceUID: string;
  activeTool: ToolName;
  layout: Layout;
  onLayoutChange: (l: Layout) => void;
  slots: ViewportSlot[];
  setSlots: (next: ViewportSlot[]) => void;
  activeSlotIdx: number;
  setActiveSlotIdx: (i: number) => void;
  sync: boolean;
  setSync: (v: boolean) => void;
  /** Called once per mount with the slot index + handle. */
  registerHandle: (idx: number, handle: ViewerHandle | null) => void;
}) {
  const layoutDef = useMemo(
    () => LAYOUTS.find((l) => l.id === layout) ?? LAYOUTS[0],
    [layout]
  );

  // Resize slot list to match layout cell count
  useEffect(() => {
    if (slots.length === layoutDef.cells) return;
    const next: ViewportSlot[] = [...slots];
    while (next.length < layoutDef.cells) {
      next.push({ id: `vp-${crypto.randomUUID().slice(0, 8)}` });
    }
    next.length = layoutDef.cells;
    setSlots(next);
    if (activeSlotIdx >= layoutDef.cells) setActiveSlotIdx(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layout]);

  const refs = useRef<(ViewerHandle | null)[]>([]);
  if (refs.current.length !== slots.length) {
    const grown: (ViewerHandle | null)[] = [];
    for (let i = 0; i < slots.length; i++) grown.push(refs.current[i] ?? null);
    refs.current = grown;
  }

  // Sync-scroll: when any viewport's slice changes (and sync is on),
  // mirror to siblings. We can't introspect cornerstone events from
  // outside the viewer, so the broadcasting handler is invoked from
  // each viewer's onSliceChange callback.
  function broadcastSlice(srcIdx: number, oneBased: number, total: number) {
    if (!sync) return;
    slots.forEach((_, i) => {
      if (i === srcIdx) return;
      const handle = refs.current[i];
      if (!handle) return;
      const t = handle.getTotalSlices();
      if (t === 0) return;
      const ratio = (oneBased - 1) / Math.max(1, total - 1);
      const target = Math.round(ratio * (t - 1));
      handle.setSliceIndex(target);
    });
  }

  // Keyboard: Tab cycles active viewport (without leaving the page)
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tgt = e.target as HTMLElement | null;
      const tag = tgt?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tgt?.isContentEditable)
        return;
      if (e.key === "Tab" && !e.metaKey && !e.ctrlKey && !e.altKey && slots.length > 1) {
        e.preventDefault();
        const next = e.shiftKey
          ? (activeSlotIdx - 1 + slots.length) % slots.length
          : (activeSlotIdx + 1) % slots.length;
        setActiveSlotIdx(next);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [slots.length, activeSlotIdx, setActiveSlotIdx]);

  function onDrop(slotIdx: number, e: React.DragEvent) {
    e.preventDefault();
    const uid = e.dataTransfer.getData("text/x-series-uid");
    if (!uid) return;
    const next = [...slots];
    next[slotIdx] = { ...next[slotIdx], seriesInstanceUID: uid };
    setSlots(next);
    setActiveSlotIdx(slotIdx);
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-zinc-800 bg-zinc-950/80 px-2 py-1.5">
        <TooltipProvider delayDuration={250}>
          {LAYOUTS.map((l) => {
            const Icon = l.icon;
            const isActive = layout === l.id;
            return (
              <Tooltip key={l.id}>
                <TooltipTrigger asChild>
                  <Button
                    type="button"
                    variant={isActive ? "default" : "ghost"}
                    size="icon-sm"
                    onClick={() => onLayoutChange(l.id)}
                    aria-label={`Layout ${l.id}`}
                    className={cn(
                      !isActive &&
                        "text-zinc-300 hover:bg-zinc-800 hover:text-white"
                    )}
                  >
                    <Icon />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>{l.id}</TooltipContent>
              </Tooltip>
            );
          })}
          <div className="mx-1 h-5 w-px bg-zinc-800" />
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant={sync ? "default" : "ghost"}
                size="sm"
                onClick={() => setSync(!sync)}
                className={cn(
                  "h-7 gap-1.5 px-2 text-[11px]",
                  !sync && "text-zinc-300 hover:bg-zinc-800 hover:text-white"
                )}
              >
                <LinkIcon className="h-3.5 w-3.5" />
                Sync
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              When on, scrolling one viewport scrolls the others
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <span className="ml-auto text-[10px] text-zinc-500">
          Active cell {activeSlotIdx + 1} of {slots.length} · Tab to cycle
        </span>
      </div>

      <div
        className="grid flex-1 gap-px bg-zinc-800"
        style={{
          gridTemplateColumns: `repeat(${layoutDef.cols}, minmax(0, 1fr))`,
          gridTemplateRows: `repeat(${layoutDef.rows}, minmax(0, 1fr))`,
        }}
      >
        {slots.map((slot, i) => (
          <div
            key={slot.id}
            onClick={() => setActiveSlotIdx(i)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => onDrop(i, e)}
            className={cn(
              "relative cursor-pointer bg-black ring-inset transition-shadow",
              activeSlotIdx === i && "ring-2 ring-primary"
            )}
          >
            {slot.label && (
              <div className="absolute right-2 top-2 z-10 rounded bg-primary/80 px-2 py-0.5 text-[10px] uppercase tracking-wide text-white">
                {slot.label}
              </div>
            )}
            <CornerstoneViewer
              ref={(h) => {
                refs.current[i] = h;
                registerHandle(i, h);
              }}
              studyInstanceUID={slot.studyInstanceUID || studyInstanceUID}
              activeTool={activeTool}
              viewportId={slot.id}
              seriesInstanceUID={slot.seriesInstanceUID}
              onSliceChange={(oneBased, total) =>
                broadcastSlice(i, oneBased, total)
              }
            />
          </div>
        ))}
      </div>
    </div>
  );
}
