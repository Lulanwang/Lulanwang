"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  LayoutDashboard,
  ListChecks,
  Users,
  BarChart3,
  ShieldCheck,
  Search,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

const SHORTCUTS = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Worklist", href: "/worklist", icon: ListChecks },
  { label: "Patients", href: "/patients", icon: Users },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
  { label: "Audit", href: "/admin/audit", icon: ShieldCheck },
];

export function CommandPalette() {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const router = useRouter();

  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const filtered = SHORTCUTS.filter((s) =>
    s.label.toLowerCase().includes(query.toLowerCase())
  );

  function go(href: string) {
    setOpen(false);
    setQuery("");
    router.push(href);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-lg gap-0 overflow-hidden p-0">
        <DialogTitle className="sr-only">Command palette</DialogTitle>
        <DialogDescription className="sr-only">
          Quickly jump to any page in Lulan
        </DialogDescription>
        <div className="flex items-center gap-2 border-b px-3 py-2">
          <Search className="h-4 w-4 text-muted-foreground" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Jump to…"
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
        </div>
        <ul className="max-h-72 overflow-auto py-1 text-sm">
          {filtered.length === 0 && (
            <li className="px-3 py-4 text-xs text-muted-foreground">
              No matches
            </li>
          )}
          {filtered.map((s) => (
            <li key={s.href}>
              <button
                onClick={() => go(s.href)}
                className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-muted"
              >
                <s.icon className="h-4 w-4 text-muted-foreground" />
                <span>{s.label}</span>
                <span className="ml-auto text-[10px] text-muted-foreground">
                  {s.href}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  );
}
