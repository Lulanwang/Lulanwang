"use client";

import { useState } from "react";
import { ImageOff } from "lucide-react";

export function StudyThumbnail({
  studyId,
  size = 40,
}: {
  studyId: string;
  size?: number;
}) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <div
        className="flex items-center justify-center rounded border bg-muted text-muted-foreground"
        style={{ width: size, height: size }}
        aria-label="Thumbnail unavailable"
      >
        <ImageOff className="h-3.5 w-3.5" />
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={`/api/v1/studies/${studyId}/thumbnail`}
      alt=""
      onError={() => setFailed(true)}
      loading="lazy"
      className="rounded border border-border bg-black object-cover"
      style={{ width: size, height: size }}
    />
  );
}
