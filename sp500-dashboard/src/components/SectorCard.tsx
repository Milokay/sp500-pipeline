"use client";

import type { SectorSummary } from "@/types/stock";

interface SectorCardProps {
  sector: SectorSummary;
}

export default function SectorCard({ sector }: SectorCardProps) {
  const avgUpside = sector.avgUpsidePercent * 100;
  const borderColor = avgUpside >= 0 ? "border-l-emerald-400" : "border-l-red-400";
  const upsideColor = avgUpside >= 0 ? "text-emerald-400" : "text-red-400";

  return (
    <div
      className={`rounded-lg border border-slate-700 border-l-4 ${borderColor} bg-slate-900 p-3 transition-colors hover:bg-slate-800/70`}
    >
      <div className="text-sm font-semibold text-slate-200 truncate">{sector.sector}</div>
      <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
        <div className="text-slate-500">Undervalued</div>
        <div className="text-right font-mono text-slate-300">
          {sector.undervaluedCount} / {sector.stockCount}
        </div>
        <div className="text-slate-500">Avg Upside</div>
        <div className={`text-right font-mono ${upsideColor}`}>
          {avgUpside > 0 ? "+" : ""}{avgUpside.toFixed(1)}%
        </div>
        <div className="text-slate-500">Avg RSI</div>
        <div className="text-right font-mono text-slate-300">
          {sector.avgRSI.toFixed(1)}
        </div>
      </div>
    </div>
  );
}
