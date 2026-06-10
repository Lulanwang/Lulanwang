"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { Calendar, GitCompare, Inbox, Users } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { Badge } from "@/components/ui/badge";
import { Timeline } from "@/components/patient/Timeline";
import { ChangeReportDrawer } from "@/components/patient/ChangeReportDrawer";

export default function PatientPage() {
  const params = useParams<{ pseudonym: string }>();
  const pseudonym = decodeURIComponent(params.pseudonym);
  const { data, error, isLoading } = useSWR(
    ["patient", pseudonym],
    () => api.patientStudies(pseudonym)
  );
  const [selected, setSelected] = useState<string[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const range = useMemo(() => {
    if (!data || data.length === 0) return null;
    const dated = data.filter((s) => s.study_date);
    if (dated.length === 0) return null;
    const dates = dated.map((s) => new Date(s.study_date!).getTime());
    return {
      first: new Date(Math.min(...dates)),
      last: new Date(Math.max(...dates)),
    };
  }, [data]);

  function toggle(id: string) {
    setSelected((cur) => {
      if (cur.includes(id)) return cur.filter((x) => x !== id);
      if (cur.length >= 2) return [cur[1], id]; // keep last 2
      return [...cur, id];
    });
  }

  function compare() {
    if (selected.length !== 2) {
      toast.warning("Select two studies to compare", {
        description: "Click Compare on two timeline entries.",
      });
      return;
    }
    setDrawerOpen(true);
  }

  // Ensure baseline = earlier of the two
  const ordered = useMemo(() => {
    if (selected.length !== 2 || !data) return null;
    const studies = selected
      .map((id) => data.find((s) => s.id === id))
      .filter((x): x is NonNullable<typeof x> => !!x);
    if (studies.length !== 2) return null;
    const sorted = [...studies].sort((a, b) => {
      const ad = a.study_date ? new Date(a.study_date).getTime() : 0;
      const bd = b.study_date ? new Date(b.study_date).getTime() : 0;
      return ad - bd;
    });
    return { baseline: sorted[0], followUp: sorted[1] };
  }, [selected, data]);

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <Users className="h-5 w-5 text-primary" />
            Patient timeline
          </h1>
          <p className="font-mono text-xs text-muted-foreground">
            {pseudonym}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {data && (
            <Badge variant="secondary">{data.length} studies</Badge>
          )}
          <Button
            size="sm"
            variant="default"
            onClick={compare}
            disabled={selected.length !== 2 || !ordered}
            title={
              selected.length !== 2
                ? "Select two timeline entries to compare"
                : "Generate longitudinal change report"
            }
          >
            <GitCompare />
            Compare ({selected.length}/2)
          </Button>
        </div>
      </div>

      {range && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              {range.first.toLocaleDateString()} →{" "}
              {range.last.toLocaleDateString()}
            </CardTitle>
          </CardHeader>
        </Card>
      )}

      {error && (
        <Card className="border-destructive/30">
          <CardContent className="pt-4 text-sm text-destructive">
            {error instanceof Error ? error.message : String(error)}
          </CardContent>
        </Card>
      )}

      {isLoading && (
        <div className="space-y-2">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      )}

      {data && data.length === 0 && (
        <EmptyState
          icon={Inbox}
          title="No studies"
          description="This patient has no studies in the system."
        />
      )}

      {data && data.length > 0 && (
        <Timeline
          studies={data}
          selected={selected}
          onToggleSelect={toggle}
        />
      )}

      {ordered && (
        <ChangeReportDrawer
          open={drawerOpen}
          onOpenChange={setDrawerOpen}
          pseudonym={pseudonym}
          baselineId={ordered.baseline.id}
          followUpId={ordered.followUp.id}
        />
      )}
    </div>
  );
}
