"use client";

import { use, useMemo, useState } from "react";
import Link from "next/link";
import {
  getStockByTicker,
  getQualityForTicker,
  getMarginOfSafety,
  getValuationGap,
  getAllStocks,
  getSectorMedians,
} from "@/lib/data";
import { usePortfolio } from "@/context/PortfolioContext";
import { formatValue } from "@/lib/format";
import SignalBadge from "@/components/SignalBadge";
import ConvictionStars from "@/components/ConvictionStars";
import MetricCard from "@/components/MetricCard";
import PriceBar from "@/components/PriceBar";
import RSIGauge from "@/components/RSIGauge";
import ConfidenceDot from "@/components/ConfidenceDot";

function MomentumCard({ label, value }: { label: string; value: number | null }) {
  if (value === null) {
    return (
      <div className="rounded-lg border border-slate-700 bg-slate-900 p-3 text-center">
        <div className="text-xs text-slate-500">{label}</div>
        <div className="font-mono text-lg text-slate-600 mt-1">{"\u2014"}</div>
      </div>
    );
  }
  const pct = value * 100;
  const isPositive = pct >= 0;
  const color = isPositive ? "text-emerald-400" : "text-red-400";
  const arrow = isPositive ? "\u25B2" : "\u25BC";

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900 p-3 text-center">
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`font-mono text-lg font-bold ${color} mt-1`}>
        {arrow} {pct > 0 ? "+" : ""}{pct.toFixed(1)}%
      </div>
    </div>
  );
}

function CompareMetric({
  label,
  value,
  sectorMedian,
  format = "ratio",
  higherIsBetter = true,
}: {
  label: string;
  value: number | null;
  sectorMedian: number | null;
  format?: "ratio" | "percentage";
  higherIsBetter?: boolean;
}) {
  const display =
    value === null
      ? "\u2014"
      : format === "percentage"
      ? `${(value * 100).toFixed(1)}%`
      : value.toFixed(2);

  let compareColor = "text-slate-400";
  let compareText = "";
  if (value !== null && sectorMedian !== null) {
    const isBetter = higherIsBetter ? value > sectorMedian : value < sectorMedian;
    compareColor = isBetter ? "text-emerald-400" : "text-red-400";
    const medianDisplay =
      format === "percentage" ? `${(sectorMedian * 100).toFixed(1)}%` : sectorMedian.toFixed(2);
    compareText = `vs ${medianDisplay} sector median`;
  }

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900 p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`font-mono text-lg font-bold mt-1 ${value === null ? "text-slate-600" : compareColor}`}>
        {display}
      </div>
      {compareText && <div className="text-[10px] text-slate-500 mt-1">{compareText}</div>}
    </div>
  );
}

export default function StockDeepDive({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = use(params);
  const decodedTicker = decodeURIComponent(ticker).toUpperCase();

  const { portfolio, addStock, removeStock } = usePortfolio();
  const [added, setAdded] = useState(false);

  const stock = useMemo(() => getStockByTicker(decodedTicker), [decodedTicker]);
  const quality = useMemo(() => getQualityForTicker(decodedTicker), [decodedTicker]);
  const sectorMedians = useMemo(() => getSectorMedians(getAllStocks()), []);
  const isInPortfolio = useMemo(
    () => portfolio.some((ps) => ps.stock.ticker === decodedTicker),
    [portfolio, decodedTicker]
  );

  if (!stock) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <h1 className="text-2xl font-bold text-slate-300 mb-2">Stock Not Found</h1>
        <p className="text-slate-500 mb-4">No data found for ticker &quot;{decodedTicker}&quot;</p>
        <Link href="/" className="text-emerald-400 hover:underline">
          Back to Scanner
        </Link>
      </div>
    );
  }

  const mos = getMarginOfSafety(stock);
  const valGap = getValuationGap(stock);
  const medians = sectorMedians[stock.sector];
  const ivLow = stock.ivExitMult !== null && stock.ivPerpGrowth !== null
    ? Math.min(stock.ivExitMult, stock.ivPerpGrowth)
    : stock.ivExitMult ?? stock.ivPerpGrowth;
  const ivHigh = stock.ivExitMult !== null && stock.ivPerpGrowth !== null
    ? Math.max(stock.ivExitMult, stock.ivPerpGrowth)
    : stock.ivExitMult ?? stock.ivPerpGrowth;
  const avgIV = stock.ivExitMult !== null && stock.ivPerpGrowth !== null
    ? (stock.ivExitMult + stock.ivPerpGrowth) / 2
    : stock.intrinsicValue;

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link href="/" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-emerald-400">
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Back to Scanner
      </Link>

      {/* Header */}
      <div className="flex flex-wrap items-center gap-4">
        <h1 className="text-3xl font-bold text-slate-100">{stock.ticker}</h1>
        <div className="text-lg text-slate-400">{stock.company}</div>
        <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs text-slate-400">{stock.sector}</span>
        <SignalBadge signal={stock.signal} />
        <ConvictionStars level={stock.conviction} size="lg" />
      </div>

      {/* Section A: Valuation Verdict */}
      <section className="rounded-lg border border-slate-700 bg-slate-900 p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4">Valuation Verdict</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4 mb-4">
          <MetricCard label="Current Price" value={formatValue(stock.price, "currency")} color="sky" />
          <MetricCard label="IV (Exit Mult)" value={formatValue(stock.ivExitMult, "currency")} color="slate" />
          <MetricCard label="IV (Perp Growth)" value={formatValue(stock.ivPerpGrowth, "currency")} color="slate" />
          <MetricCard label="Average IV" value={formatValue(avgIV, "currency")} color="emerald" />
          <MetricCard
            label="Upside %"
            value={stock.upsidePercent !== null ? `${stock.upsidePercent > 0 ? "+" : ""}${(stock.upsidePercent * 100).toFixed(1)}%` : "\u2014"}
            color={stock.upsidePercent !== null && stock.upsidePercent > 0 ? "emerald" : "red"}
            size="lg"
          />
          <MetricCard label="Buy Price" value={formatValue(stock.buyPrice, "currency")} color="amber" />
          <MetricCard
            label="Margin of Safety"
            value={mos !== null ? `${(mos * 100).toFixed(1)}%` : "\u2014"}
            color={mos !== null && mos < 0 ? "emerald" : "red"}
          />
        </div>

        <PriceBar buyPrice={stock.buyPrice} currentPrice={stock.price} ivLow={ivLow} ivHigh={ivHigh} />

        {valGap !== null && valGap > 0.5 && (
          <div className="mt-3 rounded-md border border-amber-700/50 bg-amber-900/20 px-3 py-2 text-xs text-amber-400">
            Valuation model disagreement: The two IV methods differ by {(valGap * 100).toFixed(0)}%. Exercise caution with this estimate.
          </div>
        )}
      </section>

      {/* Section B: Technical Position */}
      <section className="rounded-lg border border-slate-700 bg-slate-900 p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4">Technical Position</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Bollinger Band */}
          <div>
            <div className="text-xs text-slate-500 mb-2">Bollinger Bands</div>
            <div className="relative h-8 w-full rounded bg-slate-800">
              {stock.lowerBand !== null && stock.upperBand !== null && stock.price !== null && (
                <>
                  <div className="absolute inset-0 flex items-center justify-between px-2 text-[10px] text-slate-600">
                    <span>${stock.lowerBand.toFixed(0)}</span>
                    <span>${stock.upperBand.toFixed(0)}</span>
                  </div>
                  <div
                    className="absolute top-1 bottom-1 w-2 rounded bg-sky-400"
                    style={{
                      left: `${Math.max(0, Math.min(100, ((stock.price - stock.lowerBand) / (stock.upperBand - stock.lowerBand)) * 100))}%`,
                    }}
                  />
                </>
              )}
            </div>
            <div className="mt-1 text-center">
              <span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
                {stock.bandPosition ?? "\u2014"}
              </span>
            </div>
          </div>

          {/* RSI Gauge */}
          <div className="flex justify-center">
            <RSIGauge value={stock.rsi} size={140} />
          </div>

          {/* Momentum */}
          <div className="grid grid-cols-2 gap-2">
            <MomentumCard label="1 Month" value={stock.return1M} />
            <MomentumCard label="6 Month" value={stock.return6M} />
            <MomentumCard label="1 Year" value={stock.return1Y} />
            <MomentumCard label="3 Year" value={stock.return3Y} />
          </div>
        </div>
      </section>

      {/* Section C: Fundamental Quality */}
      <section className="rounded-lg border border-slate-700 bg-slate-900 p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4">Fundamental Quality</h2>

        <div className="text-xs text-slate-500 mb-2">Profitability</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <CompareMetric label="ROA" value={stock.roa} sectorMedian={medians?.medianROA ?? null} format="percentage" />
          <CompareMetric label="ROE" value={stock.roe} sectorMedian={medians?.medianROE ?? null} format="percentage" />
          <MetricCard label="EBITDA %" value={stock.ebitdaPercent !== null ? `${(stock.ebitdaPercent * 100).toFixed(1)}%` : "\u2014"} />
          <MetricCard label="Net Margin %" value={stock.netMarginPercent !== null ? `${(stock.netMarginPercent * 100).toFixed(1)}%` : "\u2014"} />
        </div>

        <div className="text-xs text-slate-500 mb-2">Valuation</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <CompareMetric label="P/E" value={stock.pe} sectorMedian={medians?.medianPE ?? null} higherIsBetter={false} />
          <CompareMetric label="P/B" value={stock.pb} sectorMedian={medians?.medianPB ?? null} higherIsBetter={false} />
          <MetricCard label="EPS" value={stock.eps !== null ? `$${stock.eps.toFixed(2)}` : "\u2014"} />
          <MetricCard label="Exit Multiple" value={stock.exitMultiple !== null ? stock.exitMultiple.toFixed(1) + "x" : "\u2014"} />
        </div>

        <div className="text-xs text-slate-500 mb-2">Risk</div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <CompareMetric label="D/E" value={stock.de} sectorMedian={medians?.medianDE ?? null} higherIsBetter={false} />
          <MetricCard label="Std Dev 52W" value={stock.stdDev52W !== null ? `${(stock.stdDev52W * 100).toFixed(1)}%` : "\u2014"} />
          <MetricCard
            label="Sharpe 52W"
            value={stock.sharpe52W !== null ? stock.sharpe52W.toFixed(2) : "\u2014"}
            color={stock.sharpe52W !== null && stock.sharpe52W > 1 ? "emerald" : stock.sharpe52W !== null && stock.sharpe52W < 0 ? "red" : "slate"}
          />
        </div>
      </section>

      {/* Section D: Model Confidence */}
      <section className="rounded-lg border border-slate-700 bg-slate-900 p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4">Model Confidence</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs text-slate-500">Data Quality:</span>
              <ConfidenceDot confidence={quality?.confidence} />
            </div>
            {quality?.missingFields && (
              <div className="text-xs text-slate-500 mb-2">
                <span className="text-slate-400">Missing Fields:</span> {quality.missingFields}
              </div>
            )}
            {quality?.notes && (
              <div className="text-xs text-slate-500">
                <span className="text-slate-400">Notes:</span> {quality.notes}
              </div>
            )}
          </div>
          <div>
            <div className="text-xs text-slate-500 mb-1">Implied Growth Rate</div>
            <div className={`font-mono text-sm ${stock.impliedG !== null && stock.impliedG > 0.04 ? "text-red-400" : "text-slate-300"}`}>
              {stock.impliedG !== null ? `${(stock.impliedG * 100).toFixed(2)}%` : "\u2014"}
            </div>
            {stock.impliedG !== null && stock.impliedG > 0.04 && (
              <div className="mt-1 rounded-md border border-red-700/50 bg-red-900/20 px-2 py-1 text-[10px] text-red-400">
                Implied growth rate exceeds GDP ceiling (4%). Model assumptions may be overly optimistic.
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Section E: Decision Box */}
      <section className="rounded-lg border border-slate-700 bg-slate-900 p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4">Decision</h2>
        {stock.rationale && (
          <div className="mb-4 rounded-md border-l-4 border-slate-600 bg-slate-800/50 px-4 py-3 text-sm text-slate-300 italic">
            {stock.rationale}
          </div>
        )}
        <div className="flex flex-wrap gap-3">
          {isInPortfolio ? (
            <button
              onClick={() => removeStock(decodedTicker)}
              className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-500 transition-colors"
            >
              Remove from Portfolio
            </button>
          ) : (
            <button
              onClick={() => {
                if (stock) {
                  addStock(stock, quality);
                  setAdded(true);
                  setTimeout(() => setAdded(false), 2000);
                }
              }}
              className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 transition-colors"
            >
              {added ? "Added!" : "Add to Portfolio"}
            </button>
          )}
          <button
            onClick={() => {
              if (stock) {
                addStock(stock, quality);
                setAdded(true);
                setTimeout(() => setAdded(false), 2000);
              }
            }}
            className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              isInPortfolio
                ? "bg-amber-700 text-amber-200 cursor-default"
                : "bg-amber-600 text-white hover:bg-amber-500"
            }`}
            disabled={isInPortfolio}
          >
            Watchlist
          </button>
          <Link
            href="/"
            className="rounded-md bg-slate-700 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-slate-600 transition-colors"
          >
            Skip
          </Link>
        </div>
      </section>
    </div>
  );
}
