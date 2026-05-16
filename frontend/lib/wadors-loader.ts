"use client";

/**
 * Translate a WADO-RS study browse into a list of imageIds that the
 * Cornerstone3D image loader can stream.
 *
 * Cornerstone's wadors loader expects imageIds of the form
 *   `wadors:<base>/studies/<studyUID>/series/<seriesUID>/instances/<sopUID>/frames/1`
 *
 * Our backend's authenticated DICOMweb proxy is at /dicom-web — every
 * QIDO/WADO call below goes through it, so the audit log captures the
 * pull and JWT auth is applied.
 */

const DICOMWEB_BASE = "/dicom-web";

function bearer(): HeadersInit {
  if (typeof window === "undefined") return {};
  const t = window.localStorage.getItem("lulan_token");
  return t
    ? { Authorization: `Bearer ${t}`, Accept: "application/dicom+json" }
    : { Accept: "application/dicom+json" };
}

async function qido<T>(path: string): Promise<T> {
  const r = await fetch(`${DICOMWEB_BASE}/${path}`, { headers: bearer() });
  if (!r.ok) throw new Error(`DICOMweb ${path} → ${r.status}`);
  // QIDO returns 204 for no matches
  if (r.status === 204) return [] as unknown as T;
  return (await r.json()) as T;
}

type Tag = { Value?: unknown[] };
type Dataset = Record<string, Tag>;

function get(ds: Dataset, key: string): string | undefined {
  const v = ds[key]?.Value?.[0];
  return v == null ? undefined : String(v);
}

export type Series = {
  seriesInstanceUID: string;
  modality: string;
  seriesDescription: string;
  instanceCount: number;
};

export async function listSeries(studyInstanceUID: string): Promise<Series[]> {
  const rows = await qido<Dataset[]>(`studies/${studyInstanceUID}/series`);
  return rows.map((r) => ({
    seriesInstanceUID: get(r, "0020000E") ?? "",
    modality: get(r, "00080060") ?? "",
    seriesDescription: get(r, "0008103E") ?? "",
    instanceCount: Number(get(r, "00201209") ?? "0"),
  }));
}

export async function listInstances(
  studyInstanceUID: string,
  seriesInstanceUID: string
): Promise<string[]> {
  const rows = await qido<Dataset[]>(
    `studies/${studyInstanceUID}/series/${seriesInstanceUID}/instances`
  );
  // Sort by InstanceNumber so the stack scrolls in anatomic order
  const sorted = rows
    .map((r) => ({
      sop: get(r, "00080018") ?? "",
      idx: Number(get(r, "00200013") ?? "0"),
    }))
    .filter((x) => x.sop)
    .sort((a, b) => a.idx - b.idx);
  return sorted.map((x) => x.sop);
}

export function imageIdFor(
  studyInstanceUID: string,
  seriesInstanceUID: string,
  sopInstanceUID: string
): string {
  // Cornerstone resolves wadors: against an absolute origin, so we
  // construct the full URL.
  const origin = typeof window === "undefined" ? "" : window.location.origin;
  return `wadors:${origin}${DICOMWEB_BASE}/studies/${studyInstanceUID}/series/${seriesInstanceUID}/instances/${sopInstanceUID}/frames/1`;
}

export async function buildStackImageIds(studyInstanceUID: string): Promise<{
  series: Series[];
  primary: Series | null;
  imageIds: string[];
}> {
  const series = await listSeries(studyInstanceUID);
  // Prefer the longest series that is an actual image modality
  const imaging = series
    .filter((s) => ["CT", "MR", "MG", "CR", "DX", "US"].includes(s.modality))
    .sort((a, b) => b.instanceCount - a.instanceCount);
  const primary = imaging[0] ?? series[0] ?? null;
  if (!primary) return { series, primary: null, imageIds: [] };

  const sopUIDs = await listInstances(studyInstanceUID, primary.seriesInstanceUID);
  const imageIds = sopUIDs.map((sop) =>
    imageIdFor(studyInstanceUID, primary.seriesInstanceUID, sop)
  );
  return { series, primary, imageIds };
}
