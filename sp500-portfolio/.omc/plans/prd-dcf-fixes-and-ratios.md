# PRD: DCF Intrinsic Value Fixes + Financial Ratios Dashboard

## Problem Statement

The current DCF intrinsic value calculations produce unreasonable results in several scenarios:
- BRK-B shows +146,199% upside due to bad P/B data (0.001 from yfinance)
- FOXA/FOX show +1,100% upside because low WACC near growth rate explodes terminal value
- CAG gets WACC ~6% from negative beta, inflating terminal value
- AAPL/MSFT show -70% overvalued — model doesn't capture growth company premiums

Additionally, the Dashboard tab lacks key financial ratios that investors need for quick screening.

## Goals

1. Fix DCF engine to produce reasonable intrinsic values across all sectors
2. Add sector-aware valuation multiples for better peer comparison
3. Add key financial ratios to fundamentals fetcher and Excel Dashboard
4. Maintain all existing unit tests (82 tests must still pass)

## Non-Goals

- Building a completely new valuation model (we improve the existing DCF)
- Adding new data sources beyond yfinance
- Changing the signal matrix logic (signals.py stays the same)

---

## Phase 1: Fix DCF Engine Reasonableness

### 1A. Sanity-check P/B values (fixes BRK-B)
- **Problem**: yfinance returns P/B = 0.001 for BRK-B (actual ~1.5)
- **Fix**: In `_handle_financial_company()` and `_handle_reit()`, reject P/B < 0.05 or > 200
- **Fallback**: When P/B is invalid, set `valuation_status = "Insufficient Data"` and `intrinsic_value = None`
- **Test**: BRK-B should show "Insufficient Data" instead of +146,199% upside

### 1B. Cap intrinsic value relative to price (fixes extreme upsides)
- **Problem**: When WACC - g is small (e.g., 0.01), terminal value = FCF / 0.01 → enormous
- **Fix**: After calculating intrinsic_value, cap it at `max(intrinsic_value, current_price * 5)`
  - If IV > 5x price, set confidence = "Low" and add dcf_note explaining the cap
- **Alternative/additional**: Use exit multiple method (15x FCF) when `(WACC - terminal_growth) < 0.03`
- **Test**: FOXA IV should be capped, no stock should show >400% upside from DCF alone

### 1C. Fix beta floor causing ultra-low WACC (fixes CAG)
- **Problem**: `_cap_beta()` floors at 0.1, giving cost_of_equity = 4.3% + 0.1*5.5% = 4.85%
- **Fix**: Raise beta floor from 0.1 to 0.5 (more realistic minimum)
- **Test**: CAG's WACC should be > 7% with beta floor of 0.5

### 1D. Sector-specific valuation adjustments
- **Problem**: Simple DCF undervalues growth companies (AAPL/MSFT) and overvalues capital-intensive ones
- **Fix**: Apply sector-specific growth rate adjustments in the DCF:
  - Technology: allow higher growth cap (0.20 instead of 0.25) — actually this helps, keep 0.25
  - Utilities/Energy: lower growth cap (0.10)
  - Consumer Staples: lower growth cap (0.12)
- **Note**: This is a mild adjustment, not a complete sector model

### Acceptance Criteria (Phase 1)
- [ ] No stock shows upside > 500% or downside < -95% from DCF
- [ ] BRK-B does NOT show +146,199% upside
- [ ] P/B < 0.05 treated as invalid data
- [ ] Beta floor raised to 0.5
- [ ] Terminal value uses exit multiple when WACC-g spread < 0.03
- [ ] All 24 existing DCF unit tests pass
- [ ] New unit tests for the edge cases above

---

## Phase 2: Add Financial Ratios to Fundamentals Fetcher

### New fields to fetch from yfinance `info` dict:
| Field | yfinance key | Description |
|-------|-------------|-------------|
| ROA | `returnOnAssets` | Return on Assets (decimal, e.g., 0.24) |
| ROE | `returnOnEquity` | Return on Equity (decimal, e.g., 1.52) |
| EPS (trailing) | `trailingEps` | Earnings Per Share (TTM) |
| EPS (forward) | `forwardEps` | Forward EPS estimate |
| EBITDA margin | `ebitdaMargins` | EBITDA / Revenue (decimal) |
| Net margin | `profitMargins` | Net Income / Revenue (decimal) |
| Operating margin | `operatingMargins` | Operating Income / Revenue (decimal) |
| Gross margin | `grossMargins` | Gross Profit / Revenue (decimal) |
| Debt/Equity | `debtToEquity` | Total Debt / Total Equity (ratio) |
| Current ratio | `currentRatio` | Current Assets / Current Liabilities |

### Implementation
- Add these fields to `fetch_fundamentals()` result dict in `fundamentals.py`
- Use `_safe_float()` for all values (handles None/NaN)
- Default to None if not available (some financials don't have EBITDA margins)

### Acceptance Criteria (Phase 2)
- [ ] All 10 new fields fetched and cached properly
- [ ] `_safe_float()` handles all edge cases
- [ ] No existing tests broken

---

## Phase 3: Add Ratios to Excel Dashboard

### New Dashboard columns (after existing 13 columns):
| Column | Source Key | Format | Header |
|--------|-----------|--------|--------|
| 14 | `trailing_pe` | `0.0` | P/E |
| 15 | `price_to_book` | `0.00` | P/B |
| 16 | `trailing_eps` | `$#,##0.00` | EPS |
| 17 | `return_on_assets` | `0.0%` | ROA |
| 18 | `return_on_equity` | `0.0%` | ROE |
| 19 | `ebitda_margin` | `0.0%` | EBITDA% |
| 20 | `net_margin` | `0.0%` | Net Margin% |
| 21 | `debt_to_equity` | `0.0` | D/E |

### Implementation
- Add columns to `_write_dashboard()` in `excel_builder/builder.py`
- Apply appropriate number formats
- Conditional formatting on ROE (green > 15%, red < 5%)
- Handle None values gracefully (show "N/A" or leave blank)

### Acceptance Criteria (Phase 3)
- [ ] Dashboard has 21 columns (13 existing + 8 new ratio columns)
- [ ] All ratio columns have proper number formatting
- [ ] None/missing values displayed as "N/A"
- [ ] Headers are styled consistently with existing columns
- [ ] Frozen pane and auto-filter still work with wider table

---

## Phase 4: Cache Refresh & Full Run Verification

### Steps
1. Clear fundamentals cache (`--refresh` or manual cache clear for fundamentals only)
2. Run full 503-ticker analysis
3. Verify:
   - No extreme upside/downside values in output
   - All ratio columns populated for most tickers
   - Excel report opens correctly with all 21 dashboard columns
   - Signal distribution is reasonable (not all SELL or all BUY)

### Acceptance Criteria (Phase 4)
- [ ] All 82+ unit tests pass
- [ ] Full 503-ticker run completes without errors
- [ ] Excel report has all 5 sheets with proper data
- [ ] No ticker shows > 500% DCF upside
- [ ] Dashboard has all 21 columns with data

---

## Technical Constraints

- Python 3.11+, yfinance, openpyxl, pandas, numpy
- All data from yfinance only (no API keys)
- SQLite cache with 24h expiry
- Must work on Windows 11

## Files to Modify

1. `modules/dcf_engine.py` — Fix IV reasonableness (Phase 1)
2. `modules/fundamentals.py` — Add ratio fields (Phase 2)
3. `excel_builder/builder.py` — Add ratio columns (Phase 3)
4. `tests/test_dcf.py` — Add new edge case tests (Phase 1)
5. `config.py` — Add any new constants (IV cap multiplier, beta floor)
