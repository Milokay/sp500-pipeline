"use client";

interface MetricCardProps {
  label: string;
  value: string;
  comparison?: string;
  color?: "emerald" | "red" | "amber" | "sky" | "slate";
  size?: "sm" | "md" | "lg";
}

const colorMap = {
  emerald: "text-emerald-400",
  red: "text-red-400",
  amber: "text-amber-400",
  sky: "text-sky-400",
  slate: "text-slate-300",
};

export default function MetricCard({ label, value, comparison, color = "slate", size = "md" }: MetricCardProps) {
  const valueSize = size === "lg" ? "text-2xl" : size === "md" ? "text-lg" : "text-sm";

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900 p-3">
      <div className="text-xs text-slate-500 uppercase tracking-wide">{label}</div>
      <div className={`font-mono font-bold ${valueSize} ${colorMap[color]} mt-1`}>
        {value}
      </div>
      {comparison && (
        <div className="text-xs text-slate-500 mt-1">{comparison}</div>
      )}
    </div>
  );
}
