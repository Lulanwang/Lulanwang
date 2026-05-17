"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Loader2, Plus, Printer, Stethoscope } from "lucide-react";
import { toast } from "sonner";
import { api, type TreatmentPlan } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ResearchPlanBanner } from "@/components/oncology/ResearchBanner";
import { PlanHeader } from "@/components/oncology/PlanHeader";
import { ContouringPanel } from "@/components/oncology/ContouringPanel";
import { BeamPlannerPanel } from "@/components/oncology/BeamPlannerPanel";
import { OARManagerPanel } from "@/components/oncology/OARManagerPanel";
import { DoseSummaryCard } from "@/components/oncology/DoseSummaryCard";

export default function PlanPage() {
  const params = useParams<{ studyUid: string }>();
  const studyId = params.studyUid;
  const [plans, setPlans] = useState<TreatmentPlan[] | null>(null);
  const [plan, setPlan] = useState<TreatmentPlan | null>(null);
  const [creating, setCreating] = useState(false);

  async function load() {
    try {
      const list = await api.listPlans(studyId);
      setPlans(list);
      if (list.length > 0) {
        // Prefer the most recently created
        const fresh = await api.getPlan(list[0].id);
        setPlan(fresh);
      } else {
        setPlan(null);
      }
    } catch (e) {
      toast.error("Failed to load plans", {
        description: e instanceof Error ? e.message : String(e),
      });
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studyId]);

  async function refreshPlan() {
    if (!plan) return;
    const fresh = await api.getPlan(plan.id);
    setPlan(fresh);
  }

  async function createPlan() {
    setCreating(true);
    try {
      const fresh = await api.createPlan({ study_id: studyId });
      setPlan(fresh);
      setPlans((cur) => [fresh, ...(cur ?? [])]);
      toast.success("Draft plan created");
    } catch (e) {
      toast.error("Create failed", {
        description: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <Link
            href={`/studies/${studyId}`}
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-3 w-3" />
            Back to study
          </Link>
          <h1 className="mt-1 flex items-center gap-2 text-xl font-semibold">
            <Stethoscope className="h-5 w-5 text-primary" />
            Treatment planning
          </h1>
        </div>
        {plan && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => window.print()}
            className="hidden print:hidden md:inline-flex"
          >
            <Printer />
            Print summary
          </Button>
        )}
      </div>

      <ResearchPlanBanner />

      {plans === null && (
        <div className="space-y-2">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}

      {plans !== null && plans.length === 0 && (
        <EmptyState
          icon={Stethoscope}
          title="No plans for this study"
          description="Create a draft plan to start contouring, adding beams, and computing illustrative dose."
          action={
            <Button onClick={createPlan} disabled={creating} size="sm">
              {creating ? <Loader2 className="animate-spin" /> : <Plus />}
              New draft plan
            </Button>
          }
        />
      )}

      {plan && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_minmax(0,1fr)_320px]">
          <aside className="space-y-4">
            <ContouringPanel planId={plan.id} />
          </aside>

          <div className="space-y-4">
            <PlanHeader plan={plan} onChanged={refreshPlan} />
            <OARManagerPanel plan={plan} />
            {plan.notes && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Notes</CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="whitespace-pre-wrap font-sans text-xs">
                    {plan.notes}
                  </pre>
                </CardContent>
              </Card>
            )}
          </div>

          <aside className="space-y-4">
            <BeamPlannerPanel plan={plan} onChanged={refreshPlan} />
            <DoseSummaryCard plan={plan} onChanged={refreshPlan} />
          </aside>
        </div>
      )}
    </div>
  );
}
