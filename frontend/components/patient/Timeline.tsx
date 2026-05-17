"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowUpRight, Calendar } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { StatusPill } from "@/components/StatusPill";
import { StudyThumbnail } from "@/components/worklist/StudyThumbnail";
import { cn } from "@/lib/cn";

type Study = {
  id: string;
  study_instance_uid: string;
  modality: string;
  body_part: string;
  description: string;
  state: string;
  study_date: string | null;
  finding_count: number;
};

export function Timeline({
  studies,
  selected,
  onToggleSelect,
}: {
  studies: Study[];
  selected: string[];
  onToggleSelect: (id: string) => void;
}) {
  // Group by year (descending)
  const groups = new Map<string, Study[]>();
  for (const s of studies) {
    const year = s.study_date
      ? new Date(s.study_date).getFullYear().toString()
      : "Undated";
    if (!groups.has(year)) groups.set(year, []);
    groups.get(year)!.push(s);
  }
  const yearKeys = [...groups.keys()].sort((a, b) => {
    if (a === "Undated") return 1;
    if (b === "Undated") return -1;
    return Number(b) - Number(a);
  });

  return (
    <div className="space-y-6">
      {yearKeys.map((year) => (
        <div key={year}>
          <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <Calendar className="h-3.5 w-3.5" /> {year}
          </h3>
          <ol className="relative space-y-3 border-l-2 border-border pl-4">
            {groups.get(year)!.map((s, i) => (
              <motion.li
                key={s.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
                className="relative"
              >
                <span
                  className={cn(
                    "absolute -left-[22px] top-3 h-3 w-3 rounded-full border-2 border-background bg-primary",
                    selected.includes(s.id) && "ring-2 ring-primary/40"
                  )}
                />
                <Card
                  className={cn(
                    "flex items-start gap-3 p-3 text-xs transition-colors",
                    selected.includes(s.id) &&
                      "border-primary/50 ring-1 ring-primary/30"
                  )}
                >
                  <StudyThumbnail studyId={s.id} size={56} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="truncate font-medium text-foreground">
                          {s.description || "(no description)"}
                        </div>
                        <div className="mt-0.5 text-muted-foreground">
                          {s.study_date
                            ? new Date(s.study_date).toLocaleDateString()
                            : "no date"}
                        </div>
                      </div>
                      <StatusPill state={s.state} />
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-1">
                      <Badge variant="secondary">{s.modality}</Badge>
                      <span className="text-muted-foreground">{s.body_part}</span>
                      <span className="text-muted-foreground">·</span>
                      <span className="tabular-nums text-muted-foreground">
                        {s.finding_count} findings
                      </span>
                    </div>
                    <div className="mt-2 flex items-center gap-3">
                      <label className="inline-flex cursor-pointer items-center gap-1 text-[10px] text-muted-foreground">
                        <input
                          type="checkbox"
                          checked={selected.includes(s.id)}
                          onChange={() => onToggleSelect(s.id)}
                          className="h-3 w-3 rounded border-border"
                        />
                        Compare
                      </label>
                      <Link
                        href={`/studies/${s.id}`}
                        className="inline-flex items-center gap-1 text-[10px] font-medium text-primary hover:underline"
                      >
                        Open study
                        <ArrowUpRight className="h-3 w-3" />
                      </Link>
                    </div>
                  </div>
                </Card>
              </motion.li>
            ))}
          </ol>
        </div>
      ))}
    </div>
  );
}
