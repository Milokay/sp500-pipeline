"use client";

import { useState } from "react";

export interface FilterState {
  sectors: string[];
  signals: string[];
  minConviction: number;
  upsideMin: string;
  upsideMax: string;
  rsiMin: string;
  rsiMax: string;
  maxDE: string;
  minSharpe: string;
  confidence: string[];
}

export const defaultFilters: FilterState = {
  sectors: [],
  signals: [],
  minConviction: 1,
  upsideMin: "",
  upsideMax: "",
  rsiMin: "",
  rsiMax: "",
  maxDE: "",
  minSharpe: "",
  confidence: [],
};

interface FilterSidebarProps {
  filters: FilterState;
  onChange: (filters: FilterState) => void;
  allSectors: string[];
  collapsed?: boolean;
  onToggle?: () => void;
}

export default function FilterSidebar({
  filters,
  onChange,
  allSectors,
  collapsed = false,
  onToggle,
}: FilterSidebarProps) {
  const [localFilters, setLocalFilters] = useState(filters);

  function update(partial: Partial<FilterState>) {
    const next = { ...localFilters, ...partial };
    setLocalFilters(next);
    onChange(next);
  }

  function toggleArrayItem(arr: string[], item: string): string[] {
    return arr.includes(item) ? arr.filter((x) => x !== item) : [...arr, item];
  }

  function handleReset() {
    setLocalFilters(defaultFilters);
    onChange(defaultFilters);
  }

  if (collapsed) {
    return (
      <button
        onClick={onToggle}
        className="flex items-center gap-1 rounded-md border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200"
      >
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 010 2H4a1 1 0 01-1-1zm4 8a1 1 0 011-1h8a1 1 0 010 2H8a1 1 0 01-1-1zm2 8a1 1 0 011-1h4a1 1 0 010 2h-4a1 1 0 01-1-1z" />
        </svg>
        Filters
      </button>
    );
  }

  return (
    <div className="w-64 shrink-0 rounded-lg border border-slate-700 bg-slate-900 p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200">Filters</h3>
        <div className="flex gap-2">
          <button onClick={handleReset} className="text-xs text-slate-500 hover:text-emerald-400">
            Reset
          </button>
          {onToggle && (
            <button onClick={onToggle} className="text-xs text-slate-500 hover:text-slate-300">
              Hide
            </button>
          )}
        </div>
      </div>

      {/* Sector */}
      <div className="mb-4">
        <div className="text-xs font-medium text-slate-400 mb-2">Sector</div>
        <div className="max-h-40 overflow-y-auto space-y-1">
          {allSectors.map((s) => (
            <label key={s} className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer hover:text-slate-100">
              <input
                type="checkbox"
                checked={localFilters.sectors.includes(s)}
                onChange={() => update({ sectors: toggleArrayItem(localFilters.sectors, s) })}
                className="rounded border-slate-600 bg-slate-800 text-emerald-400 focus:ring-emerald-400/30"
              />
              {s}
            </label>
          ))}
        </div>
      </div>

      {/* Signal */}
      <div className="mb-4">
        <div className="text-xs font-medium text-slate-400 mb-2">Signal</div>
        <div className="flex flex-wrap gap-1">
          {["BUY", "SELL", "HOLD"].map((sig) => {
            const active = localFilters.signals.includes(sig);
            const color =
              sig === "BUY" ? "bg-emerald-900/50 text-emerald-400 border-emerald-700" :
              sig === "SELL" ? "bg-red-900/50 text-red-400 border-red-700" :
              "bg-amber-900/50 text-amber-400 border-amber-700";
            return (
              <button
                key={sig}
                onClick={() => update({ signals: toggleArrayItem(localFilters.signals, sig) })}
                className={`rounded-full border px-2 py-0.5 text-xs font-medium transition-colors ${
                  active ? color : "border-slate-600 text-slate-500 hover:border-slate-500"
                }`}
              >
                {sig}
              </button>
            );
          })}
        </div>
      </div>

      {/* Conviction */}
      <div className="mb-4">
        <div className="text-xs font-medium text-slate-400 mb-2">
          Min Conviction: <span className="text-amber-400">{localFilters.minConviction}</span>
        </div>
        <input
          type="range"
          min={1}
          max={5}
          value={localFilters.minConviction}
          onChange={(e) => update({ minConviction: Number(e.target.value) })}
          className="w-full accent-amber-400"
        />
        <div className="flex justify-between text-[10px] text-slate-600">
          <span>1</span><span>2</span><span>3</span><span>4</span><span>5</span>
        </div>
      </div>

      {/* Upside % range */}
      <div className="mb-4">
        <div className="text-xs font-medium text-slate-400 mb-2">Upside % Range</div>
        <div className="flex gap-2">
          <input
            type="number"
            placeholder="Min"
            value={localFilters.upsideMin}
            onChange={(e) => update({ upsideMin: e.target.value })}
            className="w-full rounded border border-slate-700 bg-slate-800 px-2 py-1 text-xs text-slate-200 placeholder-slate-600 focus:border-emerald-400 focus:outline-none"
          />
          <input
            type="number"
            placeholder="Max"
            value={localFilters.upsideMax}
            onChange={(e) => update({ upsideMax: e.target.value })}
            className="w-full rounded border border-slate-700 bg-slate-800 px-2 py-1 text-xs text-slate-200 placeholder-slate-600 focus:border-emerald-400 focus:outline-none"
          />
        </div>
      </div>

      {/* RSI range */}
      <div className="mb-4">
        <div className="text-xs font-medium text-slate-400 mb-2">RSI Range</div>
        <div className="flex gap-2">
          <input
            type="number"
            placeholder="Min"
            value={localFilters.rsiMin}
            onChange={(e) => update({ rsiMin: e.target.value })}
            className="w-full rounded border border-slate-700 bg-slate-800 px-2 py-1 text-xs text-slate-200 placeholder-slate-600 focus:border-emerald-400 focus:outline-none"
          />
          <input
            type="number"
            placeholder="Max"
            value={localFilters.rsiMax}
            onChange={(e) => update({ rsiMax: e.target.value })}
            className="w-full rounded border border-slate-700 bg-slate-800 px-2 py-1 text-xs text-slate-200 placeholder-slate-600 focus:border-emerald-400 focus:outline-none"
          />
        </div>
      </div>

      {/* Max D/E */}
      <div className="mb-4">
        <div className="text-xs font-medium text-slate-400 mb-2">Max D/E Ratio</div>
        <input
          type="number"
          placeholder="e.g. 2.0"
          value={localFilters.maxDE}
          onChange={(e) => update({ maxDE: e.target.value })}
          className="w-full rounded border border-slate-700 bg-slate-800 px-2 py-1 text-xs text-slate-200 placeholder-slate-600 focus:border-emerald-400 focus:outline-none"
        />
      </div>

      {/* Min Sharpe */}
      <div className="mb-4">
        <div className="text-xs font-medium text-slate-400 mb-2">Min Sharpe Ratio</div>
        <input
          type="number"
          step="0.1"
          placeholder="e.g. 0.5"
          value={localFilters.minSharpe}
          onChange={(e) => update({ minSharpe: e.target.value })}
          className="w-full rounded border border-slate-700 bg-slate-800 px-2 py-1 text-xs text-slate-200 placeholder-slate-600 focus:border-emerald-400 focus:outline-none"
        />
      </div>

      {/* Data Confidence */}
      <div className="mb-2">
        <div className="text-xs font-medium text-slate-400 mb-2">Data Confidence</div>
        <div className="space-y-1">
          {["High", "Medium", "Low"].map((c) => {
            const dotColor = c === "High" ? "bg-emerald-400" : c === "Medium" ? "bg-amber-400" : "bg-red-400";
            return (
              <label key={c} className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer hover:text-slate-100">
                <input
                  type="checkbox"
                  checked={localFilters.confidence.includes(c)}
                  onChange={() => update({ confidence: toggleArrayItem(localFilters.confidence, c) })}
                  className="rounded border-slate-600 bg-slate-800 text-emerald-400 focus:ring-emerald-400/30"
                />
                <span className={`inline-block h-2 w-2 rounded-full ${dotColor}`} />
                {c}
              </label>
            );
          })}
        </div>
      </div>
    </div>
  );
}
