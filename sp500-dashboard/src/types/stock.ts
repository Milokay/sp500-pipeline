export interface StockData {
  ticker: string;
  company: string;
  sector: string;
  price: number | null;
  intrinsicValue: number | null;
  upsidePercent: number | null;
  lowerBand: number | null;
  upperBand: number | null;
  bandPosition: 'Upper Half' | 'Lower Half' | null;
  rsi: number | null;
  signal: 'BUY' | 'BUY (Low Confidence)' | 'SELL' | 'SELL (Low Confidence)' | 'HOLD' | null;
  conviction: number | null;
  rationale: string | null;
  pe: number | null;
  pb: number | null;
  eps: number | null;
  roa: number | null;
  roe: number | null;
  ebitdaPercent: number | null;
  netMarginPercent: number | null;
  de: number | null;
  ivExitMult: number | null;
  ivPerpGrowth: number | null;
  exitMultiple: number | null;
  impliedG: number | null;
  return1M: number | null;
  return6M: number | null;
  return1Y: number | null;
  return3Y: number | null;
  stdDev52W: number | null;
  sharpe52W: number | null;
  buyPrice: number | null;
}

export interface SectorSummary {
  sector: string;
  stockCount: number;
  avgUpsidePercent: number;
  undervaluedCount: number;
  overvaluedCount: number;
  avgRSI: number;
}

export interface DataQuality {
  ticker: string;
  confidence: 'High' | 'Medium' | 'Low';
  missingFields: string | null;
  lastUpdated: string | null;
  notes: string | null;
}

export interface Assumption {
  parameter: string;
  value: string;
  description: string;
}

export interface PortfolioStock {
  stock: StockData;
  quality: DataQuality | null;
  allocationPercent: number;
  status: 'interested' | 'committed';
  notes: string;
}

/**
 * Maps Excel column headers to StockData property names.
 * Used by the parser to convert raw Excel rows into typed objects.
 */
export const COLUMN_MAP: Record<string, keyof StockData> = {
  'Ticker': 'ticker',
  'Company': 'company',
  'Sector': 'sector',
  'Price': 'price',
  'Intrinsic Value': 'intrinsicValue',
  'Upside %': 'upsidePercent',
  'Lower Band': 'lowerBand',
  'Upper Band': 'upperBand',
  'Band Position': 'bandPosition',
  'RSI': 'rsi',
  'Signal': 'signal',
  'Conviction': 'conviction',
  'Rationale': 'rationale',
  'P/E': 'pe',
  'P/B': 'pb',
  'EPS': 'eps',
  'ROA': 'roa',
  'ROE': 'roe',
  'EBITDA%': 'ebitdaPercent',
  'Net Margin%': 'netMarginPercent',
  'D/E': 'de',
  'IV (Exit Mult)': 'ivExitMult',
  'IV (Perp Growth)': 'ivPerpGrowth',
  'Exit Multiple': 'exitMultiple',
  'Implied g': 'impliedG',
  'Return 1M': 'return1M',
  'Return 6M': 'return6M',
  'Return 1Y': 'return1Y',
  'Return 3Y': 'return3Y',
  'Std Dev 52W': 'stdDev52W',
  'Sharpe 52W': 'sharpe52W',
  'Buy Price': 'buyPrice',
};

/** Numeric fields in StockData that should have NaN/undefined/empty converted to null */
export const NUMERIC_STOCK_FIELDS: (keyof StockData)[] = [
  'price', 'intrinsicValue', 'upsidePercent', 'lowerBand', 'upperBand',
  'rsi', 'conviction', 'pe', 'pb', 'eps', 'roa', 'roe',
  'ebitdaPercent', 'netMarginPercent', 'de', 'ivExitMult', 'ivPerpGrowth',
  'exitMultiple', 'impliedG', 'return1M', 'return6M', 'return1Y', 'return3Y',
  'stdDev52W', 'sharpe52W', 'buyPrice',
];

/** Column map for Sector Summary sheet */
export const SECTOR_SUMMARY_MAP: Record<string, keyof SectorSummary> = {
  'Sector': 'sector',
  '# Stocks': 'stockCount',
  'Avg Upside %': 'avgUpsidePercent',
  '# Undervalued': 'undervaluedCount',
  '# Overvalued': 'overvaluedCount',
  'Avg RSI': 'avgRSI',
};

/** Column map for Data Quality sheet */
export const DATA_QUALITY_MAP: Record<string, keyof DataQuality> = {
  'Ticker': 'ticker',
  'Confidence': 'confidence',
  'Missing Fields': 'missingFields',
  'Last Updated': 'lastUpdated',
  'Notes': 'notes',
};

/** Column map for Assumptions sheet */
export const ASSUMPTIONS_MAP: Record<string, keyof Assumption> = {
  'Parameter': 'parameter',
  'Value': 'value',
  'Description': 'description',
};
