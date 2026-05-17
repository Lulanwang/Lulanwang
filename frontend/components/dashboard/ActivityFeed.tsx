"use client";

import { Activity } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";

type ActivityRow = {
  id: string;
  created_at: string | null;
  action: string;
  actor_role: string | null;
  resource_type: string | null;
};

function relativeTime(iso: string | null): string {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function ActivityFeed({ rows }: { rows: ActivityRow[] }) {
  if (rows.length === 0) {
    return (
      <div className="flex h-[200px] items-center justify-center text-xs text-muted-foreground">
        <Activity className="mr-1 h-3.5 w-3.5" /> No activity yet
      </div>
    );
  }
  return (
    <ScrollArea className="h-[240px]">
      <ul className="space-y-2 pr-3 text-xs">
        {rows.map((r) => (
          <li
            key={r.id}
            className="flex items-center justify-between gap-2 border-b pb-2 last:border-0"
          >
            <div className="flex flex-1 items-center gap-2">
              <Badge variant="secondary">{r.action}</Badge>
              <span className="truncate text-muted-foreground">
                {r.resource_type ?? "—"}
              </span>
            </div>
            <span className="shrink-0 text-[10px] text-muted-foreground">
              {relativeTime(r.created_at)}
            </span>
          </li>
        ))}
      </ul>
    </ScrollArea>
  );
}
