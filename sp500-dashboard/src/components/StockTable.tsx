"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import type { StockData, DataQuality } from "@/types/stock";
import { formatValue } from "@/lib/format";
import SignalBadge from "./SignalBadge";
import ConvictionStars from "./ConvictionStars";
import UpsideBar from "./UpsideBar";
import ConfidenceDot from "./ConfidenceDot";

type SortDir = "asc" | "desc";
type SortKey = keyof StockData | "marginOfSafety" | "confidence";

interface StockTableProps {
  stocks: StockData[];
  qualityMap: Record<string, DataQuality>;
  selectedTickers: Set<string>;
  onToggleSelect: (ticker: string) => void;
}

const columns: { key: SortKey; label: string; align?: "right" | "left" | "center" }[] = [
  { key: "ticker", label: "Ticker" },
  { key: "company", label: "Company" },
  { key: "sector", label: "Sector" },
  { key: "price", label: "Price ($)", align: "right" },
  { key: "intrinsicValue", label: "IV ($)", align: "right" },
  { key: "upsidePercent", label: "Upside %", align: "right" },
  { key: "buyPrice", label: "Buy Price ($)", align: "right" },
  { key: "marginOfSafety", label: "Margin of Safety", align: "right" },
  { key: "signal", label: "Signal", align: "center" },
  { key: "conviction", label: "Conviction", align: "center" },
  { key: "rsi", label: "RSI", align: "right" },
  { key: "sharpe52W", label: "Sharpe 52W", align: "right" },
  { key: "roe", label: "ROE (%)", align: "right" },
  { key: "de", label: "D/E", align: "right" },
  { key: "confidence", label: "Confidence", align: "center" },
];

function getMarginOfSafety(stock: StockData): number | null {
  if (stock.buyPrice === null || stock.price === null || stock.price === 0) return null;
  return (stock.buyPrice - stock.price) / stock.price;
}

function getSortValue(stock: StockData, key: SortKey, qualityMap: Record<string, DataQuality>): string | number | null {
  if (key === "marginOfSafety") return getMarginOfSafety(stock);
  if (key === "confidence") {
    const q = qualityMap[stock.ticker];
    if (!q) return null;
    return q.confidence === "High" ? 3 : q.confidence === "Medium" ? 2 : 1;
  }
  const val = stock[key as keyof StockData];
  if (val === null || val === undefined) return null;
  return val as string | number;
}

export default function StockTable({ stocks, qualityMap, selectedTickers, onToggleSelect }: StockTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("upsidePercent");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  const sorted = useMemo(() => {
    return [...stocks].sort((a, b) => {
      const av = getSortValue(a, sortKey, qualityMap);
      const bv = getSortValue(b, sortKey, qualityMap);
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
      const cmp = typeof av === "string" && typeof bv === "string"
        ? av.localeCompare(bv)
        : (av as number) - (bv as number);
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [stocks, sortKey, sortDir, qualityMap]);

  if (stocks.length === 0) {
    return (
      <div className="flex items-center justify-center rounded-lg border border-slate-700 bg-slate-900 p-12 text-slate-500">
        No stocks match your filters.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-700">
      <table className="w-full text-sm">
        <thead className="sticky-header">
          <tr className="border-b border-slate-700 bg-slate-900">
            <th className="px-2 py-2 text-left">
              <span className="sr-only">Select</span>
            </th>
            {columns.map((col) => (
              <th
                key={col.key}
                onClick={() => handleSort(col.key)}
                className={`cursor-pointer whitespace-nowrap px-3 py-2 text-xs font-medium uppercase tracking-wider text-slate-400 hover:text-emerald-400 transition-colors ${
                  col.align === "right" ? "text-right" : col.align === "center" ? "text-center" : "text-left"
                }`}
              >
                <span className="inline-flex items-center gap-1">
                  {col.label}
                  {sortKey === col.key && (
                    <span className="text-emerald-400">{sortDir === "asc" ? "\u25B2" : "\u25BC"}</span>
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((stock) => {
            const quality = qualityMap[stock.ticker];
            const mos = getMarginOfSafety(stock);
            const selected = selectedTickers.has(stock.ticker);

            return (
              <tr
                key={stock.ticker}
                className={`border-b border-slate-800 transition-colors hover:bg-slate-800/50 ${
                  selected ? "bg-emerald-950/20" : ""
                }`}
              >
                <td className="px-2 py-2">
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => onToggleSelect(stock.ticker)}
                    className="rounded border-slate-600 bg-slate-800 text-emerald-400 focus:ring-emerald-400/30"
                  />
                </td>
                <td className="px-3 py-2">
                  <Link
                    href={`/stock/${stock.ticker}`}
                    className="font-semibold text-sky-400 hover:text-sky-300 hover:underline"
                  >
                    {stock.ticker}
                  </Link>
                </td>
                <td className="px-3 py-2 text-slate-300 max-w-[200px] truncate">{stock.company}</td>
                <td className="px-3 py-2 text-slate-400 text-xs">{stock.sector}</td>
                <td className="px-3 py-2 text-right font-mono text-slate-200">
                  {formatValue(stock.price, "currency")}
                </td>
                <td className="px-3 py-2 text-right font-mono text-slate-200">
                  {formatValue(stock.intrinsicValue, "currency")}
                </td>
                <td className="px-3 py-2">
                  <UpsideBar value={stock.upsidePercent} />
                </td>
                <td className="px-3 py-2 text-right font-mono text-slate-200">
                  {formatValue(stock.buyPrice, "currency")}
                </td>
                <td className="px-3 py-2 text-right font-mono">
                  {mos !== null ? (
                    <span className={mos >= 0 ? "text-emerald-400" : "text-red-400"}>
                      {formatValue(mos, "percentage", 1)}
                    </span>
                  ) : (
                    <span className="text-slate-600">{"\u2014"}</span>
                  )}
                </td>
                <td className="px-3 py-2 text-center">
                  <SignalBadge signal={stock.signal} size="sm" />
                </td>
                <td className="px-3 py-2 text-center">
                  <ConvictionStars level={stock.conviction} size="sm" />
                </td>
                <td className="px-3 py-2 text-right font-mono text-slate-300">
                  {stock.rsi !== null ? stock.rsi.toFixed(1) : "\u2014"}
                </td>
                <td className="px-3 py-2 text-right font-mono text-slate-300">
                  {stock.sharpe52W !== null ? stock.sharpe52W.toFixed(2) : "\u2014"}
                </td>
                <td className="px-3 py-2 text-right font-mono text-slate-300">
                  {stock.roe !== null ? (stock.roe * 100).toFixed(1) + "%" : "\u2014"}
                </td>
                <td className="px-3 py-2 text-right font-mono text-slate-300">
                  {stock.de !== null ? stock.de.toFixed(2) : "\u2014"}
                </td>
                <td className="px-3 py-2 text-center">
                  <ConfidenceDot confidence={quality?.confidence} showLabel={false} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
