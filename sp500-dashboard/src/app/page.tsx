"use client";

import { useState, useMemo, useCallback } from "react";
import {
  getAllStocks,
  getStrongBuys,
  getSectorSummaries,
  getDataQualities,
  getUniqueSectors,
  getUndervalued,
  getStockByTicker,
} from "@/lib/data";
import type { DataQuality } from "@/types/stock";
import { usePortfolio } from "@/context/PortfolioContext";
import SectorCard from "@/components/SectorCard";
import StockTable from "@/components/StockTable";
import FilterSidebar, { FilterState, defaultFilters } from "@/components/FilterSidebar";
import SearchBar from "@/components/SearchBar";

type ViewMode = "strong_buys" | "all" | "custom";

export default function OpportunityScanner() {
  const allStocks = useMemo(() => getAllStocks(), []);
  const strongBuys = useMemo(() => getStrongBuys(), []);
  const sectorSummaries = useMemo(() => getSectorSummaries(), []);
  const dataQualities = useMemo(() => getDataQualities(), []);
  const allSectors = useMemo(() => getUniqueSectors(), []);
  const undervalued = useMemo(() => getUndervalued(), []);
  const { portfolio, addStock, removeStock } = usePortfolio();

  const qualityMap = useMemo(() => {
    const map: Record<string, DataQuality> = {};
    for (const q of dataQualities) {
      map[q.ticker] = q;
    }
    return map;
  }, [dataQualities]);

  const selectedTickers = useMemo(() => {
    return new Set(portfolio.map((ps) => ps.stock.ticker));
  }, [portfolio]);

  const [viewMode, setViewMode] = useState<ViewMode>("strong_buys");
  const [filters, setFilters] = useState<FilterState>(defaultFilters);
  const [search, setSearch] = useState("");
  const [filtersCollapsed, setFiltersCollapsed] = useState(false);

  const toggleSelect = useCallback((ticker: string) => {
    if (selectedTickers.has(ticker)) {
      removeStock(ticker);
    } else {
      const stock = getStockByTicker(ticker);
      if (stock) {
        addStock(stock, qualityMap[ticker] ?? null);
      }
    }
  }, [selectedTickers, addStock, removeStock, qualityMap]);

  const baseStocks = useMemo(() => {
    if (viewMode === "strong_buys") return strongBuys;
    return allStocks;
  }, [viewMode, allStocks, strongBuys]);

  const filteredStocks = useMemo(() => {
    let result = baseStocks;

    // Search
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter(
        (s) =>
          s.ticker.toLowerCase().includes(q) ||
          s.company.toLowerCase().includes(q)
      );
    }

    // Only apply custom filters when in custom mode or all mode
    if (viewMode === "custom" || viewMode === "all") {
      // Sector filter
      if (filters.sectors.length > 0) {
        result = result.filter((s) => filters.sectors.includes(s.sector));
      }

      // Signal filter
      if (filters.signals.length > 0) {
        result = result.filter((s) => {
          if (!s.signal) return false;
          return filters.signals.some((sig) => s.signal!.toUpperCase().includes(sig));
        });
      }

      // Conviction filter
      if (filters.minConviction > 1) {
        result = result.filter(
          (s) => s.conviction !== null && s.conviction >= filters.minConviction
        );
      }

      // Upside range
      if (filters.upsideMin !== "") {
        const min = parseFloat(filters.upsideMin) / 100;
        result = result.filter(
          (s) => s.upsidePercent !== null && s.upsidePercent >= min
        );
      }
      if (filters.upsideMax !== "") {
        const max = parseFloat(filters.upsideMax) / 100;
        result = result.filter(
          (s) => s.upsidePercent !== null && s.upsidePercent <= max
        );
      }

      // RSI range
      if (filters.rsiMin !== "") {
        const min = parseFloat(filters.rsiMin);
        result = result.filter((s) => s.rsi !== null && s.rsi >= min);
      }
      if (filters.rsiMax !== "") {
        const max = parseFloat(filters.rsiMax);
        result = result.filter((s) => s.rsi !== null && s.rsi <= max);
      }

      // Max D/E
      if (filters.maxDE !== "") {
        const max = parseFloat(filters.maxDE);
        result = result.filter((s) => s.de !== null && s.de <= max);
      }

      // Min Sharpe
      if (filters.minSharpe !== "") {
        const min = parseFloat(filters.minSharpe);
        result = result.filter(
          (s) => s.sharpe52W !== null && s.sharpe52W >= min
        );
      }

      // Data Confidence
      if (filters.confidence.length > 0) {
        result = result.filter((s) => {
          const q = qualityMap[s.ticker];
          return q && filters.confidence.includes(q.confidence);
        });
      }
    }

    return result;
  }, [baseStocks, search, filters, viewMode, qualityMap]);

  // Summary stats
  const totalUndervalued = undervalued.length;
  const totalStrongBuys = strongBuys.length;
  const avgMarketUpside = useMemo(() => {
    const withUpside = allStocks.filter((s) => s.upsidePercent !== null);
    if (withUpside.length === 0) return 0;
    return (
      withUpside.reduce((sum, s) => sum + (s.upsidePercent ?? 0), 0) /
      withUpside.length *
      100
    );
  }, [allStocks]);

  return (
    <div className="space-y-6">
      {/* Market Pulse */}
      <section>
        <h2 className="text-lg font-semibold text-slate-200 mb-3">Market Pulse</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
          {sectorSummaries.map((sector) => (
            <SectorCard key={sector.sector} sector={sector} />
          ))}
        </div>
        <div className="mt-3 flex flex-wrap gap-4 rounded-lg border border-slate-700 bg-slate-900 px-4 py-2.5 text-sm">
          <span className="text-slate-400">
            <span className="font-mono text-emerald-400">{totalUndervalued}</span> of {allStocks.length} stocks undervalued
          </span>
          <span className="text-slate-600">|</span>
          <span className="text-slate-400">
            <span className="font-mono text-emerald-400">{totalStrongBuys}</span> Strong Buys
          </span>
          <span className="text-slate-600">|</span>
          <span className="text-slate-400">
            Avg market upside:{" "}
            <span className={`font-mono ${avgMarketUpside >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {avgMarketUpside > 0 ? "+" : ""}{avgMarketUpside.toFixed(1)}%
            </span>
          </span>
        </div>
      </section>

      {/* Stock Screener */}
      <section>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h2 className="text-lg font-semibold text-slate-200">Stock Screener</h2>
          <div className="flex items-center gap-2">
            <div className="flex rounded-md border border-slate-700 bg-slate-800 overflow-hidden">
              {(
                [
                  { key: "strong_buys" as ViewMode, label: "Strong Buys" },
                  { key: "all" as ViewMode, label: `All ${allStocks.length}` },
                  { key: "custom" as ViewMode, label: "Custom Filter" },
                ] as const
              ).map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => setViewMode(key)}
                  className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                    viewMode === key
                      ? "bg-emerald-600 text-white"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-700"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <span className="text-xs text-slate-500">
              {filteredStocks.length} result{filteredStocks.length !== 1 ? "s" : ""}
            </span>
          </div>
        </div>

        <div className="mb-4 max-w-md">
          <SearchBar value={search} onChange={setSearch} />
        </div>

        <div className="flex gap-4">
          {(viewMode === "custom" || viewMode === "all") && (
            <FilterSidebar
              filters={filters}
              onChange={setFilters}
              allSectors={allSectors}
              collapsed={filtersCollapsed}
              onToggle={() => setFiltersCollapsed(!filtersCollapsed)}
            />
          )}
          <div className="flex-1 min-w-0">
            <StockTable
              stocks={filteredStocks}
              qualityMap={qualityMap}
              selectedTickers={selectedTickers}
              onToggleSelect={toggleSelect}
            />
          </div>
        </div>
      </section>
    </div>
  );
}
