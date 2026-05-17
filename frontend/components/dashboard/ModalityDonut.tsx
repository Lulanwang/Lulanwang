"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

const COLORS = [
  "hsl(217 91% 60%)",
  "hsl(142 71% 50%)",
  "hsl(31 90% 56%)",
  "hsl(280 75% 60%)",
  "hsl(0 72% 60%)",
  "hsl(190 80% 55%)",
];

export function ModalityDonut({
  data,
}: {
  data: Array<{ modality: string; count: number }>;
}) {
  if (data.length === 0) {
    return (
      <div className="flex h-[200px] items-center justify-center text-xs text-muted-foreground">
        No studies yet
      </div>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={200}>
      <PieChart>
        <Pie
          data={data}
          dataKey="count"
          nameKey="modality"
          innerRadius={50}
          outerRadius={80}
          paddingAngle={2}
        >
          {data.map((_, i) => (
            <Cell
              key={i}
              fill={COLORS[i % COLORS.length]}
              stroke="hsl(var(--card))"
              strokeWidth={2}
            />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            background: "hsl(var(--popover))",
            border: "1px solid hsl(var(--border))",
            borderRadius: 6,
            fontSize: 11,
          }}
          labelStyle={{ color: "hsl(var(--foreground))" }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
