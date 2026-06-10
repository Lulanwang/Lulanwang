"use client";

import { useEffect } from "react";
import { Filter, X } from "lucide-react";
import useSWR from "swr";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";

export type WorklistFilters = {
  modality?: string;
  body_part?: string;
  state?: string;
  has_findings?: boolean;
};

export function FilterSidebar({
  filters,
  onChange,
}: {
  filters: WorklistFilters;
  onChange: (f: WorklistFilters) => void;
}) {
  const { data, isLoading } = useSWR("/studies/facets", () =>
    api.listStudyFacets()
  );

  const activeCount = Object.values(filters).filter(
    (v) => v !== undefined && v !== "" && v !== null
  ).length;

  useEffect(() => {
    // no-op — placeholder for future facet refresh on URL change
  }, [filters]);

  return (
    <Card className="sticky top-4 h-fit">
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="flex items-center gap-1.5 text-xs uppercase tracking-wide text-muted-foreground">
          <Filter className="h-3.5 w-3.5" /> Filters
        </CardTitle>
        {activeCount > 0 && (
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-1.5 text-[10px]"
            onClick={() => onChange({})}
          >
            <X className="h-3 w-3" />
            Clear
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-4 pt-0">
        <FacetGroup
          label="Modality"
          loading={isLoading}
          options={data?.modalities ?? []}
          value={filters.modality}
          onChange={(v) =>
            onChange({ ...filters, modality: v === filters.modality ? undefined : v })
          }
        />
        <FacetGroup
          label="Body part"
          loading={isLoading}
          options={data?.body_parts ?? []}
          value={filters.body_part}
          onChange={(v) =>
            onChange({
              ...filters,
              body_part: v === filters.body_part ? undefined : v,
            })
          }
        />
        <FacetGroup
          label="State"
          loading={isLoading}
          options={data?.states ?? []}
          value={filters.state}
          onChange={(v) =>
            onChange({ ...filters, state: v === filters.state ? undefined : v })
          }
        />
        <div>
          <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            AI findings
          </div>
          <div className="flex flex-wrap gap-1">
            <FilterChip
              active={filters.has_findings === true}
              onClick={() =>
                onChange({
                  ...filters,
                  has_findings: filters.has_findings === true ? undefined : true,
                })
              }
            >
              with findings
            </FilterChip>
            <FilterChip
              active={filters.has_findings === false}
              onClick={() =>
                onChange({
                  ...filters,
                  has_findings:
                    filters.has_findings === false ? undefined : false,
                })
              }
            >
              none
            </FilterChip>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function FacetGroup({
  label,
  options,
  value,
  onChange,
  loading,
}: {
  label: string;
  options: string[];
  value: string | undefined;
  onChange: (v: string) => void;
  loading?: boolean;
}) {
  return (
    <div>
      <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="flex flex-wrap gap-1">
        {loading && <Skeleton className="h-5 w-16" />}
        {!loading &&
          options.map((o) => (
            <FilterChip
              key={o}
              active={value === o}
              onClick={() => onChange(o)}
            >
              {o}
            </FilterChip>
          ))}
        {!loading && options.length === 0 && (
          <span className="text-[10px] text-muted-foreground">—</span>
        )}
      </div>
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide transition-colors",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border text-muted-foreground hover:border-primary/40 hover:text-foreground"
      )}
    >
      {children}
    </button>
  );
}
