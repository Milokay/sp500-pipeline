"use client";

interface UpsideBarProps {
  value: number | null | undefined;
  maxAbsValue?: number;
}

export default function UpsideBar({ value, maxAbsValue = 2 }: UpsideBarProps) {
  if (value === null || value === undefined || isNaN(value)) {
    return <span className="text-slate-600">{"\u2014"}</span>;
  }

  const pct = value * 100;
  const clampedAbs = Math.min(Math.abs(value), maxAbsValue);
  const widthPercent = (clampedAbs / maxAbsValue) * 50;
  const isPositive = value >= 0;

  return (
    <div className="flex items-center gap-2">
      <div className="relative h-4 w-24 rounded bg-slate-800">
        <div className="absolute top-0 bottom-0 left-1/2 w-px bg-slate-600" />
        {isPositive ? (
          <div
            className="absolute top-0.5 bottom-0.5 left-1/2 rounded-r bg-gradient-to-r from-emerald-600 to-emerald-400"
            style={{ width: `${widthPercent}%` }}
          />
        ) : (
          <div
            className="absolute top-0.5 bottom-0.5 rounded-l bg-gradient-to-l from-red-600 to-red-400"
            style={{ width: `${widthPercent}%`, right: "50%" }}
          />
        )}
      </div>
      <span className={`font-mono text-xs ${isPositive ? "text-emerald-400" : "text-red-400"}`}>
        {pct > 0 ? "+" : ""}{pct.toFixed(1)}%
      </span>
    </div>
  );
}
