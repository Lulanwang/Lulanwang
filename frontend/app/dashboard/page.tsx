"use client";

import useSWR from "swr";
import {
  Activity,
  CheckCircle2,
  ClipboardList,
  Sparkles,
  Timer,
} from "lucide-react";
import { api } from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { StudiesPerDayChart } from "@/components/dashboard/StudiesPerDayChart";
import { ModalityDonut } from "@/components/dashboard/ModalityDonut";
import { ActivityFeed } from "@/components/dashboard/ActivityFeed";
import { UnsignedWorklist } from "@/components/dashboard/UnsignedWorklist";

export default function DashboardPage() {
  const kpis = useSWR("kpis", () => api.dashboardKpis(), {
    shouldRetryOnError: false,
  });
  const series = useSWR("studiesPerDay", () => api.dashboardStudiesPerDay(30));
  const modalities = useSWR("modalities", () => api.dashboardModalityBreakdown());
  const activity = useSWR("recentActivity", () =>
    api.dashboardRecentActivity(10)
  );
  const unsigned = useSWR("unsigned", () => api.dashboardUnsigned(5));

  const acceptPct =
    kpis.data?.accept_rate !== null && kpis.data?.accept_rate !== undefined
      ? `${(kpis.data.accept_rate * 100).toFixed(0)}%`
      : null;

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <p className="text-xs text-muted-foreground">
          Operational overview · last 7 days · RESEARCH USE ONLY
        </p>
      </header>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Studies (7d)"
          value={kpis.data?.studies_7d}
          icon={ClipboardList}
          loading={!kpis.data}
        />
        <KpiCard
          label="Signed reports"
          value={kpis.data?.signed_reports}
          icon={CheckCircle2}
          tone="success"
          loading={!kpis.data}
        />
        <KpiCard
          label="Mean inference latency"
          value={
            kpis.data ? `${(kpis.data.mean_latency_ms / 1000).toFixed(2)}s` : null
          }
          icon={Timer}
          tone="warning"
          loading={!kpis.data}
        />
        <KpiCard
          label="AI accept rate"
          value={acceptPct ?? "n/a"}
          hint={
            kpis.data
              ? `${kpis.data.reviewed_findings} reviewed findings`
              : undefined
          }
          icon={Sparkles}
          tone="default"
          loading={!kpis.data}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-sm">Studies per day · 30d</CardTitle>
            <CardDescription>Volume trend across the worklist.</CardDescription>
          </CardHeader>
          <CardContent>
            {series.data ? (
              <StudiesPerDayChart data={series.data} />
            ) : (
              <Skeleton className="h-[200px] w-full" />
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Modality breakdown</CardTitle>
            <CardDescription>Distribution across all studies.</CardDescription>
          </CardHeader>
          <CardContent>
            {modalities.data ? (
              <>
                <ModalityDonut data={modalities.data} />
                <div className="mt-2 flex flex-wrap items-center justify-center gap-1.5 text-[10px]">
                  {modalities.data.map((m) => (
                    <Badge key={m.modality} variant="secondary">
                      {m.modality} · {m.count}
                    </Badge>
                  ))}
                </div>
              </>
            ) : (
              <Skeleton className="h-[200px] w-full" />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Unsigned reports</CardTitle>
            <CardDescription>
              Reported studies awaiting radiologist signature.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {unsigned.data ? (
              <UnsignedWorklist rows={unsigned.data} />
            ) : (
              <Skeleton className="h-[200px] w-full" />
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5 text-sm">
              <Activity className="h-4 w-4 text-primary" /> Recent activity
            </CardTitle>
            <CardDescription>
              Audit events from the last few actions.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {activity.data ? (
              <ActivityFeed rows={activity.data} />
            ) : (
              <Skeleton className="h-[200px] w-full" />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
