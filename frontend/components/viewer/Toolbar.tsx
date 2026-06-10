"use client";

import {
  Contrast,
  Move,
  ZoomIn,
  Layers,
  Ruler,
  Circle,
  Square,
  Paintbrush,
  Scissors,
  type LucideIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ToolName } from "@/lib/cornerstone-init";
import { cn } from "@/lib/cn";

const TOOLS: { id: ToolName; label: string; icon: LucideIcon; hint: string }[] =
  [
    { id: "WindowLevel", label: "W/L", icon: Contrast, hint: "Window / level" },
    { id: "Pan", label: "Pan", icon: Move, hint: "Pan (right-click default)" },
    { id: "Zoom", label: "Zoom", icon: ZoomIn, hint: "Zoom (middle-click default)" },
    { id: "StackScroll", label: "Scroll", icon: Layers, hint: "Slice scroll (mouse wheel)" },
    { id: "Length", label: "Length", icon: Ruler, hint: "Length measurement" },
    { id: "EllipticalROI", label: "Ellipse", icon: Circle, hint: "Elliptical ROI" },
    { id: "RectangleROI", label: "Rect", icon: Square, hint: "Rectangular ROI" },
    { id: "Brush", label: "Brush", icon: Paintbrush, hint: "Paint segmentation" },
    {
      id: "RectangleScissors",
      label: "Cut",
      icon: Scissors,
      hint: "Rectangle scissors",
    },
  ];

export function Toolbar({
  active,
  onChange,
}: {
  active: ToolName;
  onChange: (t: ToolName) => void;
}) {
  return (
    <TooltipProvider delayDuration={250}>
      <div className="flex flex-wrap items-center gap-1 border-b border-zinc-800 bg-zinc-950/80 px-2 py-1.5">
        {TOOLS.map((t) => {
          const Icon = t.icon;
          const isActive = active === t.id;
          return (
            <Tooltip key={t.id}>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  variant={isActive ? "default" : "ghost"}
                  size="sm"
                  onClick={() => onChange(t.id)}
                  aria-label={t.hint}
                  aria-pressed={isActive}
                  className={cn(
                    "h-7 gap-1.5 px-2 text-[11px]",
                    !isActive && "text-zinc-300 hover:bg-zinc-800 hover:text-white"
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {t.label}
                </Button>
              </TooltipTrigger>
              <TooltipContent>{t.hint}</TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </TooltipProvider>
  );
}
