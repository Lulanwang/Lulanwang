"use client";

import { ToolName } from "@/lib/cornerstone-init";

const TOOLS: { id: ToolName; label: string; icon: string; hint: string }[] = [
  { id: "WindowLevel", label: "W/L", icon: "◐", hint: "Window / level" },
  { id: "Pan", label: "Pan", icon: "✥", hint: "Pan (right-click default)" },
  { id: "Zoom", label: "Zoom", icon: "⟲", hint: "Zoom (middle-click default)" },
  { id: "StackScroll", label: "Scroll", icon: "⇅", hint: "Slice scroll (mouse wheel)" },
  { id: "Length", label: "Length", icon: "↔", hint: "Length measurement" },
  { id: "EllipticalROI", label: "Ellipse", icon: "◯", hint: "Elliptical ROI" },
  { id: "RectangleROI", label: "Rect", icon: "▭", hint: "Rectangular ROI" },
  { id: "Brush", label: "Brush", icon: "●", hint: "Paint segmentation" },
  { id: "RectangleScissors", label: "Cut", icon: "✂", hint: "Rectangle scissors" },
];

export function Toolbar({
  active,
  onChange,
}: {
  active: ToolName;
  onChange: (t: ToolName) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1 bg-gray-900 text-white rounded-t px-2 py-1">
      {TOOLS.map((t) => (
        <button
          key={t.id}
          title={t.hint}
          onClick={() => onChange(t.id)}
          className={`text-[11px] px-2 py-1 rounded flex items-center gap-1 ${
            active === t.id
              ? "bg-blue-600 text-white"
              : "bg-gray-800 hover:bg-gray-700 text-gray-200"
          }`}
        >
          <span className="w-3 text-center">{t.icon}</span>
          {t.label}
        </button>
      ))}
    </div>
  );
}
