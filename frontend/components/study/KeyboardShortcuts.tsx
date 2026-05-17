"use client";

import * as React from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Kbd } from "@/components/ui/kbd";

const SHORTCUTS: { keys: string[]; label: string }[] = [
  { keys: ["J"], label: "Next finding" },
  { keys: ["K"], label: "Previous finding" },
  { keys: ["A"], label: "Accept current finding" },
  { keys: ["R"], label: "Reject current finding" },
  { keys: ["E"], label: "Refine current finding" },
  { keys: ["S"], label: "Sign report" },
  { keys: ["P"], label: "Compare priors" },
  { keys: ["Tab"], label: "Cycle active viewport" },
  { keys: ["Space"], label: "Play / pause cine" },
  { keys: ["["], label: "Cine slower (fps −1)" },
  { keys: ["]"], label: "Cine faster (fps +1)" },
  { keys: ["?"], label: "Show this overlay" },
  { keys: ["⌘", "K"], label: "Open command palette" },
];

export function KeyboardShortcuts({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Keyboard shortcuts</DialogTitle>
          <DialogDescription>
            Fast keys for the study reading workflow.
          </DialogDescription>
        </DialogHeader>
        <ul className="grid grid-cols-1 gap-1 text-sm">
          {SHORTCUTS.map((s) => (
            <li
              key={s.label}
              className="flex items-center justify-between rounded-md px-2 py-1.5 hover:bg-muted"
            >
              <span className="text-foreground">{s.label}</span>
              <span className="flex items-center gap-1">
                {s.keys.map((k, i) => (
                  <Kbd key={i}>{k}</Kbd>
                ))}
              </span>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  );
}
