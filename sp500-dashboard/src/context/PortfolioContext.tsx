'use client';

import { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef } from 'react';
import type { ReactNode } from 'react';
import type { StockData, DataQuality, PortfolioStock } from '@/types/stock';
import { getPortfolioStats, getQualityForTicker } from '@/lib/data';
import type { PortfolioStats } from '@/lib/data';

const STORAGE_KEY = 'sp500-portfolio';

interface PortfolioActions {
  addStock: (stock: StockData, quality?: DataQuality | null) => void;
  removeStock: (ticker: string) => void;
  updateAllocation: (ticker: string, percent: number) => void;
  updateStatus: (ticker: string, status: PortfolioStock['status']) => void;
  updateNotes: (ticker: string, notes: string) => void;
  clearPortfolio: () => void;
  equalWeight: () => void;
  weightByConviction: () => void;
  weightByUpside: () => void;
}

interface PortfolioContextValue extends PortfolioActions {
  portfolio: PortfolioStock[];
  stats: PortfolioStats;
}

const PortfolioContext = createContext<PortfolioContextValue | null>(null);

function loadFromStorage(): PortfolioStock[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed;
  } catch {
    return [];
  }
}

function saveToStorage(portfolio: PortfolioStock[]): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(portfolio));
  } catch {
    // Storage full or unavailable -- silently ignore
  }
}

export function PortfolioProvider({ children }: { children: ReactNode }) {
  const [portfolio, setPortfolio] = useState<PortfolioStock[]>(() => loadFromStorage());
  const hydrated = useRef(false);

  // Mark hydrated after first render
  useEffect(() => {
    hydrated.current = true;
  }, []);

  // Persist to localStorage on change (skip initial mount)
  useEffect(() => {
    if (hydrated.current) {
      saveToStorage(portfolio);
    }
  }, [portfolio]);

  const addStock = useCallback((stock: StockData, quality?: DataQuality | null) => {
    setPortfolio((prev) => {
      if (prev.some((ps) => ps.stock.ticker === stock.ticker)) return prev;
      const q = quality !== undefined ? quality : getQualityForTicker(stock.ticker);
      return [
        ...prev,
        {
          stock,
          quality: q ?? null,
          allocationPercent: 0,
          status: 'interested' as const,
          notes: '',
        },
      ];
    });
  }, []);

  const removeStock = useCallback((ticker: string) => {
    setPortfolio((prev) => prev.filter((ps) => ps.stock.ticker !== ticker));
  }, []);

  const updateAllocation = useCallback((ticker: string, percent: number) => {
    setPortfolio((prev) =>
      prev.map((ps) =>
        ps.stock.ticker === ticker ? { ...ps, allocationPercent: Math.max(0, Math.min(100, percent)) } : ps
      )
    );
  }, []);

  const updateStatus = useCallback((ticker: string, status: PortfolioStock['status']) => {
    setPortfolio((prev) =>
      prev.map((ps) => (ps.stock.ticker === ticker ? { ...ps, status } : ps))
    );
  }, []);

  const updateNotes = useCallback((ticker: string, notes: string) => {
    setPortfolio((prev) =>
      prev.map((ps) => (ps.stock.ticker === ticker ? { ...ps, notes } : ps))
    );
  }, []);

  const clearPortfolio = useCallback(() => {
    setPortfolio([]);
  }, []);

  const equalWeight = useCallback(() => {
    setPortfolio((prev) => {
      if (prev.length === 0) return prev;
      const weight = 100 / prev.length;
      return prev.map((ps) => ({ ...ps, allocationPercent: Math.round(weight * 100) / 100 }));
    });
  }, []);

  const weightByConviction = useCallback(() => {
    setPortfolio((prev) => {
      if (prev.length === 0) return prev;
      const totalConviction = prev.reduce((sum, ps) => sum + (ps.stock.conviction ?? 1), 0);
      if (totalConviction === 0) return prev;
      return prev.map((ps) => ({
        ...ps,
        allocationPercent: Math.round(((ps.stock.conviction ?? 1) / totalConviction) * 10000) / 100,
      }));
    });
  }, []);

  const weightByUpside = useCallback(() => {
    setPortfolio((prev) => {
      if (prev.length === 0) return prev;
      // Only weight positive-upside stocks; zero-or-negative get minimum allocation
      const positiveStocks = prev.filter(
        (ps) => ps.stock.upsidePercent !== null && ps.stock.upsidePercent > 0
      );
      const totalUpside = positiveStocks.reduce(
        (sum, ps) => sum + (ps.stock.upsidePercent ?? 0),
        0
      );
      if (totalUpside === 0) return prev;
      return prev.map((ps) => {
        const upside = ps.stock.upsidePercent;
        if (upside === null || upside <= 0) {
          return { ...ps, allocationPercent: 0 };
        }
        return {
          ...ps,
          allocationPercent: Math.round((upside / totalUpside) * 10000) / 100,
        };
      });
    });
  }, []);

  const stats = useMemo(() => getPortfolioStats(portfolio), [portfolio]);

  const value = useMemo<PortfolioContextValue>(
    () => ({
      portfolio,
      stats,
      addStock,
      removeStock,
      updateAllocation,
      updateStatus,
      updateNotes,
      clearPortfolio,
      equalWeight,
      weightByConviction,
      weightByUpside,
    }),
    [
      portfolio,
      stats,
      addStock,
      removeStock,
      updateAllocation,
      updateStatus,
      updateNotes,
      clearPortfolio,
      equalWeight,
      weightByConviction,
      weightByUpside,
    ]
  );

  return <PortfolioContext.Provider value={value}>{children}</PortfolioContext.Provider>;
}

export function usePortfolio(): PortfolioContextValue {
  const ctx = useContext(PortfolioContext);
  if (!ctx) {
    throw new Error('usePortfolio must be used within a PortfolioProvider');
  }
  return ctx;
}
