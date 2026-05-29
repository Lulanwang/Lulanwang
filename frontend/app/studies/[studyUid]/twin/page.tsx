"use client";

/**
 * Round 12 — interactive 3D digital twin viewer.
 *
 * Reconstructs the primary organ for the study's body part (brain MR,
 * lung CT, breast MG) plus any current findings, color-coded. The mesh
 * is built server-side by classical computer vision; this page just
 * streams the resulting glTF-binary and renders it with three.js.
 *
 * The Canvas component is loaded via next/dynamic with ssr:false so
 * three.js stays out of the server bundle and Next 15 RSC stays happy.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { ArrowLeft, Boxes, Loader2, RefreshCcw } from "lucide-react";
import { toast } from "sonner";
import { api, type OrganTwin, type TwinStatus } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ResearchTwinBanner } from "@/components/twin/ResearchTwinBanner";

const TwinViewer = dynamic(() => import("@/components/twin/TwinViewer"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center rounded-md border bg-muted/30">
      <Skeleton className="h-32 w-32 rounded-md" />
    </div>
  ),
});

const POLL_MS = 2500;
const POLL_TIMEOUT_MS = 5 * 60 * 1000;

export default function TwinPage() {
  const params = useParams<{ studyUid: string }>();
  const studyId = params.studyUid;
  const [twin, setTwin] = useState<OrganTwin | null | undefined>(undefined);
  const [generating, setGenerating] = useState(false);
  const pollStartRef = useRef<number | null>(null);

  const load = useCallback(async (): Promise<OrganTwin | null> => {
    try {
      const t = await api.getTwin(studyId);
      setTwin(t);
      return t;
    } catch (e) {
      if (e instanceof Error && e.message.includes("404")) {
        setTwin(null);
        return null;
      }
      toast.error("Failed to load twin", {
        description: e instanceof Error ? e.message : String(e),
      });
      setTwin(null);
      return null;
    }
  }, [studyId]);

  useEffect(() => {
    load();
  }, [load]);

  // Poll while the twin is queued/running.
  useEffect(() => {
    if (!twin || (twin.status !== "queued" && twin.status !== "running")) {
      pollStartRef.current = null;
      return;
    }
    if (pollStartRef.current === null) pollStartRef.current = Date.now();
    const handle = setInterval(async () => {
      const elapsed = Date.now() - (pollStartRef.current ?? Date.now());
      if (elapsed > POLL_TIMEOUT_MS) {
        clearInterval(handle);
        toast.error("Twin generation timed out");
        return;
      }
      const next = await load();
      if (next && next.status === "succeeded") {
        toast.success("Twin ready");
        clearInterval(handle);
      } else if (next && next.status === "failed") {
        toast.error("Twin generation failed", {
          description: next.error ?? undefined,
        });
        clearInterval(handle);
      }
    }, POLL_MS);
    return () => clearInterval(handle);
  }, [twin, load]);

  const startGeneration = async (force = false) => {
    setGenerating(true);
    try {
      const { status } = await api.generateTwin(studyId, force);
      if (status === "succeeded") {
        toast.success("Twin already cached — loading");
      } else {
        toast.info("Twin generation queued");
      }
      await load();
    } catch (e) {
      toast.error("Could not start twin generation", {
        description: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col gap-3 p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button asChild variant="ghost" size="sm">
            <Link href={`/studies/${studyId}`}>
              <ArrowLeft className="h-4 w-4" /> Back to study
            </Link>
          </Button>
          <h1 className="flex items-center gap-2 text-lg font-semibold">
            <Boxes className="h-5 w-5" /> 3D Digital Twin
          </h1>
        </div>
        {twin && twin.status === "succeeded" && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => startGeneration(true)}
            disabled={generating}
          >
            <RefreshCcw className="h-3.5 w-3.5" /> Regenerate
          </Button>
        )}
      </div>

      <ResearchTwinBanner />

      <div className="flex-1 overflow-hidden">
        {twin === undefined && (
          <div className="flex h-full items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        )}
        {twin === null && (
          <EmptyState
            icon={Boxes}
            title="No twin generated yet"
            description="Reconstruct a 3D mesh of the primary organ plus any current findings for this study. Generation runs in the background and takes 10-60 seconds depending on series size."
            action={
              <Button
                onClick={() => startGeneration(false)}
                disabled={generating}
              >
                {generating && <Loader2 className="h-4 w-4 animate-spin" />}
                Generate 3D twin
              </Button>
            }
          />
        )}
        {twin && (twin.status === "queued" || twin.status === "running") && (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
            <p>
              {twin.status === "queued"
                ? "Twin generation queued…"
                : "Reconstructing organ mesh…"}
            </p>
            <p className="text-[10px]">
              Loading the DICOM series, segmenting the {twin.body_part || "organ"},
              running marching cubes, and exporting glTF. Hold tight.
            </p>
          </div>
        )}
        {twin && twin.status === "failed" && (
          <div className="flex h-full flex-col items-center justify-center gap-3 rounded-md border border-destructive/40 bg-destructive/10 p-6 text-center text-sm">
            <p className="font-medium text-destructive">
              Twin generation failed
            </p>
            <p className="text-xs text-muted-foreground">
              {twin.error ?? "Unknown error"}
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => startGeneration(true)}
              disabled={generating}
            >
              Retry
            </Button>
          </div>
        )}
        {twin && twin.status === "succeeded" && (
          <TwinViewer studyId={studyId} twin={twin} />
        )}
      </div>
    </div>
  );
}

// Suppress unused-import lint for the TwinStatus type that is implicitly
// referenced via OrganTwin.status — keep the import so future edits
// stay strict.
export type _TwinStatus = TwinStatus;
