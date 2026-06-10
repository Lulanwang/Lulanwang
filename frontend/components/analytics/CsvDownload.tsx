"use client";

import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";

export function CsvDownload<T extends Record<string, unknown>>({
  data,
  filename,
}: {
  data: T[];
  filename: string;
}) {
  function download() {
    if (data.length === 0) return;
    const keys = Object.keys(data[0]);
    const lines = [
      keys.join(","),
      ...data.map((row) =>
        keys
          .map((k) => {
            const v = row[k];
            const s = v === null || v === undefined ? "" : String(v);
            return s.includes(",") || s.includes('"')
              ? `"${s.replace(/"/g, '""')}"`
              : s;
          })
          .join(",")
      ),
    ];
    const blob = new Blob([lines.join("\n")], {
      type: "text/csv;charset=utf-8;",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Button
      size="sm"
      variant="ghost"
      onClick={download}
      disabled={data.length === 0}
      title="Download as CSV"
    >
      <Download />
      CSV
    </Button>
  );
}
