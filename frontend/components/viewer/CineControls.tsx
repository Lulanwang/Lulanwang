"use client";

import { useEffect, useRef, useState } from "react";
import { Pause, Play, Repeat, SkipBack, SkipForward } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import type { ViewerHandle } from "./CornerstoneViewer";

export function CineControls({
  getActive,
  className,
}: {
  /** Returns the currently active viewer handle (changes as user tabs between cells) */
  getActive: () => ViewerHandle | null;
  className?: string;
}) {
  const [playing, setPlaying] = useState(false);
  const [fps, setFps] = useState(10);
  const [loop, setLoop] = useState(true);
  const [tick, setTick] = useState(0); // re-render to update slice readout
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Drive the active viewer at the configured rate
  useEffect(() => {
    if (!playing) {
      if (intervalRef.current) clearInterval(intervalRef.current);
      intervalRef.current = null;
      return;
    }
    intervalRef.current = setInterval(() => {
      const v = getActive();
      if (!v) return;
      const total = v.getTotalSlices();
      if (total <= 1) return;
      const cur = v.getSliceIndex();
      let next = cur + 1;
      if (next >= total) {
        if (loop) next = 0;
        else {
          setPlaying(false);
          return;
        }
      }
      v.setSliceIndex(next);
      setTick((t) => t + 1);
    }, Math.max(33, Math.round(1000 / fps)));
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [playing, fps, loop, getActive]);

  // Keyboard: Space toggles, [ / ] adjust fps
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tgt = e.target as HTMLElement | null;
      const tag = tgt?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tgt?.isContentEditable)
        return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === " ") {
        e.preventDefault();
        setPlaying((p) => !p);
      } else if (e.key === "[") {
        setFps((f) => Math.max(1, f - 1));
      } else if (e.key === "]") {
        setFps((f) => Math.min(30, f + 1));
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const active = getActive();
  const cur = active ? active.getSliceIndex() + 1 : 0;
  const total = active ? active.getTotalSlices() : 0;
  void tick;

  return (
    <div
      className={cn(
        "flex items-center gap-2 border-t border-zinc-800 bg-zinc-950/80 px-3 py-1.5 text-xs text-zinc-200",
        className
      )}
    >
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={() => active?.jumpRelative(-10)}
        aria-label="Back 10 slices"
        className="text-zinc-300 hover:bg-zinc-800 hover:text-white"
      >
        <SkipBack />
      </Button>
      <Button
        variant={playing ? "default" : "ghost"}
        size="icon-sm"
        onClick={() => setPlaying((p) => !p)}
        aria-label={playing ? "Pause" : "Play"}
        className={cn(
          !playing && "text-zinc-300 hover:bg-zinc-800 hover:text-white"
        )}
        title="Space toggles"
      >
        {playing ? <Pause /> : <Play />}
      </Button>
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={() => active?.jumpRelative(10)}
        aria-label="Forward 10 slices"
        className="text-zinc-300 hover:bg-zinc-800 hover:text-white"
      >
        <SkipForward />
      </Button>
      <Button
        variant={loop ? "default" : "ghost"}
        size="icon-sm"
        onClick={() => setLoop((l) => !l)}
        aria-label="Toggle loop"
        title="Loop"
        className={cn(
          !loop && "text-zinc-300 hover:bg-zinc-800 hover:text-white"
        )}
      >
        <Repeat />
      </Button>
      <label className="ml-1 flex items-center gap-2 text-[10px] text-zinc-400">
        <span className="uppercase tracking-wide">fps</span>
        <input
          type="range"
          min={1}
          max={30}
          value={fps}
          onChange={(e) => setFps(Number(e.target.value))}
          className="w-24 accent-blue-500"
        />
        <span className="w-6 tabular-nums text-zinc-200">{fps}</span>
      </label>
      <div className="ml-auto tabular-nums text-zinc-400">
        slice <span className="text-zinc-200">{cur}</span> / {total}
      </div>
    </div>
  );
}
