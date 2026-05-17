"use client";

import { ShieldAlert, Search, Command } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ThemeToggle } from "./ThemeToggle";
import { UserMenu } from "./UserMenu";
import { Kbd } from "@/components/ui/kbd";

export function Topbar() {
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <button
        type="button"
        onClick={() =>
          window.dispatchEvent(
            new KeyboardEvent("keydown", { key: "k", metaKey: true })
          )
        }
        className="hidden flex-1 items-center gap-2 rounded-md border bg-surface px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted md:flex md:max-w-md"
      >
        <Search className="h-3.5 w-3.5" />
        Search studies, patients…
        <span className="ml-auto inline-flex items-center gap-1">
          <Kbd>
            <Command className="h-2.5 w-2.5" />
          </Kbd>
          <Kbd>K</Kbd>
        </span>
      </button>
      <div className="ml-auto flex items-center gap-2">
        <TooltipProvider delayDuration={300}>
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge
                variant="destructive"
                className="cursor-help gap-1.5 py-1"
              >
                <ShieldAlert className="h-3 w-3" />
                Research only
              </Badge>
            </TooltipTrigger>
            <TooltipContent className="max-w-sm">
              Outputs from this system are not FDA cleared and must not be used
              for diagnosis, treatment, or clinical decision-making.
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}
