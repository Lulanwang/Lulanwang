"use client";

import Link from "next/link";
import { ArrowUpRight, Inbox } from "lucide-react";
import { Badge } from "@/components/ui/badge";

type UnsignedRow = {
  id: string;
  description: string;
  modality: string;
  body_part: string;
};

export function UnsignedWorklist({ rows }: { rows: UnsignedRow[] }) {
  if (rows.length === 0) {
    return (
      <div className="flex h-[200px] flex-col items-center justify-center gap-1 text-xs text-muted-foreground">
        <Inbox className="h-5 w-5" />
        No unsigned reports
      </div>
    );
  }
  return (
    <ul className="divide-y text-xs">
      {rows.map((r) => (
        <li key={r.id} className="flex items-center gap-3 py-2">
          <div className="min-w-0 flex-1">
            <div className="truncate font-medium">
              {r.description || "(no description)"}
            </div>
            <div className="mt-0.5 flex items-center gap-1.5 text-muted-foreground">
              <Badge variant="secondary">{r.modality}</Badge>
              <span>{r.body_part}</span>
            </div>
          </div>
          <Link
            href={`/studies/${r.id}`}
            className="inline-flex items-center gap-1 text-primary hover:underline"
          >
            Open
            <ArrowUpRight className="h-3 w-3" />
          </Link>
        </li>
      ))}
    </ul>
  );
}
