/**
 * Build-time script: reads the Excel workbook and writes typed JSON files to src/data/.
 * Run via: node scripts/generate-data.mjs
 * Automatically runs before `next build` via the "prebuild" npm script.
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import XLSX from 'xlsx';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const ROOT = join(__dirname, '..');

// Find the Excel file: prefer generic name (from pipeline), fall back to latest timestamped
function findExcelFile() {
  const dataDir = join(ROOT, 'data');
  // 1. Generic name (copied by run-pipeline)
  const generic = join(dataDir, 'sp500_analysis.xlsx');
  if (existsSync(generic)) return generic;
  // 2. Latest timestamped file
  const files = readdirSync(dataDir)
    .filter(f => f.startsWith('sp500_analysis_') && f.endsWith('.xlsx'))
    .sort()
    .reverse();
  if (files.length > 0) return join(dataDir, files[0]);
  throw new Error('No sp500_analysis*.xlsx found in data/ directory');
}

const EXCEL_PATH = findExcelFile();
console.log(`Using Excel file: ${EXCEL_PATH}`);
const OUTPUT_DIR = join(ROOT, 'src', 'data');

// ---------------------------------------------------------------------------
// Column maps (mirrored from src/types/stock.ts to avoid TS compilation)
// ---------------------------------------------------------------------------
const COLUMN_MAP = {
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

const NUMERIC_STOCK_FIELDS = new Set([
  'price', 'intrinsicValue', 'upsidePercent', 'lowerBand', 'upperBand',
  'rsi', 'conviction', 'pe', 'pb', 'eps', 'roa', 'roe',
  'ebitdaPercent', 'netMarginPercent', 'de', 'ivExitMult', 'ivPerpGrowth',
  'exitMultiple', 'impliedG', 'return1M', 'return6M', 'return1Y', 'return3Y',
  'stdDev52W', 'sharpe52W', 'buyPrice',
]);

const SECTOR_SUMMARY_MAP = {
  'Sector': 'sector',
  '# Stocks': 'stockCount',
  'Avg Upside %': 'avgUpsidePercent',
  '# Undervalued': 'undervaluedCount',
  '# Overvalued': 'overvaluedCount',
  'Avg RSI': 'avgRSI',
};

const DATA_QUALITY_MAP = {
  'Ticker': 'ticker',
  'Confidence': 'confidence',
  'Missing Fields': 'missingFields',
  'Last Updated': 'lastUpdated',
  'Notes': 'notes',
};

const ASSUMPTIONS_MAP = {
  'Parameter': 'parameter',
  'Value': 'value',
  'Description': 'description',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function toNumberOrNull(val) {
  if (val === undefined || val === null || val === '' || val === 'N/A' || val === 'n/a') return null;
  const n = typeof val === 'number' ? val : Number(val);
  if (Number.isNaN(n) || !Number.isFinite(n)) return null;
  return n;
}

function toStringOrNull(val) {
  if (val === undefined || val === null || val === '') return null;
  return String(val);
}

function parseStockRow(row) {
  const stock = {};
  for (const [excelCol, propName] of Object.entries(COLUMN_MAP)) {
    stock[propName] = row[excelCol];
  }
  for (const field of NUMERIC_STOCK_FIELDS) {
    stock[field] = toNumberOrNull(stock[field]);
  }
  stock.ticker = String(stock.ticker || '');
  stock.company = String(stock.company || '');
  stock.sector = String(stock.sector || '');
  stock.rationale = toStringOrNull(stock.rationale);

  const bp = stock.bandPosition;
  stock.bandPosition = (bp === 'Upper Half' || bp === 'Lower Half') ? bp : null;

  const sig = stock.signal;
  const validSignals = ['BUY', 'BUY (Low Confidence)', 'SELL', 'SELL (Low Confidence)', 'HOLD'];
  stock.signal = (typeof sig === 'string' && validSignals.includes(sig)) ? sig : null;

  return stock;
}

function parseSectorRow(row) {
  const r = {};
  for (const [excelCol, propName] of Object.entries(SECTOR_SUMMARY_MAP)) {
    r[propName] = row[excelCol];
  }
  return {
    sector: String(r.sector || ''),
    stockCount: toNumberOrNull(r.stockCount) ?? 0,
    avgUpsidePercent: toNumberOrNull(r.avgUpsidePercent) ?? 0,
    undervaluedCount: toNumberOrNull(r.undervaluedCount) ?? 0,
    overvaluedCount: toNumberOrNull(r.overvaluedCount) ?? 0,
    avgRSI: toNumberOrNull(r.avgRSI) ?? 0,
  };
}

function parseQualityRow(row) {
  const r = {};
  for (const [excelCol, propName] of Object.entries(DATA_QUALITY_MAP)) {
    r[propName] = row[excelCol];
  }
  const conf = r.confidence;
  const validConf = ['High', 'Medium', 'Low'];
  return {
    ticker: String(r.ticker || ''),
    confidence: (typeof conf === 'string' && validConf.includes(conf)) ? conf : 'Low',
    missingFields: toStringOrNull(r.missingFields),
    lastUpdated: toStringOrNull(r.lastUpdated),
    notes: toStringOrNull(r.notes),
  };
}

function parseAssumptionRow(row) {
  const r = {};
  for (const [excelCol, propName] of Object.entries(ASSUMPTIONS_MAP)) {
    r[propName] = row[excelCol];
  }
  return {
    parameter: String(r.parameter || ''),
    value: String(r.value ?? ''),
    description: String(r.description || ''),
  };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main() {
  console.log('[generate-data] Reading Excel file...');
  if (!existsSync(EXCEL_PATH)) {
    console.error(`[generate-data] ERROR: Excel file not found at ${EXCEL_PATH}`);
    process.exit(1);
  }

  const buf = readFileSync(EXCEL_PATH);
  const wb = XLSX.read(buf);
  console.log(`[generate-data] Sheets found: ${wb.SheetNames.join(', ')}`);

  const readSheet = (name) => {
    const ws = wb.Sheets[name];
    if (!ws) {
      console.warn(`[generate-data] WARNING: Sheet "${name}" not found`);
      return [];
    }
    return XLSX.utils.sheet_to_json(ws);
  };

  const dashboard = readSheet('Dashboard').map(parseStockRow);
  const strongBuys = readSheet('Strong Buys').map(parseStockRow);
  const sectorSummary = readSheet('Sector Summary').map(parseSectorRow);
  const dataQuality = readSheet('Data Quality').map(parseQualityRow);
  const assumptions = readSheet('Assumptions').map(parseAssumptionRow);

  // Validate: count nulls to make sure NaN handling is working
  let nanCount = 0;
  for (const stock of dashboard) {
    for (const val of Object.values(stock)) {
      if (typeof val === 'number' && Number.isNaN(val)) {
        nanCount++;
      }
    }
  }
  if (nanCount > 0) {
    console.error(`[generate-data] ERROR: Found ${nanCount} NaN values in dashboard data!`);
    process.exit(1);
  }

  // Write JSON files
  if (!existsSync(OUTPUT_DIR)) {
    mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  const files = {
    'dashboard.json': dashboard,
    'strongBuys.json': strongBuys,
    'sectorSummary.json': sectorSummary,
    'dataQuality.json': dataQuality,
    'assumptions.json': assumptions,
  };

  for (const [filename, data] of Object.entries(files)) {
    const path = join(OUTPUT_DIR, filename);
    writeFileSync(path, JSON.stringify(data, null, 2));
    console.log(`[generate-data] Wrote ${filename} (${Array.isArray(data) ? data.length : 0} records)`);
  }

  console.log('[generate-data] Done!');
}

main();
