"use client";

interface PriceBarProps {
  buyPrice: number | null | undefined;
  currentPrice: number | null | undefined;
  ivLow: number | null | undefined;
  ivHigh: number | null | undefined;
}

export default function PriceBar({ buyPrice, currentPrice, ivLow, ivHigh }: PriceBarProps) {
  const values = [buyPrice, currentPrice, ivLow, ivHigh].filter(
    (v): v is number => v !== null && v !== undefined && !isNaN(v)
  );

  if (values.length < 2) {
    return <span className="text-slate-600">{"\u2014"}</span>;
  }

  const min = Math.min(...values) * 0.9;
  const max = Math.max(...values) * 1.1;
  const range = max - min;

  function posPercent(val: number | null | undefined): number | null {
    if (val === null || val === undefined || isNaN(val)) return null;
    return ((val - min) / range) * 100;
  }

  const buyPos = posPercent(buyPrice);
  const curPos = posPercent(currentPrice);
  const ivLowPos = posPercent(ivLow);
  const ivHighPos = posPercent(ivHigh);

  return (
    <div className="w-full">
      <div className="relative h-8 w-full rounded bg-slate-800">
        {/* IV range bar */}
        {ivLowPos !== null && ivHighPos !== null && (
          <div
            className="absolute top-2 bottom-2 rounded bg-emerald-900/40"
            style={{ left: `${ivLowPos}%`, width: `${ivHighPos - ivLowPos}%` }}
          />
        )}
        {/* Buy price marker */}
        {buyPos !== null && (
          <div className="absolute top-0 bottom-0 flex flex-col items-center" style={{ left: `${buyPos}%` }}>
            <div className="h-full w-0.5 bg-amber-400" />
          </div>
        )}
        {/* Current price marker */}
        {curPos !== null && (
          <div className="absolute top-0 bottom-0 flex flex-col items-center" style={{ left: `${curPos}%` }}>
            <div className="h-full w-1 bg-sky-400 rounded" />
          </div>
        )}
        {/* IV Low marker */}
        {ivLowPos !== null && (
          <div className="absolute top-0 bottom-0" style={{ left: `${ivLowPos}%` }}>
            <div className="h-full w-0.5 bg-emerald-400/60" />
          </div>
        )}
        {/* IV High marker */}
        {ivHighPos !== null && (
          <div className="absolute top-0 bottom-0" style={{ left: `${ivHighPos}%` }}>
            <div className="h-full w-0.5 bg-emerald-400/60" />
          </div>
        )}
      </div>
      {/* Labels */}
      <div className="mt-1 flex justify-between text-[10px] text-slate-500">
        <div className="flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-sm bg-amber-400" /> Buy
        </div>
        <div className="flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-sm bg-sky-400" /> Current
        </div>
        <div className="flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-sm bg-emerald-400/60" /> IV Range
        </div>
      </div>
    </div>
  );
}
