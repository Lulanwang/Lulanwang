export function DisclaimerBadge({
  modelName,
  modelVersion,
  confidence,
}: {
  modelName: string;
  modelVersion: string;
  confidence: number;
}) {
  return (
    <span className="inline-flex items-center gap-1 rounded border border-warn-500 bg-warn-50 px-2 py-0.5 text-[10px] font-medium text-warn-700">
      AI · {modelName} v{modelVersion} · conf {confidence.toFixed(2)} · UNVERIFIED
    </span>
  );
}
