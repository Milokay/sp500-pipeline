import type { StockData, SectorSummary, DataQuality, Assumption, PortfolioStock } from '@/types/stock';

import dashboardJson from '@/data/dashboard.json';
import strongBuysJson from '@/data/strongBuys.json';
import sectorSummaryJson from '@/data/sectorSummary.json';
import dataQualityJson from '@/data/dataQuality.json';
import assumptionsJson from '@/data/assumptions.json';

// Cast imported JSON to typed arrays
const allStocks: StockData[] = dashboardJson as StockData[];
const strongBuysList: StockData[] = strongBuysJson as StockData[];
const sectorSummaries: SectorSummary[] = sectorSummaryJson as SectorSummary[];
const dataQualities: DataQuality[] = dataQualityJson as DataQuality[];
const assumptionsList: Assumption[] = assumptionsJson as Assumption[];

// ---------------------------------------------------------------------------
// Data accessors
// ---------------------------------------------------------------------------

export function getAllStocks(): StockData[] {
  return allStocks;
}

export function getStrongBuys(): StockData[] {
  return allStocks.filter(
    (s) => s.signal !== null && s.signal.includes('BUY') && s.conviction !== null && s.conviction >= 4
  );
}

export function getPrecomputedStrongBuys(): StockData[] {
  return strongBuysList;
}

export function getByConviction(n: number): StockData[] {
  return allStocks.filter((s) => s.conviction === n);
}

export function getBySector(sector: string): StockData[] {
  return allStocks.filter((s) => s.sector === sector);
}

export function getUndervalued(): StockData[] {
  return allStocks.filter((s) => s.upsidePercent !== null && s.upsidePercent > 0);
}

export function getOvervalued(): StockData[] {
  return allStocks.filter((s) => s.upsidePercent !== null && s.upsidePercent < 0);
}

export function getSectorSummaries(): SectorSummary[] {
  return sectorSummaries;
}

export function getDataQualities(): DataQuality[] {
  return dataQualities;
}

export function getQualityForTicker(ticker: string): DataQuality | null {
  return dataQualities.find((d) => d.ticker === ticker) ?? null;
}

export function getAssumptions(): Assumption[] {
  return assumptionsList;
}

export function getStockByTicker(ticker: string): StockData | null {
  return allStocks.find((s) => s.ticker === ticker) ?? null;
}

export function getUniqueSectors(): string[] {
  const sectors = new Set(allStocks.map((s) => s.sector));
  return Array.from(sectors).sort();
}

// ---------------------------------------------------------------------------
// Sorting
// ---------------------------------------------------------------------------

export function sortBy<T>(
  arr: T[],
  column: keyof T,
  direction: 'asc' | 'desc' = 'desc'
): T[] {
  return [...arr].sort((a, b) => {
    const aVal = a[column];
    const bVal = b[column];
    if (aVal === null || aVal === undefined) return 1;
    if (bVal === null || bVal === undefined) return -1;
    if (typeof aVal === 'string' && typeof bVal === 'string') {
      return direction === 'asc'
        ? aVal.localeCompare(bVal)
        : bVal.localeCompare(aVal);
    }
    const diff = (aVal as number) - (bVal as number);
    return direction === 'asc' ? diff : -diff;
  });
}

// ---------------------------------------------------------------------------
// Computed metrics
// ---------------------------------------------------------------------------

/** (buyPrice - price) / price. Negative = price already below buy price = good margin of safety */
export function getMarginOfSafety(stock: StockData): number | null {
  if (stock.buyPrice === null || stock.price === null || stock.price === 0) return null;
  return (stock.buyPrice - stock.price) / stock.price;
}

/** |ivExitMult - ivPerpGrowth| / average of both. Higher = more model disagreement */
export function getValuationGap(stock: StockData): number | null {
  if (stock.ivExitMult === null || stock.ivPerpGrowth === null) return null;
  const avg = (stock.ivExitMult + stock.ivPerpGrowth) / 2;
  if (avg === 0) return null;
  return Math.abs(stock.ivExitMult - stock.ivPerpGrowth) / avg;
}

/** Composite risk score normalized to 0-100. Higher = riskier. */
export function getRiskScore(stock: StockData): number | null {
  const quality = getQualityForTicker(stock.ticker);
  const confMap: Record<string, number> = { High: 0, Medium: 33, Low: 66 };
  const confScore = quality ? (confMap[quality.confidence] ?? 50) : 50;

  // Normalize stdDev52W: typical range 0-1, map to 0-100
  const volScore = stock.stdDev52W !== null ? Math.min(stock.stdDev52W * 100, 100) : 50;

  // Normalize D/E: 0 is safe, >3 is risky
  const deScore = stock.de !== null ? Math.min((Math.abs(stock.de) / 3) * 100, 100) : 50;

  // Weighted composite
  const score = volScore * 0.4 + deScore * 0.3 + confScore * 0.3;
  return Math.round(Math.min(Math.max(score, 0), 100));
}

/** Composite quality score normalized to 0-100. Higher = better quality business. */
export function getQualityScore(stock: StockData): number | null {
  let total = 0;
  let weights = 0;

  // ROE: good > 15%, great > 25%
  if (stock.roe !== null) {
    total += Math.min(Math.max(stock.roe * 100 / 0.3, 0), 100) * 0.3;
    weights += 0.3;
  }

  // EBITDA margin: good > 15%, great > 30%
  if (stock.ebitdaPercent !== null) {
    total += Math.min(Math.max(stock.ebitdaPercent * 100 / 0.4, 0), 100) * 0.25;
    weights += 0.25;
  }

  // Net Margin: good > 10%, great > 20%
  if (stock.netMarginPercent !== null) {
    total += Math.min(Math.max(stock.netMarginPercent * 100 / 0.25, 0), 100) * 0.25;
    weights += 0.25;
  }

  // Sharpe: good > 1, great > 2
  if (stock.sharpe52W !== null) {
    total += Math.min(Math.max((stock.sharpe52W + 1) / 3 * 100, 0), 100) * 0.2;
    weights += 0.2;
  }

  if (weights === 0) return null;
  return Math.round(Math.min(Math.max(total / weights, 0), 100));
}

// ---------------------------------------------------------------------------
// Sector analysis
// ---------------------------------------------------------------------------

/** Compute allocation percentages by sector */
export function getSectorAllocation(stocks: StockData[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const s of stocks) {
    counts[s.sector] = (counts[s.sector] || 0) + 1;
  }
  const total = stocks.length || 1;
  const result: Record<string, number> = {};
  for (const [sector, count] of Object.entries(counts)) {
    result[sector] = count / total;
  }
  return result;
}

/** Compute median of a numeric array (ignoring nulls) */
function median(values: (number | null)[]): number | null {
  const filtered = values.filter((v): v is number => v !== null);
  if (filtered.length === 0) return null;
  const sorted = [...filtered].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0
    ? sorted[mid]
    : (sorted[mid - 1] + sorted[mid]) / 2;
}

/** Compute median of each key metric per sector */
export function getSectorMedians(stocks: StockData[]): Record<string, {
  medianPE: number | null;
  medianPB: number | null;
  medianROA: number | null;
  medianROE: number | null;
  medianUpside: number | null;
  medianRSI: number | null;
  medianDE: number | null;
}> {
  const grouped: Record<string, StockData[]> = {};
  for (const s of stocks) {
    if (!grouped[s.sector]) grouped[s.sector] = [];
    grouped[s.sector].push(s);
  }

  const result: Record<string, {
    medianPE: number | null;
    medianPB: number | null;
    medianROA: number | null;
    medianROE: number | null;
    medianUpside: number | null;
    medianRSI: number | null;
    medianDE: number | null;
  }> = {};

  for (const [sector, sectorStocks] of Object.entries(grouped)) {
    result[sector] = {
      medianPE: median(sectorStocks.map((s) => s.pe)),
      medianPB: median(sectorStocks.map((s) => s.pb)),
      medianROA: median(sectorStocks.map((s) => s.roa)),
      medianROE: median(sectorStocks.map((s) => s.roe)),
      medianUpside: median(sectorStocks.map((s) => s.upsidePercent)),
      medianRSI: median(sectorStocks.map((s) => s.rsi)),
      medianDE: median(sectorStocks.map((s) => s.de)),
    };
  }

  return result;
}

// ---------------------------------------------------------------------------
// Portfolio analysis
// ---------------------------------------------------------------------------

export interface PortfolioStats {
  weightedUpside: number;
  weightedSharpe: number;
  avgConviction: number;
  sectorConcentration: number;
  totalAllocation: number;
}

/** Compute aggregate portfolio statistics */
export function getPortfolioStats(portfolioStocks: PortfolioStock[]): PortfolioStats {
  if (portfolioStocks.length === 0) {
    return { weightedUpside: 0, weightedSharpe: 0, avgConviction: 0, sectorConcentration: 0, totalAllocation: 0 };
  }

  const totalAllocation = portfolioStocks.reduce((sum, ps) => sum + ps.allocationPercent, 0);
  const allocNorm = totalAllocation || 1;

  // Weighted upside
  let weightedUpside = 0;
  for (const ps of portfolioStocks) {
    if (ps.stock.upsidePercent !== null) {
      weightedUpside += ps.stock.upsidePercent * (ps.allocationPercent / allocNorm);
    }
  }

  // Weighted Sharpe
  let weightedSharpe = 0;
  for (const ps of portfolioStocks) {
    if (ps.stock.sharpe52W !== null) {
      weightedSharpe += ps.stock.sharpe52W * (ps.allocationPercent / allocNorm);
    }
  }

  // Average conviction
  const convictions = portfolioStocks
    .map((ps) => ps.stock.conviction)
    .filter((c): c is number => c !== null);
  const avgConviction = convictions.length > 0
    ? convictions.reduce((a, b) => a + b, 0) / convictions.length
    : 0;

  // Sector concentration (Herfindahl-Hirschman Index normalized to 0-1)
  const sectorWeights: Record<string, number> = {};
  for (const ps of portfolioStocks) {
    sectorWeights[ps.stock.sector] =
      (sectorWeights[ps.stock.sector] || 0) + ps.allocationPercent / allocNorm;
  }
  const hhi = Object.values(sectorWeights).reduce((sum, w) => sum + w * w, 0);
  const sectorConcentration = hhi;

  return {
    weightedUpside,
    weightedSharpe,
    avgConviction,
    sectorConcentration,
    totalAllocation,
  };
}
