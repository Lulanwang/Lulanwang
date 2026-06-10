"use client";

import { cn } from "@/lib/cn";

type Row = { date: string; count: number };

function bucket(count: number, max: number): number {
  if (count === 0) return 0;
  if (max === 0) return 0;
  const ratio = count / max;
  if (ratio < 0.2) return 1;
  if (ratio < 0.4) return 2;
  if (ratio < 0.7) return 3;
  return 4;
}

const TONE = [
  "bg-muted/40",
  "bg-primary/20",
  "bg-primary/40",
  "bg-primary/60",
  "bg-primary/90",
];

export function AuditHeatmap({ data }: { data: Row[] }) {
  if (data.length === 0) return null;
  const max = Math.max(...data.map((d) => d.count));
  // Group into weeks of 7
  const cols: Row[][] = [];
  let cur: Row[] = [];
  for (const d of data) {
    cur.push(d);
    if (cur.length === 7) {
      cols.push(cur);
      cur = [];
    }
  }
  if (cur.length) cols.push(cur);

  return (
    <div className="space-y-3">
      <div className="flex gap-[2px] overflow-x-auto pb-1">
        {cols.map((week, wi) => (
          <div key={wi} className="flex flex-col gap-[2px]">
            {week.map((d) => (
              <div
                key={d.date}
                title={`${d.date} · ${d.count} events`}
                className={cn(
                  "h-3 w-3 rounded-[2px]",
                  TONE[bucket(d.count, max)]
                )}
              />
            ))}
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
        <span>less</span>
        {TONE.map((t, i) => (
          <div key={i} className={cn("h-3 w-3 rounded-[2px]", t)} />
        ))}
        <span>more</span>
        <span className="ml-auto">peak {max} events / day</span>
      </div>
    </div>
  );
}
