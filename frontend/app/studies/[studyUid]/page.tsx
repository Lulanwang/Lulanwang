"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import dynamic from "next/dynamic";
import {
  Boxes,
  CheckCircle2,
  Download,
  FileJson,
  FileText,
  History,
  Inbox,
  Keyboard,
  Loader2,
  MessageCircle,
  PlayCircle,
  Save,
  Search,
  Sparkles,
  Stethoscope,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { api, Finding, Report } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusPill } from "@/components/StatusPill";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Toolbar } from "@/components/viewer/Toolbar";
import { FindingCard } from "@/components/viewer/FindingActions";
import type { ToolName } from "@/lib/cornerstone-init";
import { PriorsPicker } from "@/components/study/PriorsPicker";
import { KeyboardShortcuts } from "@/components/study/KeyboardShortcuts";
import { MedGemmaChat } from "@/components/study/MedGemmaChat";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { cn } from "@/lib/cn";
import type { ViewerHandle } from "@/components/viewer/CornerstoneViewer";
import type { Layout, ViewportSlot } from "@/components/viewer/ViewportGrid";

const ViewportGrid = dynamic(
  () => import("@/components/viewer/ViewportGrid").then((m) => m.ViewportGrid),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center text-xs text-zinc-500">
        Loading viewer…
      </div>
    ),
  }
);

const CineControls = dynamic(
  () => import("@/components/viewer/CineControls").then((m) => m.CineControls),
  { ssr: false }
);

const SeriesPanel = dynamic(
  () => import("@/components/viewer/SeriesPanel").then((m) => m.SeriesPanel),
  { ssr: false }
);

type Study = Awaited<ReturnType<typeof api.getStudy>>;
type ICD = Awaited<ReturnType<typeof api.searchIcd10>>[number];

export default function StudyPage() {
  const params = useParams<{ studyUid: string }>();
  const studyId = params.studyUid;
  const [study, setStudy] = useState<Study | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [icdQuery, setIcdQuery] = useState("");
  const [icdResults, setIcdResults] = useState<ICD[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTool, setActiveTool] = useState<ToolName>("WindowLevel");
  const [refining, setRefining] = useState<Finding | null>(null);
  const [activeIdx, setActiveIdx] = useState(0);
  const [priorsOpen, setPriorsOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);

  const [layout, setLayout] = useState<Layout>("1x1");
  const [slots, setSlots] = useState<ViewportSlot[]>([
    { id: "vp-1" },
  ]);
  const [activeSlot, setActiveSlot] = useState(0);
  const [sync, setSync] = useState(true);
  const handlesRef = useRef<(ViewerHandle | null)[]>([]);

  const refresh = useCallback(async () => {
    try {
      const [s, f] = await Promise.all([
        api.getStudy(studyId),
        api.listFindings(studyId),
      ]);
      setStudy(s);
      setFindings(f);
      try {
        setReport(await api.getReport(studyId));
      } catch {
        setReport(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [studyId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const t = setTimeout(() => {
      api
        .searchIcd10(icdQuery)
        .then(setIcdResults)
        .catch(() => setIcdResults([]));
    }, 150);
    return () => clearTimeout(t);
  }, [icdQuery]);

  async function rerun() {
    setBusy(true);
    try {
      await api.runInference(studyId);
      toast.info("Inference queued", { description: "Polling for results…" });
      for (let i = 0; i < 30; i++) {
        await new Promise((r) => setTimeout(r, 500));
        const s = await api.getStudy(studyId);
        if (["reported", "signed", "failed"].includes(s.state)) break;
      }
      await refresh();
      toast.success("Inference complete");
    } catch (e) {
      toast.error("Inference failed", {
        description: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setBusy(false);
    }
  }

  async function sign() {
    setBusy(true);
    try {
      await api.signReport(studyId);
      toast.success("Report signed");
      await refresh();
    } catch (e) {
      toast.error("Sign failed", {
        description: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setBusy(false);
    }
  }

  function startRefine(f: Finding) {
    setRefining(f);
    setActiveTool("Brush");
  }

  async function acceptCurrent() {
    const f = findings[activeIdx];
    if (!f || f.status !== "proposed") return;
    try {
      await api.acceptFinding(f.id);
      toast.success("Accepted", { description: f.label });
      refresh();
    } catch (e) {
      toast.error("Accept failed", {
        description: e instanceof Error ? e.message : String(e),
      });
    }
  }

  async function rejectCurrent() {
    const f = findings[activeIdx];
    if (!f || f.status !== "proposed") return;
    try {
      await api.rejectFinding(f.id);
      toast.success("Rejected", { description: f.label });
      refresh();
    } catch (e) {
      toast.error("Reject failed", {
        description: e instanceof Error ? e.message : String(e),
      });
    }
  }

  // Keyboard shortcuts (chat / cine handle their own keys)
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tgt = e.target as HTMLElement | null;
      const tag = tgt?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tgt?.isContentEditable)
        return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      switch (e.key) {
        case "j":
          setActiveIdx((i) => Math.min(i + 1, Math.max(findings.length - 1, 0)));
          break;
        case "k":
          setActiveIdx((i) => Math.max(i - 1, 0));
          break;
        case "a":
          acceptCurrent();
          break;
        case "r":
          rejectCurrent();
          break;
        case "e":
          if (findings[activeIdx]) startRefine(findings[activeIdx]);
          break;
        case "s":
          if (report) sign();
          break;
        case "p":
          if (study?.patient_pseudonym) setPriorsOpen(true);
          break;
        case "?":
          setShortcutsOpen((v) => !v);
          break;
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [findings, activeIdx, report, study]);

  async function saveRefinement() {
    if (!refining) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.set("label", `${refining.label} (refined)`);
      fd.set(
        "geometry",
        JSON.stringify({
          kind: "polygon",
          ...(refining.geometry ?? {}),
          refined: true,
          tool: "brush",
        })
      );
      if (refining.icd10_suggestion)
        fd.set("icd10_suggestion", refining.icd10_suggestion);
      await api.refineFinding(refining.id, fd);
      toast.success("Refinement saved");
      setRefining(null);
      setActiveTool("WindowLevel");
      await refresh();
    } catch (e) {
      toast.error("Refine failed", {
        description: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setBusy(false);
    }
  }

  function loadPrior(priorStudyId: string) {
    // Fetch the prior's UID + drop its primary series into slot 2 (creates a 1x2 layout)
    api
      .getStudy(priorStudyId)
      .then((s) => {
        setLayout("1x2");
        setSlots((cur) => {
          const next = [...cur];
          // Slot 0 remains the current study
          next[1] = {
            id: `vp-prior-${priorStudyId.slice(0, 6)}`,
            studyInstanceUID: s.study_instance_uid,
            label: `Prior · ${s.modality} ${s.body_part}`,
          };
          return next;
        });
        setActiveSlot(1);
        setPriorsOpen(false);
        toast.info("Prior loaded into viewport 2");
      })
      .catch((e) =>
        toast.error("Couldn't load prior", {
          description: e instanceof Error ? e.message : String(e),
        })
      );
  }

  const activeSeriesUid = slots[activeSlot]?.seriesInstanceUID;

  const getActiveHandle = useCallback(
    () => handlesRef.current[activeSlot] ?? null,
    [activeSlot]
  );

  if (error)
    return (
      <Card className="border-destructive/30">
        <CardContent className="pt-4 text-sm text-destructive">
          {error}
        </CardContent>
      </Card>
    );

  if (!study)
    return (
      <div className="space-y-3">
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-[480px] w-full" />
      </div>
    );

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[200px_minmax(0,1fr)_360px]">
      <aside className="hidden lg:block">
        <SeriesPanel
          studyInstanceUID={study.study_instance_uid}
          activeSeriesUid={activeSeriesUid}
          onSelect={(uid) => {
            setSlots((cur) => {
              const next = [...cur];
              next[activeSlot] = { ...next[activeSlot], seriesInstanceUID: uid };
              return next;
            });
          }}
        />
      </aside>

      <section className="flex min-h-[600px] flex-col overflow-hidden rounded-lg border border-zinc-800 bg-black">
        <Toolbar active={activeTool} onChange={setActiveTool} />
        <div className="flex-1">
          <ViewportGrid
            studyInstanceUID={study.study_instance_uid}
            activeTool={activeTool}
            layout={layout}
            onLayoutChange={setLayout}
            slots={slots}
            setSlots={setSlots}
            activeSlotIdx={activeSlot}
            setActiveSlotIdx={setActiveSlot}
            sync={sync}
            setSync={setSync}
            registerHandle={(i, h) => {
              handlesRef.current[i] = h;
            }}
          />
        </div>
        <CineControls getActive={getActiveHandle} />
        {refining && (
          <div className="border-t border-primary/40 bg-primary/20 px-3 py-2 text-xs text-white backdrop-blur">
            <div className="flex items-center justify-between gap-2">
              <span>
                Refining <b>{refining.label}</b> · paint with the Brush tool,
                then save.
              </span>
              <div className="flex gap-1">
                <Button
                  size="sm"
                  variant="success"
                  onClick={saveRefinement}
                  disabled={busy}
                >
                  <Save />
                  Save refinement
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setRefining(null);
                    setActiveTool("WindowLevel");
                  }}
                  className="text-white hover:bg-white/10"
                >
                  Cancel
                </Button>
              </div>
            </div>
          </div>
        )}
      </section>

      <aside className="flex flex-col gap-4">
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <CardTitle className="truncate text-sm">
                  {study.description || "(no description)"}
                </CardTitle>
                <p className="mt-1 text-xs text-muted-foreground">
                  {study.modality} · {study.body_part} · UID{" "}
                  <span className="font-mono">
                    {study.study_instance_uid.slice(0, 18)}…
                  </span>
                </p>
              </div>
              <StatusPill state={study.state} />
            </div>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2 pt-0">
            <Button
              size="sm"
              variant="secondary"
              onClick={rerun}
              disabled={busy}
            >
              {busy ? (
                <Loader2 className="animate-spin" />
              ) : (
                <PlayCircle />
              )}
              Re-run inference
            </Button>
            <Button
              size="sm"
              variant="success"
              onClick={sign}
              disabled={busy || !report || !!report.signed_at}
              title={report?.signed_at ? "Report already signed" : undefined}
            >
              <CheckCircle2 />
              {report?.signed_at ? "Signed" : "Sign report"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setPriorsOpen(true)}
              disabled={!study.patient_pseudonym}
              title={
                !study.patient_pseudonym
                  ? "Patient pseudonym unknown"
                  : "Compare prior studies (P)"
              }
            >
              <History />
              Priors
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href={`/studies/${studyId}/plan`}>
                <Stethoscope />
                Plan
              </Link>
            </Button>
            <Button asChild size="sm" variant="outline" title="3D digital twin (research only)">
              <Link href={`/studies/${studyId}/twin`}>
                <Boxes />
                3D Twin
              </Link>
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setChatOpen(true)}
              title="Ask MedGemma about this study"
            >
              <MessageCircle />
              Chat
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setShortcutsOpen(true)}
              title="Keyboard shortcuts (?)"
            >
              <Keyboard />
              Keys
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="text-sm">Findings (current)</CardTitle>
            <span className="text-[10px] text-muted-foreground">
              {findings.length}
            </span>
          </CardHeader>
          <CardContent className="pt-0">
            {findings.length === 0 ? (
              <EmptyState
                icon={Inbox}
                title="No findings yet"
                description="Run inference to populate findings."
                className="border-0 bg-transparent p-0 text-left"
              />
            ) : (
              findings.map((f, i) => (
                <div
                  key={f.id}
                  onClick={() => setActiveIdx(i)}
                  className={cn(
                    "cursor-pointer rounded-md px-2 transition-colors",
                    i === activeIdx && "bg-primary/10 ring-1 ring-primary/30"
                  )}
                >
                  <FindingCard
                    finding={f}
                    onChanged={refresh}
                    onStartRefine={startRefine}
                    modality={study.modality}
                  />
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">ICD-10 picker</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 pt-0">
            <div className="relative">
              <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <input
                placeholder="Search code or description…"
                value={icdQuery}
                onChange={(e) => setIcdQuery(e.target.value)}
                className="w-full rounded-md border border-input bg-background py-1.5 pl-7 pr-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <ul className="max-h-40 divide-y divide-border overflow-auto text-xs">
              {icdResults.slice(0, 20).map((c) => (
                <li key={c.code} className="py-1">
                  <span className="font-mono text-foreground">{c.code}</span>{" "}
                  <span className="text-muted-foreground">
                    {c.description}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        {report && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Report</CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <Tabs defaultValue="draft">
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="draft">Draft</TabsTrigger>
                  <TabsTrigger value="narrative" disabled={!report.clinical_narrative}>
                    Narrative
                  </TabsTrigger>
                  <TabsTrigger value="export">Export</TabsTrigger>
                </TabsList>
                <TabsContent value="draft">
                  <pre className="whitespace-pre-wrap text-xs text-foreground">
                    {report.impression}
                  </pre>
                  <div className="mt-3 text-[10px] text-muted-foreground">
                    Requires licensed radiologist review and signature before
                    clinical use.
                  </div>
                </TabsContent>
                <TabsContent value="narrative">
                  <div className="rounded-md border border-warning/40 bg-warning/5 p-3">
                    <div className="mb-2 flex items-center gap-2 text-xs">
                      <Sparkles className="h-3.5 w-3.5 text-warning" />
                      <span className="font-medium">Clinical narrative</span>
                      <Badge variant="ai">MedGemma · experimental</Badge>
                    </div>
                    <pre className="whitespace-pre-wrap font-sans text-xs">
                      {report.clinical_narrative}
                    </pre>
                    {report.narrative_model && (
                      <div className="mt-3 border-t border-warning/30 pt-2 text-[10px] text-muted-foreground">
                        <code className="font-mono">
                          {report.narrative_model}
                        </code>
                        {report.narrative_generated_at && (
                          <>
                            {" "}
                            at{" "}
                            {new Date(
                              report.narrative_generated_at
                            ).toLocaleString()}
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </TabsContent>
                <TabsContent value="export">
                  <div className="flex flex-col gap-2">
                    {report.sr_available && (
                      <Button asChild variant="outline" size="sm">
                        <a href={`/api/v1/reports/${report.id}/sr`}>
                          <Download />
                          Download DICOM SR
                        </a>
                      </Button>
                    )}
                    <Button asChild variant="outline" size="sm">
                      <a href={`/api/v1/reports/${report.id}/fhir`}>
                        <FileJson />
                        Download FHIR JSON
                      </a>
                    </Button>
                    {report.signed_at ? (
                      <div className="flex items-center gap-1.5 text-xs text-success">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        Signed{" "}
                        {new Date(report.signed_at).toLocaleString()}
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <FileText className="h-3.5 w-3.5" />
                        Unsigned
                      </div>
                    )}
                  </div>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        )}
      </aside>

      <PriorsPicker
        open={priorsOpen}
        onOpenChange={setPriorsOpen}
        pseudonym={study.patient_pseudonym ?? null}
        currentStudyId={studyId}
        onSelect={loadPrior}
      />
      <KeyboardShortcuts open={shortcutsOpen} onOpenChange={setShortcutsOpen} />

      <Sheet open={chatOpen} onOpenChange={setChatOpen}>
        <SheetContent className="flex w-full flex-col p-0 sm:max-w-md">
          <SheetHeader className="px-4 py-3">
            <SheetTitle className="flex items-center gap-2 text-sm">
              <Sparkles className="h-4 w-4 text-primary" />
              MedGemma chat
            </SheetTitle>
          </SheetHeader>
          <div className="flex-1 overflow-hidden">
            <MedGemmaChat studyId={studyId} />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
