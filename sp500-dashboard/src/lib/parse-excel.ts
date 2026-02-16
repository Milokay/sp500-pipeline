import * as XLSX from 'xlsx';
import {
  StockData,
  SectorSummary,
  DataQuality,
  Assumption,
  COLUMN_MAP,
  NUMERIC_STOCK_FIELDS,
  SECTOR_SUMMARY_MAP,
  DATA_QUALITY_MAP,
  ASSUMPTIONS_MAP,
} from '@/types/stock';

/** Convert a value to number or null. Handles NaN, undefined, empty string, "N/A". */
function toNumberOrNull(val: unknown): number | null {
  if (val === undefined || val === null || val === '' || val === 'N/A' || val === 'n/a') {
    return null;
  }
  const n = typeof val === 'number' ? val : Number(val);
  if (Number.isNaN(n) || !Number.isFinite(n)) {
    return null;
  }
  return n;
}

/** Convert a value to string or null */
function toStringOrNull(val: unknown): string | null {
  if (val === undefined || val === null || val === '') return null;
  return String(val);
}

/** Parse a single row from the Dashboard/Strong Buys sheet into a StockData object */
function parseStockRow(row: Record<string, unknown>): StockData {
  const stock: Record<string, unknown> = {};

  for (const [excelCol, propName] of Object.entries(COLUMN_MAP)) {
    stock[propName] = row[excelCol];
  }

  // Sanitize numeric fields
  for (const field of NUMERIC_STOCK_FIELDS) {
    stock[field] = toNumberOrNull(stock[field]);
  }

  // Sanitize string fields
  stock.ticker = String(stock.ticker || '');
  stock.company = String(stock.company || '');
  stock.sector = String(stock.sector || '');
  stock.rationale = toStringOrNull(stock.rationale);

  // Sanitize enum fields
  const bp = stock.bandPosition;
  stock.bandPosition = (bp === 'Upper Half' || bp === 'Lower Half') ? bp : null;

  const sig = stock.signal;
  const validSignals = ['BUY', 'BUY (Low Confidence)', 'SELL', 'SELL (Low Confidence)', 'HOLD'];
  stock.signal = (typeof sig === 'string' && validSignals.includes(sig)) ? sig : null;

  return stock as unknown as StockData;
}

/** Parse a Sector Summary row */
function parseSectorRow(row: Record<string, unknown>): SectorSummary {
  const result: Record<string, unknown> = {};
  for (const [excelCol, propName] of Object.entries(SECTOR_SUMMARY_MAP)) {
    result[propName] = row[excelCol];
  }
  return {
    sector: String(result.sector || ''),
    stockCount: toNumberOrNull(result.stockCount) ?? 0,
    avgUpsidePercent: toNumberOrNull(result.avgUpsidePercent) ?? 0,
    undervaluedCount: toNumberOrNull(result.undervaluedCount) ?? 0,
    overvaluedCount: toNumberOrNull(result.overvaluedCount) ?? 0,
    avgRSI: toNumberOrNull(result.avgRSI) ?? 0,
  };
}

/** Parse a Data Quality row */
function parseQualityRow(row: Record<string, unknown>): DataQuality {
  const result: Record<string, unknown> = {};
  for (const [excelCol, propName] of Object.entries(DATA_QUALITY_MAP)) {
    result[propName] = row[excelCol];
  }
  const conf = result.confidence;
  const validConf = ['High', 'Medium', 'Low'];
  return {
    ticker: String(result.ticker || ''),
    confidence: (typeof conf === 'string' && validConf.includes(conf))
      ? conf as DataQuality['confidence']
      : 'Low',
    missingFields: toStringOrNull(result.missingFields),
    lastUpdated: toStringOrNull(result.lastUpdated),
    notes: toStringOrNull(result.notes),
  };
}

/** Parse an Assumptions row */
function parseAssumptionRow(row: Record<string, unknown>): Assumption {
  const result: Record<string, unknown> = {};
  for (const [excelCol, propName] of Object.entries(ASSUMPTIONS_MAP)) {
    result[propName] = row[excelCol];
  }
  return {
    parameter: String(result.parameter || ''),
    value: String(result.value ?? ''),
    description: String(result.description || ''),
  };
}

export interface ParsedData {
  dashboard: StockData[];
  strongBuys: StockData[];
  sectorSummary: SectorSummary[];
  dataQuality: DataQuality[];
  assumptions: Assumption[];
}

/** Parse the entire Excel workbook into typed arrays */
export function parseWorkbook(filePath: string): ParsedData {
  const wb = XLSX.readFile(filePath);

  const readSheet = (name: string): Record<string, unknown>[] => {
    const ws = wb.Sheets[name];
    if (!ws) return [];
    return XLSX.utils.sheet_to_json(ws) as Record<string, unknown>[];
  };

  const dashboardRows = readSheet('Dashboard');
  const strongBuyRows = readSheet('Strong Buys');
  const sectorRows = readSheet('Sector Summary');
  const qualityRows = readSheet('Data Quality');
  const assumptionRows = readSheet('Assumptions');

  return {
    dashboard: dashboardRows.map(parseStockRow),
    strongBuys: strongBuyRows.map(parseStockRow),
    sectorSummary: sectorRows.map(parseSectorRow),
    dataQuality: qualityRows.map(parseQualityRow),
    assumptions: assumptionRows.map(parseAssumptionRow),
  };
}
