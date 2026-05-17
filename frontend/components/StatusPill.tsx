import {
  CheckCircle2,
  Clock,
  CircleAlert,
  FileText,
  Loader2,
  Inbox,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Badge, type BadgeProps } from "@/components/ui/badge";

const STATE: Record<
  string,
  { variant: BadgeProps["variant"]; icon: React.ComponentType<{ className?: string }>; label?: string }
> = {
  received: { variant: "secondary", icon: Inbox },
  deidentified: { variant: "secondary", icon: ShieldCheck },
  queued: { variant: "warning", icon: Clock },
  inferring: { variant: "warning", icon: Loader2, label: "inferring" },
  inferred: { variant: "success", icon: Sparkles },
  reported: { variant: "success", icon: FileText },
  signed: { variant: "success", icon: CheckCircle2 },
  failed: { variant: "destructive", icon: CircleAlert },
};

export function StatusPill({ state }: { state: string }) {
  const cfg = STATE[state] || { variant: "secondary" as const, icon: Inbox };
  const Icon = cfg.icon;
  return (
    <Badge variant={cfg.variant}>
      <Icon
        className={state === "inferring" ? "animate-spin" : undefined}
        aria-hidden="true"
      />
      {cfg.label ?? state}
    </Badge>
  );
}
