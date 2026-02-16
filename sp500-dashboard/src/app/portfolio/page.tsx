"use client";

import { useMemo, useCallback } from "react";
import {
  PieChart,
  Pie,
  Cell,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  BarChart,
  Bar,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { usePortfolio } from "@/context/PortfolioContext";
import { formatValue } from "@/lib/format";
import ConvictionStars from "@/components/ConvictionStars";
import MetricCard from "@/components/MetricCard";

const SECTOR_COLORS = [
  "#34d399", "#f87171", "#fbbf24", "#60a5fa", "#a78bfa",
  "#f472b6", "#2dd4bf", "#fb923c", "#818cf8", "#e879f9",
  "#4ade80", "#38bdf8",
];

export default function PortfolioBuilder() {
  const {
    portfolio,
    stats,
    removeStock,
    updateAllocation,
    equalWeight,
    weightByConviction,
    weightByUpside,
  } = usePortfolio();

  const handleExportCSV = useCallback(() => {
    if (portfolio.length === 0) return;
    const headers = [
      "Ticker", "Company", "Sector", "Price", "Intrinsic Value", "Upside %",
      "Buy Price", "Allocation %", "Signal", "Conviction", "Rationale", "Confidence",
    ];
    const rows = portfolio.map((ps) => [
      ps.stock.ticker,
      ps.stock.company,
      ps.stock.sector,
      ps.stock.price ?? "",
      ps.stock.intrinsicValue ?? "",
      ps.stock.upsidePercent !== null ? (ps.stock.upsidePercent * 100).toFixed(1) : "",
      ps.stock.buyPrice ?? "",
      ps.allocationPercent,
      ps.stock.signal ?? "",
      ps.stock.conviction ?? "",
      ps.stock.rationale ?? "",
      ps.quality?.confidence ?? "",
    ]);
    const csv = [headers, ...rows].map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "portfolio-export.csv";
    a.click();
    URL.revokeObjectURL(url);
  }, [portfolio]);

  // Sector allocation data for pie chart
  const sectorAllocationData = useMemo(() => {
    const map: Record<string, number> = {};
    for (const ps of portfolio) {
      map[ps.stock.sector] = (map[ps.stock.sector] || 0) + ps.allocationPercent;
    }
    return Object.entries(map)
      .map(([name, value]) => ({ name, value: Math.round(value * 100) / 100 }))
      .sort((a, b) => b.value - a.value);
  }, [portfolio]);

  // Risk scatter data
  const riskScatterData = useMemo(() => {
    return portfolio
      .filter((ps) => ps.stock.stdDev52W !== null && ps.stock.upsidePercent !== null)
      .map((ps) => ({
        x: (ps.stock.stdDev52W ?? 0) * 100,
        y: (ps.stock.upsidePercent ?? 0) * 100,
        z: Math.max(ps.allocationPercent * 3, 20),
        name: ps.stock.ticker,
        sector: ps.stock.sector,
      }));
  }, [portfolio]);

  // Conviction distribution data
  const convictionDistData = useMemo(() => {
    const counts = [0, 0, 0, 0, 0];
    for (const ps of portfolio) {
      const c = ps.stock.conviction;
      if (c !== null && c >= 1 && c <= 5) counts[c - 1]++;
    }
    return counts.map((count, i) => ({ level: `${i + 1}`, count }));
  }, [portfolio]);

  // Data quality distribution
  const qualityDistData = useMemo(() => {
    const counts = { High: 0, Medium: 0, Low: 0 };
    for (const ps of portfolio) {
      const conf = ps.quality?.confidence;
      if (conf && conf in counts) counts[conf as keyof typeof counts]++;
    }
    return Object.entries(counts).map(([name, value]) => ({ name, value }));
  }, [portfolio]);

  // Upside histogram
  const upsideHistData = useMemo(() => {
    const bins: Record<string, number> = {};
    const binSize = 20;
    for (const ps of portfolio) {
      const up = ps.stock.upsidePercent;
      if (up === null) continue;
      const pct = up * 100;
      const binStart = Math.floor(pct / binSize) * binSize;
      const label = `${binStart}% to ${binStart + binSize}%`;
      bins[label] = (bins[label] || 0) + 1;
    }
    return Object.entries(bins)
      .map(([range, count]) => ({ range, count }))
      .sort((a, b) => {
        const aVal = parseInt(a.range);
        const bVal = parseInt(b.range);
        return aVal - bVal;
      });
  }, [portfolio]);

  // Entry strategy data
  const entryStrategyData = useMemo(() => {
    return portfolio.map((ps) => {
      const price = ps.stock.price;
      const buyPrice = ps.stock.buyPrice;
      let gapPct: number | null = null;
      let action = "WAIT";
      let actionColor = "slate";

      if (price !== null && buyPrice !== null && buyPrice !== 0) {
        gapPct = ((price - buyPrice) / buyPrice) * 100;
        if (price <= buyPrice) {
          action = "BUY NOW";
          actionColor = "emerald";
        } else if (gapPct < 10) {
          action = "NEAR ENTRY";
          actionColor = "amber";
        } else {
          action = "WAIT";
          actionColor = "slate";
        }
      }

      return {
        ticker: ps.stock.ticker,
        price,
        buyPrice,
        gapPct,
        action,
        actionColor,
      };
    });
  }, [portfolio]);

  // Warnings
  const allocationWarning = stats.totalAllocation > 0 && Math.abs(stats.totalAllocation - 100) > 0.1;
  const sectorConcentrationWarning = sectorAllocationData.some((s) => s.value > 30);
  const lowConvictionWarning = stats.avgConviction > 0 && stats.avgConviction < 3;
  const lowQualityAllocation = useMemo(() => {
    return portfolio
      .filter((ps) => ps.quality?.confidence === "Low")
      .reduce((sum, ps) => sum + ps.allocationPercent, 0);
  }, [portfolio]);

  if (portfolio.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <svg className="h-16 w-16 text-slate-700 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
        <h2 className="text-xl font-semibold text-slate-300 mb-2">No stocks in your portfolio</h2>
        <p className="text-slate-500 max-w-md">
          Add stocks from the Scanner to build your portfolio. Use the checkboxes in the stock table or the &quot;Add to Portfolio&quot; button on any stock&apos;s detail page.
        </p>
      </div>
    );
  }

  return (
    <div className="flex gap-6">
      {/* Left Panel - Portfolio List */}
      <div className="w-1/3 shrink-0">
        <div className="sticky top-20 rounded-lg border border-slate-700 bg-slate-900 p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold text-slate-200">
              My Portfolio <span className="text-sm text-slate-500">({portfolio.length})</span>
            </h2>
            <button
              onClick={handleExportCSV}
              className="rounded bg-slate-700 px-2 py-1 text-xs text-slate-300 hover:bg-slate-600"
            >
              Export CSV
            </button>
          </div>

          {/* Quick weight buttons */}
          <div className="flex gap-2 mb-4">
            <button
              onClick={equalWeight}
              className="flex-1 rounded bg-slate-800 px-2 py-1.5 text-xs text-slate-400 hover:bg-slate-700 hover:text-slate-200"
            >
              Equal Weight
            </button>
            <button
              onClick={weightByConviction}
              className="flex-1 rounded bg-slate-800 px-2 py-1.5 text-xs text-slate-400 hover:bg-slate-700 hover:text-slate-200"
            >
              By Conviction
            </button>
            <button
              onClick={weightByUpside}
              className="flex-1 rounded bg-slate-800 px-2 py-1.5 text-xs text-slate-400 hover:bg-slate-700 hover:text-slate-200"
            >
              By Upside
            </button>
          </div>

          {/* Stock list */}
          <div className="space-y-2 max-h-[calc(100vh-280px)] overflow-y-auto">
            {portfolio.map((ps) => (
              <div
                key={ps.stock.ticker}
                className="flex items-center gap-2 rounded-md border border-slate-800 bg-slate-800/50 p-2 hover:bg-slate-800"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm text-sky-400">{ps.stock.ticker}</span>
                    <ConvictionStars level={ps.stock.conviction} size="sm" />
                  </div>
                  <div className="text-xs text-slate-500 truncate">{ps.stock.company}</div>
                  {ps.stock.upsidePercent !== null && (
                    <div className={`text-xs font-mono ${ps.stock.upsidePercent >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {ps.stock.upsidePercent > 0 ? "+" : ""}{(ps.stock.upsidePercent * 100).toFixed(1)}%
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  <input
                    type="number"
                    min={0}
                    max={100}
                    step={0.1}
                    value={ps.allocationPercent}
                    onChange={(e) => updateAllocation(ps.stock.ticker, parseFloat(e.target.value) || 0)}
                    className="w-16 rounded border border-slate-700 bg-slate-900 px-1.5 py-1 text-right text-xs font-mono text-slate-200 focus:border-emerald-400 focus:outline-none"
                  />
                  <span className="text-xs text-slate-500">%</span>
                </div>
                <button
                  onClick={() => removeStock(ps.stock.ticker)}
                  className="text-slate-600 hover:text-red-400 transition-colors"
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
          </div>

          {/* Total allocation */}
          <div className={`mt-3 flex justify-between border-t border-slate-700 pt-2 text-sm ${allocationWarning ? "text-amber-400" : "text-slate-300"}`}>
            <span>Total Allocation</span>
            <span className="font-mono font-bold">{stats.totalAllocation.toFixed(1)}%</span>
          </div>
          {allocationWarning && (
            <div className="mt-1 text-[10px] text-amber-400">
              Allocation does not sum to 100%.
            </div>
          )}
        </div>
      </div>

      {/* Right Panel - Analytics */}
      <div className="flex-1 min-w-0 space-y-6">
        {/* Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <MetricCard label="Positions" value={String(portfolio.length)} color="sky" />
          <MetricCard
            label="Wtd Avg Upside"
            value={`${stats.weightedUpside > 0 ? "+" : ""}${(stats.weightedUpside * 100).toFixed(1)}%`}
            color={stats.weightedUpside >= 0 ? "emerald" : "red"}
          />
          <MetricCard
            label="Wtd Avg Sharpe"
            value={stats.weightedSharpe.toFixed(2)}
            color={stats.weightedSharpe > 1 ? "emerald" : stats.weightedSharpe < 0 ? "red" : "slate"}
          />
          <MetricCard
            label="Avg Conviction"
            value={stats.avgConviction.toFixed(1)}
            color={stats.avgConviction >= 4 ? "emerald" : stats.avgConviction < 3 ? "amber" : "slate"}
          />
          <MetricCard
            label="Total Alloc"
            value={`${stats.totalAllocation.toFixed(1)}%`}
            color={Math.abs(stats.totalAllocation - 100) < 0.1 ? "emerald" : "amber"}
          />
        </div>

        {/* Charts Row 1: Sector Allocation + Risk Profile */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Sector Allocation Pie */}
          <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
            <h3 className="text-sm font-semibold text-slate-300 mb-3">Sector Allocation</h3>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={sectorAllocationData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={90}
                  dataKey="value"
                  nameKey="name"
                  stroke="#0f172a"
                  strokeWidth={2}
                >
                  {sectorAllocationData.map((_, i) => (
                    <Cell key={i} fill={SECTOR_COLORS[i % SECTOR_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }}
                  itemStyle={{ color: "#f1f5f9" }}
                  formatter={(value) => value != null ? `${Number(value).toFixed(1)}%` : "\u2014"}
                />
                <Legend
                  wrapperStyle={{ fontSize: 11, color: "#94a3b8" }}
                />
              </PieChart>
            </ResponsiveContainer>
            {sectorConcentrationWarning && (
              <div className="mt-2 text-[10px] text-amber-400">
                Warning: A sector exceeds 30% allocation.
              </div>
            )}
          </div>

          {/* Risk Profile Scatter */}
          <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
            <h3 className="text-sm font-semibold text-slate-300 mb-3">Risk Profile</h3>
            <ResponsiveContainer width="100%" height={250}>
              <ScatterChart margin={{ top: 10, right: 10, bottom: 10, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis
                  type="number"
                  dataKey="x"
                  name="Volatility"
                  tick={{ fill: "#64748b", fontSize: 10 }}
                  label={{ value: "Std Dev 52W (%)", position: "insideBottom", offset: -5, style: { fill: "#64748b", fontSize: 10 } }}
                />
                <YAxis
                  type="number"
                  dataKey="y"
                  name="Upside"
                  tick={{ fill: "#64748b", fontSize: 10 }}
                  label={{ value: "Upside (%)", angle: -90, position: "insideLeft", offset: 10, style: { fill: "#64748b", fontSize: 10 } }}
                />
                <Tooltip
                  contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }}
                  itemStyle={{ color: "#f1f5f9" }}
                  formatter={(value) => value != null ? `${Number(value).toFixed(1)}` : "\u2014"}
                  labelFormatter={() => ""}
                  cursor={{ strokeDasharray: "3 3" }}
                />
                <Scatter data={riskScatterData} fill="#34d399">
                  {riskScatterData.map((entry, i) => (
                    <Cell key={i} fill={SECTOR_COLORS[i % SECTOR_COLORS.length]} />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
            <div className="mt-1 flex justify-between text-[10px] text-slate-600">
              <span>Lower risk &larr;</span>
              <span>&rarr; Higher risk</span>
            </div>
          </div>
        </div>

        {/* Charts Row 2: Conviction + Data Quality */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Conviction Distribution */}
          <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
            <h3 className="text-sm font-semibold text-slate-300 mb-3">Conviction Distribution</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={convictionDistData} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="level" tick={{ fill: "#64748b", fontSize: 11 }} />
                <YAxis tick={{ fill: "#64748b", fontSize: 11 }} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }}
                  itemStyle={{ color: "#fbbf24" }}
                />
                <Bar dataKey="count" fill="#fbbf24" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            {lowConvictionWarning && (
              <div className="mt-2 text-[10px] text-amber-400">
                Warning: Average conviction below 3.
              </div>
            )}
          </div>

          {/* Data Quality */}
          <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
            <h3 className="text-sm font-semibold text-slate-300 mb-3">Data Quality</h3>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={qualityDistData}
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={70}
                  dataKey="value"
                  nameKey="name"
                  stroke="#0f172a"
                  strokeWidth={2}
                >
                  <Cell fill="#34d399" />
                  <Cell fill="#fbbf24" />
                  <Cell fill="#f87171" />
                </Pie>
                <Tooltip
                  contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }}
                  itemStyle={{ color: "#f1f5f9" }}
                />
                <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
              </PieChart>
            </ResponsiveContainer>
            {lowQualityAllocation > 10 && (
              <div className="mt-2 text-[10px] text-amber-400">
                Warning: Low confidence stocks have {lowQualityAllocation.toFixed(1)}% allocation (&gt;10%).
              </div>
            )}
          </div>
        </div>

        {/* Valuation Spread Histogram */}
        <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Valuation Spread</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={upsideHistData} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="range" tick={{ fill: "#64748b", fontSize: 10 }} />
              <YAxis tick={{ fill: "#64748b", fontSize: 11 }} allowDecimals={false} />
              <Tooltip
                contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }}
                itemStyle={{ color: "#34d399" }}
              />
              <Bar dataKey="count" fill="#34d399" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          {portfolio.some((ps) => ps.stock.signal?.includes("SELL")) && (
            <div className="mt-2 text-[10px] text-red-400">
              Note: Portfolio contains SELL-signal stocks.
            </div>
          )}
        </div>

        {/* Entry Strategy Table */}
        <div className="rounded-lg border border-slate-700 bg-slate-900 overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-700">
            <h3 className="text-sm font-semibold text-slate-300">Entry Strategy</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 bg-slate-900">
                  <th className="px-4 py-2 text-left text-xs font-medium uppercase text-slate-400">Ticker</th>
                  <th className="px-4 py-2 text-right text-xs font-medium uppercase text-slate-400">Price</th>
                  <th className="px-4 py-2 text-right text-xs font-medium uppercase text-slate-400">Buy Price</th>
                  <th className="px-4 py-2 text-right text-xs font-medium uppercase text-slate-400">Gap %</th>
                  <th className="px-4 py-2 text-center text-xs font-medium uppercase text-slate-400">Action</th>
                </tr>
              </thead>
              <tbody>
                {entryStrategyData.map((row) => (
                  <tr key={row.ticker} className="border-b border-slate-800 hover:bg-slate-800/50">
                    <td className="px-4 py-2 font-semibold text-sky-400">{row.ticker}</td>
                    <td className="px-4 py-2 text-right font-mono text-slate-200">
                      {formatValue(row.price, "currency")}
                    </td>
                    <td className="px-4 py-2 text-right font-mono text-slate-200">
                      {formatValue(row.buyPrice, "currency")}
                    </td>
                    <td className="px-4 py-2 text-right font-mono">
                      {row.gapPct !== null ? (
                        <span className={row.gapPct <= 0 ? "text-emerald-400" : "text-slate-400"}>
                          {row.gapPct > 0 ? "+" : ""}{row.gapPct.toFixed(1)}%
                        </span>
                      ) : (
                        <span className="text-slate-600">{"\u2014"}</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-center">
                      <span
                        className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                          row.actionColor === "emerald"
                            ? "bg-emerald-900/50 text-emerald-400"
                            : row.actionColor === "amber"
                            ? "bg-amber-900/50 text-amber-400"
                            : "bg-slate-700 text-slate-400"
                        }`}
                      >
                        {row.action}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
