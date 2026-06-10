"use client";

import { usePathname } from "next/navigation";
import { ThemeProvider } from "./ThemeProvider";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { CommandPalette } from "./CommandPalette";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";

const PLAIN_ROUTES = ["/login"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "";
  const isPlain = PLAIN_ROUTES.some((r) => pathname.startsWith(r));

  return (
    <ThemeProvider>
      <TooltipProvider delayDuration={250}>
        {isPlain ? (
          <main className="flex min-h-screen items-center justify-center bg-background">
            {children}
          </main>
        ) : (
          <div className="flex h-screen overflow-hidden bg-background text-foreground">
            <Sidebar />
            <div className="flex flex-1 flex-col overflow-hidden">
              <Topbar />
              <main className="flex-1 overflow-auto bg-surface p-4 md:p-6">
                {children}
              </main>
            </div>
            <CommandPalette />
          </div>
        )}
        <Toaster />
      </TooltipProvider>
    </ThemeProvider>
  );
}
