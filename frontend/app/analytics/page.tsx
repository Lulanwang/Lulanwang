"use client";

import { useState } from "react";
import useSWR from "swr";
import { BarChart3, ShieldCheck, Sparkles, Timer } from "lucide-react";
import { api } from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { AcceptRateBar } from "@/components/analytics/AcceptRateBar";
import { JobLatencyLine } from "@/components/analytics/JobLatencyLine";
import { AuditHeatmap } from "@/components/analytics/AuditHeatmap";
import { CsvDownload } from "@/components/analytics/CsvDownload";
import { cn } from "@/lib/cn";

export default function AnalyticsPage() {
  const [groupBy, setGroupBy] = useState<"model" | "body_part">("model");
  const accept = useSWR(["accept", groupBy], () =>
    api.analyticsAcceptRate(groupBy)
  );
  const latency = useSWR("latency", () => api.analyticsJobLatency(30));
  const heatmap = useSWR("heatmap", () => api.analyticsAuditHeatmap(91));

  return (
    <div className="space-y-5">
      <header>
        <h1 className="flex items-center gap-2 text-xl font-semibold">
          <BarChart3 className="h-5 w-5 text-primary" /> Analytics
        </h1>
        <p className="text-xs text-muted-foreground">
          Operational metrics across models, latency, and audit activity ·
          RESEARCH USE ONLY
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-2">
              <div>
                <CardTitle className="flex items-center gap-1.5 text-sm">
                  <Sparkles className="h-4 w-4 text-primary" /> AI accept rate
                </CardTitle>
                <CardDescription>
                  Stacked counts of accepted / modified / rejected / proposed
                  AI findings, grouped by{" "}
                  <button
                    onClick={() =>
                      setGroupBy(groupBy === "model" ? "body_part" : "model")
                    }
                    className="font-semibold text-primary hover:underline"
                  >
                    {groupBy === "model" ? "model" : "body part"}
                  </button>
                  .
                </CardDescription>
              </div>
              {accept.data && (
                <CsvDownload
                  data={accept.data}
                  filename={`accept-rate-by-${groupBy}.csv`}
                />
              )}
            </div>
          </CardHeader>
          <CardContent>
            <div className="mb-2 flex gap-1">
              {(["model", "body_part"] as const).map((k) => (
                <button
                  key={k}
                  onClick={() => setGroupBy(k)}
                  className={cn(
                    "rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide transition-colors",
                    groupBy === k
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border text-muted-foreground hover:text-foreground"
                  )}
                >
                  {k.replace("_", " ")}
                </button>
              ))}
            </div>
            {accept.data ? (
              <AcceptRateBar data={accept.data} />
            ) : (
              <Skeleton className="h-[260px] w-full" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-2">
              <div>
                <CardTitle className="flex items-center gap-1.5 text-sm">
                  <Timer className="h-4 w-4 text-primary" /> Inference latency
                </CardTitle>
                <CardDescription>
                  Per-day mean wall-clock latency (started → finished) for
                  every inference job, last 30 days.
                </CardDescription>
              </div>
              {latency.data && (
                <CsvDownload
                  data={latency.data}
                  filename="job-latency-30d.csv"
                />
              )}
            </div>
          </CardHeader>
          <CardContent>
            {latency.data ? (
              <JobLatencyLine data={latency.data} />
            ) : (
              <Skeleton className="h-[220px] w-full" />
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <div>
              <CardTitle className="flex items-center gap-1.5 text-sm">
                <ShieldCheck className="h-4 w-4 text-primary" /> Audit
                activity · 90 days
              </CardTitle>
              <CardDescription>
                Daily count of audit events. Click a cell for the date +
                count tooltip.
              </CardDescription>
            </div>
            {heatmap.data && (
              <CsvDownload
                data={heatmap.data}
                filename="audit-heatmap-90d.csv"
              />
            )}
          </div>
        </CardHeader>
        <CardContent>
          {heatmap.data ? (
            <AuditHeatmap data={heatmap.data} />
          ) : (
            <Skeleton className="h-[120px] w-full" />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
