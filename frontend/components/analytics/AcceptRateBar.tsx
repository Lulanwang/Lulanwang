"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Row = {
  group: string;
  accepted: number;
  rejected: number;
  modified: number;
  proposed: number;
};

export function AcceptRateBar({ data }: { data: Row[] }) {
  if (data.length === 0) {
    return (
      <div className="flex h-[260px] items-center justify-center text-xs text-muted-foreground">
        No reviewed findings yet
      </div>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          dataKey="group"
          tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
        />
        <YAxis
          allowDecimals={false}
          tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
          width={28}
        />
        <Tooltip
          contentStyle={{
            background: "hsl(var(--popover))",
            border: "1px solid hsl(var(--border))",
            borderRadius: 6,
            fontSize: 11,
          }}
        />
        <Legend wrapperStyle={{ fontSize: 10 }} />
        <Bar
          dataKey="accepted"
          stackId="status"
          fill="hsl(142 71% 50%)"
          name="Accepted"
        />
        <Bar
          dataKey="modified"
          stackId="status"
          fill="hsl(217 91% 60%)"
          name="Modified"
        />
        <Bar
          dataKey="rejected"
          stackId="status"
          fill="hsl(0 72% 60%)"
          name="Rejected"
        />
        <Bar
          dataKey="proposed"
          stackId="status"
          fill="hsl(215 16% 47%)"
          name="Proposed"
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
