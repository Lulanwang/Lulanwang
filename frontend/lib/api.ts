"use client";

const BASE = process.env.NEXT_PUBLIC_API_BASE || "/api/v1";

export type Report = {
  id: string;
  study_id: string;
  impression: string;
  icd10_codes: string[];
  fhir_diagnostic_report: Record<string, unknown> | null;
  signed_at: string | null;
  signed_by: string | null;
  sr_available: boolean;
  clinical_narrative: string | null;
  narrative_model: string | null;
  narrative_generated_at: string | null;
};

export type Finding = {
  id: string;
  study_id?: string;
  parent_finding_id: string | null;
  version: number;
  is_current: boolean;
  source: "ai" | "radiologist";
  status: "proposed" | "accepted" | "rejected" | "modified";
  actor_id: string | null;
  label: string;
  body_part: string;
  confidence: number | null;
  icd10_suggestion: string | null;
  geometry: Record<string, unknown> | null;
  model_name: string;
  model_version: string;
  seg_sop_instance_uid: string | null;
  created_at?: string;
};

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("lulan_token");
}

export function setToken(t: string | null) {
  if (typeof window === "undefined") return;
  if (t) window.localStorage.setItem("lulan_token", t);
  else window.localStorage.removeItem("lulan_token");
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const tok = getToken();
  if (tok) headers.set("Authorization", `Bearer ${tok}`);
  if (!headers.has("Content-Type") && init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401) {
    setToken(null);
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("unauthorized");
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.headers.get("content-type")?.includes("application/json")
    ? ((await res.json()) as T)
    : ((await res.text()) as unknown as T);
}

export const api = {
  login: (email: string, password: string) =>
    request<{ token: string; role: string; user_id: string; full_name: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<{ user_id: string; email: string; role: string; full_name: string }>("/auth/me"),

  listStudies: () =>
    request<
      Array<{
        id: string;
        study_instance_uid: string;
        modality: string;
        body_part: string;
        description: string;
        state: string;
        finding_count: number;
      }>
    >("/studies/"),
  getStudy: (id: string) =>
    request<{
      id: string;
      study_instance_uid: string;
      modality: string;
      body_part: string;
      description: string;
      state: string;
      finding_count: number;
    }>(`/studies/${id}`),
  listFindings: (id: string, includeHistory = false) =>
    request<Finding[]>(
      `/studies/${id}/findings${includeHistory ? "?include_history=true" : ""}`
    ),

  // Versioning state machine
  acceptFinding: (id: string, icd10_override?: string) =>
    request<Finding>(`/findings/${id}/accept`, {
      method: "POST",
      body: JSON.stringify({ icd10_override: icd10_override ?? null }),
    }),
  rejectFinding: (id: string) =>
    request<Finding>(`/findings/${id}/reject`, { method: "POST" }),
  refineFinding: (id: string, body: FormData) =>
    request<Finding>(`/findings/${id}/refine`, { method: "POST", body }),
  findingHistory: (id: string) =>
    request<Finding[]>(`/findings/${id}/history`),

  runInference: (id: string) =>
    request<{ job_id: string; status: string }>(`/studies/${id}/run-inference`, { method: "POST" }),
  signReport: (id: string) =>
    request<{ report_id: string; signed_at: string }>(`/studies/${id}/sign`, { method: "POST" }),

  getReport: (studyId: string) => request<Report>(`/reports/study/${studyId}`),

  searchIcd10: (q: string) =>
    request<
      Array<{ code: string; description: string; category: string; body_part: string }>
    >(`/icd10/search?q=${encodeURIComponent(q)}`),

  dashboardKpis: () =>
    request<{
      studies_7d: number;
      signed_reports: number;
      mean_latency_ms: number;
      accept_rate: number | null;
      reviewed_findings: number;
    }>("/dashboard/kpis"),
  dashboardStudiesPerDay: (days = 30) =>
    request<Array<{ date: string; count: number }>>(
      `/dashboard/studies-per-day?days=${days}`
    ),
  dashboardModalityBreakdown: () =>
    request<Array<{ modality: string; count: number }>>(
      "/dashboard/modality-breakdown"
    ),
  dashboardRecentActivity: (limit = 10) =>
    request<
      Array<{
        id: string;
        created_at: string | null;
        action: string;
        actor_role: string | null;
        resource_type: string | null;
        resource_id: string | null;
      }>
    >(`/dashboard/recent-activity?limit=${limit}`),
  dashboardUnsigned: (limit = 5) =>
    request<
      Array<{
        id: string;
        description: string;
        modality: string;
        body_part: string;
        state: string;
        created_at: string | null;
      }>
    >(`/dashboard/unsigned-studies?limit=${limit}`),

  listAudit: () =>
    request<
      Array<{
        id: string;
        created_at: string;
        actor_id: string | null;
        actor_role: string | null;
        action: string;
        resource_type: string | null;
        resource_id: string | null;
        request_id: string | null;
        ip: string | null;
        details: Record<string, unknown> | null;
      }>
    >("/audit/"),
};

export { request };
