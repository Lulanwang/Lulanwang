"use client";

/**
 * Three.js + react-three-fiber canvas for the digital twin GLB.
 *
 * Loaded via next/dynamic with ssr:false from the twin page so three
 * never enters the server bundle. The bearer-token-authed GLB ArrayBuffer
 * comes from `api.fetchTwinGlb` (drei's useGLTF cannot send the token).
 */
import { useEffect, useRef, useState } from "react";
import {
  Bounds,
  OrbitControls,
  PerspectiveCamera,
} from "@react-three/drei";
import { Canvas, useThree } from "@react-three/fiber";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { Group, Mesh, Object3D, MeshStandardMaterial } from "three";
import { toast } from "sonner";
import { api, type OrganTwin } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Camera, Download, RotateCcw } from "lucide-react";
import {
  StructurePanel,
  type StructureUIState,
} from "@/components/twin/StructurePanel";

type Props = {
  studyId: string;
  twin: OrganTwin;
};

export default function TwinViewer({ studyId, twin }: Props) {
  const [scene, setScene] = useState<Group | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [uiState, setUiState] = useState<Record<string, StructureUIState>>(() =>
    initState(twin)
  );
  const fitTriggerRef = useRef(0);

  // Load the authenticated GLB once per (study, config) tuple. We do this
  // inside the page rather than a drei hook so the Authorization header
  // is included on the fetch.
  useEffect(() => {
    let cancelled = false;
    let group: Group | null = null;
    api
      .fetchTwinGlb(studyId)
      .then((buf) => {
        new GLTFLoader().parse(
          buf,
          "",
          (gltf) => {
            if (cancelled) return;
            group = gltf.scene;
            setScene(group);
          },
          (err) => {
            if (!cancelled) {
              const msg =
                err instanceof Error
                  ? err.message
                  : err && typeof err === "object" && "message" in err
                    ? String((err as { message: unknown }).message)
                    : String(err);
              setLoadError(msg);
            }
          }
        );
      })
      .catch((e) => {
        if (!cancelled) setLoadError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
      if (group) disposeScene(group);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studyId, twin.id]);

  // Mirror StructurePanel state changes into the live three scene.
  useEffect(() => {
    if (!scene) return;
    scene.traverse((obj: Object3D) => {
      if (!(obj as Mesh).isMesh) return;
      const mesh = obj as Mesh;
      const st = uiState[mesh.name];
      if (!st) return;
      mesh.visible = st.visible;
      const mat = mesh.material as MeshStandardMaterial | MeshStandardMaterial[];
      const apply = (m: MeshStandardMaterial) => {
        m.transparent = st.opacity < 1;
        m.opacity = st.opacity;
        m.depthWrite = st.opacity >= 0.99;
        m.needsUpdate = true;
      };
      if (Array.isArray(mat)) mat.forEach(apply);
      else apply(mat);
    });
  }, [uiState, scene]);

  const onPatchStructure = (name: string, patch: Partial<StructureUIState>) =>
    setUiState((prev) => ({
      ...prev,
      [name]: { ...(prev[name] ?? { visible: true, opacity: 1 }), ...patch },
    }));

  if (loadError) {
    return (
      <div className="flex h-full items-center justify-center rounded-md border bg-card p-6 text-center text-sm">
        <div>
          <p className="font-medium">Couldn't load the twin mesh</p>
          <p className="mt-1 text-xs text-muted-foreground">{loadError}</p>
        </div>
      </div>
    );
  }

  if (!scene) {
    return (
      <div className="flex h-full items-center justify-center rounded-md border bg-muted/30">
        <Skeleton className="h-32 w-32 rounded-md" />
      </div>
    );
  }

  return (
    <div className="grid h-full grid-cols-[1fr_280px] gap-3">
      <div className="relative rounded-md border bg-[#0e1119]">
        <Canvas
          dpr={[1, 2]}
          gl={{ preserveDrawingBuffer: true, antialias: true }}
        >
          <PerspectiveCamera makeDefault position={[200, 200, 320]} fov={40} />
          <ambientLight intensity={0.6} />
          <hemisphereLight color="#ffffff" groundColor="#222236" intensity={0.7} />
          <directionalLight position={[300, 400, 250]} intensity={0.9} />
          <directionalLight position={[-200, -100, 200]} intensity={0.3} />
          <Bounds fit clip observe margin={1.2} key={fitTriggerRef.current}>
            <primitive object={scene} />
          </Bounds>
          <OrbitControls makeDefault enableDamping dampingFactor={0.1} />
          <ScreenshotBridge />
        </Canvas>
        <ViewerOverlay
          twin={twin}
          onReset={() => {
            fitTriggerRef.current += 1;
            setUiState(initState(twin));
            toast.success("View reset");
          }}
          onDownload={() => downloadGlb(studyId)}
        />
      </div>
      <div className="space-y-3 overflow-y-auto">
        <div className="rounded-md border bg-card p-2">
          <p className="px-1 pb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Structures
          </p>
          <StructurePanel
            structures={twin.structures ?? []}
            state={uiState}
            onChange={onPatchStructure}
          />
        </div>
        <Legend twin={twin} />
      </div>
    </div>
  );
}

function ViewerOverlay({
  twin,
  onReset,
  onDownload,
}: {
  twin: OrganTwin;
  onReset: () => void;
  onDownload: () => void;
}) {
  return (
    <div className="pointer-events-none absolute inset-0 flex flex-col p-2">
      <div className="flex items-center justify-between gap-2">
        <div className="pointer-events-auto rounded-md bg-background/70 px-2 py-1 text-[10px] text-muted-foreground backdrop-blur">
          {twin.body_part || "—"} · {twin.seg_config_version} ·{" "}
          {twin.glb_bytes
            ? `${(twin.glb_bytes / 1024).toFixed(0)} KB`
            : "—"}
        </div>
        <div className="pointer-events-auto flex gap-1">
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={onReset}
            aria-label="Reset view"
          >
            <RotateCcw className="h-3.5 w-3.5" /> Reset
          </Button>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={() => screenshotCanvas()}
            aria-label="Screenshot"
          >
            <Camera className="h-3.5 w-3.5" /> Snap
          </Button>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={onDownload}
            aria-label="Download GLB"
          >
            <Download className="h-3.5 w-3.5" /> GLB
          </Button>
        </div>
      </div>
    </div>
  );
}

function Legend({ twin }: { twin: OrganTwin }) {
  const list = twin.structures ?? [];
  return (
    <div className="rounded-md border bg-card p-2 text-[10px] text-muted-foreground">
      <p className="px-1 pb-1 font-medium uppercase tracking-wide">Legend</p>
      <ul className="space-y-1 px-1">
        {list.map((s) => (
          <li key={s.name} className="flex items-center gap-2">
            <span
              className="inline-block h-2 w-2 rounded-sm"
              style={{ background: s.color }}
            />
            <span className="flex-1 truncate">
              {s.kind === "organ" ? "Organ envelope" : s.name}
            </span>
            <span>{s.volume_cm3.toFixed(1)} cm³</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ScreenshotBridge() {
  // Stash the GL context's canvas on window so the overlay button can
  // grab a PNG without prop-drilling.
  const { gl } = useThree();
  useEffect(() => {
    (window as unknown as { __lulanTwinCanvas?: HTMLCanvasElement }).__lulanTwinCanvas =
      gl.domElement;
    return () => {
      (window as unknown as { __lulanTwinCanvas?: HTMLCanvasElement }).__lulanTwinCanvas =
        undefined;
    };
  }, [gl]);
  return null;
}

function screenshotCanvas() {
  const canvas = (window as unknown as { __lulanTwinCanvas?: HTMLCanvasElement })
    .__lulanTwinCanvas;
  if (!canvas) {
    toast.error("Canvas not ready");
    return;
  }
  try {
    const url = canvas.toDataURL("image/png");
    const a = document.createElement("a");
    a.href = url;
    a.download = `twin-${Date.now()}.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    toast.success("Snapshot saved");
  } catch (e) {
    toast.error("Snapshot failed", {
      description: e instanceof Error ? e.message : String(e),
    });
  }
}

async function downloadGlb(studyId: string) {
  try {
    const buf = await api.fetchTwinGlb(studyId);
    const blob = new Blob([buf], { type: "model/gltf-binary" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `twin-${studyId}.glb`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    toast.error("GLB download failed", {
      description: e instanceof Error ? e.message : String(e),
    });
  }
}

function initState(twin: OrganTwin): Record<string, StructureUIState> {
  const out: Record<string, StructureUIState> = {};
  for (const s of twin.structures ?? []) {
    out[s.name] = {
      visible: true,
      opacity: s.kind === "organ" ? 0.35 : 1,
    };
  }
  return out;
}

function disposeScene(group: Group) {
  group.traverse((obj: Object3D) => {
    const mesh = obj as Mesh;
    if (mesh.isMesh) {
      mesh.geometry?.dispose();
      const mat = mesh.material as MeshStandardMaterial | MeshStandardMaterial[];
      if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
      else mat?.dispose();
    }
  });
}
