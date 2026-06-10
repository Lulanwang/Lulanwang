"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/**
 * DICOM viewer pane.
 *
 * In production this is where OHIF Viewer v3 is embedded against our
 * authenticated /dicom-web endpoint. OHIF expects to bootstrap with a
 * StudyInstanceUID and a DICOMweb data source root; both are available
 * via /dicom-web (proxied through FastAPI with JWT auth and audit).
 *
 * For the MVP build we render a clearly-labeled placeholder so the
 * shell deploys cleanly without bundling the ~30MB OHIF web build.
 * Drop-in upgrade path: replace this component with
 *   <iframe src={`/ohif/?StudyInstanceUIDs=${study.study_instance_uid}`} />
 * once an OHIF static build is mounted at /ohif by Caddy.
 */
export default function ViewerPage() {
  const params = useParams<{ studyUid: string }>();
  const studyId = params.studyUid;
  const [study, setStudy] = useState<Awaited<ReturnType<typeof api.getStudy>> | null>(null);

  useEffect(() => {
    api.getStudy(studyId).then(setStudy).catch(() => setStudy(null));
  }, [studyId]);

  return (
    <div className="flex h-full min-h-[60vh] flex-col items-center justify-center gap-3 rounded-lg border bg-black text-white">
      <div className="text-[10px] uppercase tracking-widest text-zinc-500">
        DICOM viewer
      </div>
      <div className="text-sm">
        {study ? (
          <>
            Study{" "}
            <span className="font-mono">{study.study_instance_uid}</span>
            <br />
            Modality {study.modality} · Body part {study.body_part}
          </>
        ) : (
          "Loading study…"
        )}
      </div>
      <div className="max-w-md px-6 text-center text-xs leading-relaxed text-zinc-400">
        OHIF Viewer v3 mounts here. The frontend fetches images via
        <code className="mx-1 rounded bg-zinc-800 px-1">/dicom-web/*</code>
        which Caddy routes to FastAPI&apos;s authenticated DICOMweb proxy.
        Every WADO-RS pull is recorded in the audit log.
      </div>
    </div>
  );
}
