import * as React from "react";
import { cn } from "@/lib/cn";

export function Avatar({
  className,
  initials,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { initials: string }) {
  return (
    <div
      className={cn(
        "inline-flex h-8 w-8 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary",
        className
      )}
      {...props}
    >
      {initials.slice(0, 2).toUpperCase()}
    </div>
  );
}
