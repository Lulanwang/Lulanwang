"use client";

import useSWR, { type SWRConfiguration } from "swr";
import { request, type Report } from "@/lib/api";

const fetcher = <T>(path: string) => request<T>(path);

export function useStudy(id: string | null | undefined) {
  return useSWR(id ? `/studies/${id}` : null, fetcher);
}

export function useStudies(query?: string) {
  return useSWR(`/studies/${query ? `?${query}` : ""}`, fetcher, {
    refreshInterval: 0,
  });
}

export function useFindings(
  studyId: string | null | undefined,
  includeHistory = false
) {
  return useSWR(
    studyId
      ? `/studies/${studyId}/findings${
          includeHistory ? "?include_history=true" : ""
        }`
      : null,
    fetcher
  );
}

export function useReport(studyId: string | null | undefined) {
  return useSWR<Report>(
    studyId ? `/reports/study/${studyId}` : null,
    fetcher,
    { shouldRetryOnError: false }
  );
}

export function useAudit() {
  return useSWR("/audit/", fetcher, { refreshInterval: 0 });
}

export function useMe() {
  return useSWR("/auth/me", fetcher, { shouldRetryOnError: false });
}

export function swrConfig(): SWRConfiguration {
  return { revalidateOnFocus: false, shouldRetryOnError: false };
}
