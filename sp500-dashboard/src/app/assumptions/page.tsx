"use client";

import { useMemo } from "react";
import { getAssumptions, getDataQualities } from "@/lib/data";
import type { Assumption } from "@/types/stock";

function categorize(parameter: string): string {
  const lower = parameter.toLowerCase();
  if (lower.includes("wacc") || lower.includes("discount") || lower.includes("cost of")) return "WACC & Discount Rate";
  if (lower.includes("growth") || lower.includes("terminal") || lower.includes("perpetuity")) return "Growth";
  if (lower.includes("risk") || lower.includes("beta") || lower.includes("premium")) return "Risk";
  if (lower.includes("multiple") || lower.includes("exit") || lower.includes("ev/")) return "Exit Multiple";
  if (lower.includes("margin") || lower.includes("revenue") || lower.includes("ebitda")) return "Financials";
  if (lower.includes("rate") || lower.includes("rfr") || lower.includes("treasury")) return "Interest Rates";
  return "Other";
}

const highlightParams = ["wacc", "risk-free", "risk free", "exit multiple", "growth cap", "terminal growth", "rfr"];

function isHighlighted(parameter: string): boolean {
  const lower = parameter.toLowerCase();
  return highlightParams.some((h) => lower.includes(h));
}

export default function AssumptionsPage() {
  const assumptions = useMemo(() => getAssumptions(), []);
  const qualities = useMemo(() => getDataQualities(), []);

  const lastUpdated = useMemo(() => {
    const dates = qualities.map((q) => q.lastUpdated).filter(Boolean);
    return dates.length > 0 ? dates[0] : null;
  }, [qualities]);

  const grouped = useMemo(() => {
    const groups: Record<string, Assumption[]> = {};
    for (const a of assumptions) {
      const cat = categorize(a.parameter);
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(a);
    }
    // Sort groups with known categories first
    const order = ["WACC & Discount Rate", "Interest Rates", "Growth", "Risk", "Exit Multiple", "Financials", "Other"];
    const sorted: [string, Assumption[]][] = [];
    for (const cat of order) {
      if (groups[cat]) sorted.push([cat, groups[cat]]);
    }
    return sorted;
  }, [assumptions]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-slate-100">Assumptions & Methodology</h1>
        {lastUpdated && (
          <span className="text-xs text-slate-500">Data as of: {lastUpdated}</span>
        )}
      </div>

      <div className="rounded-lg border border-slate-700 bg-slate-900 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="sticky-header">
            <tr className="border-b border-slate-700 bg-slate-900">
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-400">Parameter</th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-400">Value</th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-400">Description</th>
            </tr>
          </thead>
          {grouped.map(([category, items]) => (
            <tbody key={`group-${category}`}>
              <tr>
                <td
                  colSpan={3}
                  className="bg-slate-800/50 px-4 py-2 text-xs font-semibold uppercase tracking-wider text-slate-400"
                >
                  {category}
                </td>
              </tr>
              {items.map((a, i) => {
                const highlighted = isHighlighted(a.parameter);
                return (
                  <tr
                    key={`${category}-${i}`}
                    className={`border-b border-slate-800 transition-colors hover:bg-slate-800/50 ${
                      highlighted ? "border-l-2 border-l-emerald-400" : ""
                    }`}
                  >
                    <td className={`px-4 py-2.5 font-medium ${highlighted ? "text-emerald-300" : "text-slate-200"}`}>
                      {a.parameter}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-slate-300">{a.value || "\u2014"}</td>
                    <td className="px-4 py-2.5 text-slate-500 max-w-md">{a.description || "\u2014"}</td>
                  </tr>
                );
              })}
            </tbody>
          ))}
        </table>
      </div>

      <div className="text-xs text-slate-600">
        {assumptions.length} parameters loaded. Key inputs are highlighted with a green border.
      </div>
    </div>
  );
}
