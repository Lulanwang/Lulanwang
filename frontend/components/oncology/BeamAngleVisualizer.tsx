"use client";

import { type Beam } from "@/lib/api";

/**
 * Top-down axial schematic. Patient is the central circle; each beam
 * is an arrow pointing inward from its gantry angle (0° = anterior, top).
 */
export function BeamAngleVisualizer({ beams }: { beams: Beam[] }) {
  const size = 240;
  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - 24;

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className="mx-auto block"
      role="img"
      aria-label="Beam angle visualizer"
    >
      <defs>
        <marker
          id="arrow-head"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <path d="M0,0 L10,5 L0,10 z" fill="hsl(var(--primary))" />
        </marker>
      </defs>

      {/* Patient cross-section */}
      <circle
        cx={cx}
        cy={cy}
        r={r * 0.55}
        fill="hsl(var(--muted))"
        stroke="hsl(var(--border))"
        strokeWidth={1.5}
      />
      {/* Isocenter */}
      <circle cx={cx} cy={cy} r={3} fill="hsl(var(--primary))" />

      {/* Cardinal compass labels — A/P/L/R */}
      {[
        { l: "A", x: cx, y: cy - r - 6 },
        { l: "P", x: cx, y: cy + r + 14 },
        { l: "R", x: cx - r - 12, y: cy + 4 },
        { l: "L", x: cx + r + 6, y: cy + 4 },
      ].map(({ l, x, y }) => (
        <text
          key={l}
          x={x}
          y={y}
          textAnchor="middle"
          fontSize={10}
          fontWeight={600}
          fill="hsl(var(--muted-foreground))"
        >
          {l}
        </text>
      ))}

      {/* Beam arrows */}
      {beams.map((b, i) => {
        // gantry 0° = anterior (top, y- in SVG); 90° = left = x+
        const angRad = ((b.gantry_angle - 90) * Math.PI) / 180;
        const startX = cx + Math.cos(angRad) * r;
        const startY = cy + Math.sin(angRad) * r;
        return (
          <g key={i}>
            <line
              x1={startX}
              y1={startY}
              x2={cx + Math.cos(angRad) * 8}
              y2={cy + Math.sin(angRad) * 8}
              stroke="hsl(var(--primary))"
              strokeWidth={1.5}
              markerEnd="url(#arrow-head)"
              opacity={0.8}
            />
            <text
              x={cx + Math.cos(angRad) * (r + 12)}
              y={cy + Math.sin(angRad) * (r + 12) + 3}
              textAnchor="middle"
              fontSize={9}
              fill="hsl(var(--foreground))"
            >
              {Math.round(b.gantry_angle)}°
            </text>
          </g>
        );
      })}

      {beams.length === 0 && (
        <text
          x={cx}
          y={cy + 4}
          textAnchor="middle"
          fontSize={10}
          fill="hsl(var(--muted-foreground))"
        >
          No beams
        </text>
      )}
    </svg>
  );
}
