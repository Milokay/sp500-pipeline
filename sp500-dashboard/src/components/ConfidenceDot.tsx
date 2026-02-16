"use client";

interface ConfidenceDotProps {
  confidence: string | null | undefined;
  showLabel?: boolean;
}

function getConfidenceConfig(confidence: string | null | undefined) {
  if (!confidence) return { color: "bg-slate-600", label: "\u2014" };
  const lower = confidence.toLowerCase();
  if (lower === "high") return { color: "bg-emerald-400", label: "High" };
  if (lower === "medium") return { color: "bg-amber-400", label: "Medium" };
  if (lower === "low") return { color: "bg-red-400", label: "Low" };
  return { color: "bg-slate-600", label: confidence };
}

export default function ConfidenceDot({ confidence, showLabel = true }: ConfidenceDotProps) {
  const { color, label } = getConfidenceConfig(confidence);

  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`inline-block h-2.5 w-2.5 rounded-full ${color}`} />
      {showLabel && <span className="text-xs text-slate-300">{label}</span>}
    </span>
  );
}
