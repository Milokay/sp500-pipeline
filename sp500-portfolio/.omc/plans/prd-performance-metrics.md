# PRD: Portfolio Performance Metrics

## Problem Statement
The S&P 500 portfolio tool currently lacks key risk/return metrics that investors use for portfolio construction: Sharpe ratio, volatility (standard deviation), and multi-period returns. Without these, users cannot assess risk-adjusted performance or compare historical returns across time horizons.

## Goals
- Add 52-week Sharpe Ratio and Standard Deviation (annualized) per ticker
- Add return % for 1 month, 6 months, 1 year, and 3 years per ticker
- Display all 6 new metrics as columns on the Dashboard and Strong Buys Excel sheets
- Maintain backward compatibility — no changes to existing signals or DCF logic

## Non-Goals
- Portfolio-level Sharpe (this is per-stock)
- Sortino ratio, max drawdown, or other advanced risk metrics (future work)
- Changing the signal generation logic based on these new metrics

## Technical Design

### Data Flow
```
price_data.py (extend to 3y) → technicals.py (new calculate_performance_metrics) → main.py (merge) → builder.py (new columns)
```

### Phase 1: Extend Price Data Window
**File: `modules/price_data.py`**
- Change default `period` from `"1y"` to `"3y"` in both `fetch_price_history()` and `fetch_price_history_bulk()`
- This provides enough data for 3-year returns and 52-week calculations
- Bollinger/RSI still use only recent data (unchanged)

### Phase 2: New Performance Metrics Function
**File: `modules/technicals.py`**
- Add `calculate_performance_metrics(price_df: pd.DataFrame) -> dict`
- Calculations:
  - **Return periods**: Simple price return = (current - past) / past
    - `return_1m`: ~21 trading days ago
    - `return_6m`: ~126 trading days ago
    - `return_1y`: ~252 trading days ago
    - `return_3y`: ~756 trading days ago
  - **Std Dev (52-week)**: Annualized standard deviation of daily returns over last 252 trading days
    - `std_dev = daily_returns[-252:].std() * sqrt(252)`
  - **Sharpe Ratio (52-week)**: Risk-adjusted return over last 252 trading days
    - `annual_return = (price_now / price_252d_ago) - 1`
    - `sharpe = (annual_return - risk_free_rate) / std_dev`
    - Use `config.RISK_FREE_RATE` (currently 4.3%)
- Edge cases:
  - If insufficient data for a period, return `None` for that metric
  - If std_dev is 0, return `None` for Sharpe
- Integrate into `calculate_technicals()` by merging performance metrics dict

### Phase 3: Wire Into Main Pipeline
**File: `main.py`**
- No changes needed — `calculate_technicals()` already returns a merged dict
- The `tech_` prefix applied in main.py will automatically create `tech_return_1m`, `tech_sharpe_52w`, etc.

### Phase 4: Add Excel Columns
**File: `excel_builder/builder.py`**
- Add 6 new columns to Dashboard and Strong Buys headers (after existing columns):
  - `Return 1M` (format: `0.0%`)
  - `Return 6M` (format: `0.0%`)
  - `Return 1Y` (format: `0.0%`)
  - `Return 3Y` (format: `0.0%`)
  - `Std Dev 52W` (format: `0.0%`)
  - `Sharpe 52W` (format: `0.00`)
- Add conditional formatting on Sharpe column:
  - Green: > 1.0 (good risk-adjusted return)
  - Red: < 0 (negative risk-adjusted return)

### Phase 5: Tests
**File: `tests/test_technicals.py`**
- Add `TestPerformanceMetrics` class:
  - `test_returns_with_sufficient_data`: verify all 4 return periods
  - `test_return_3y_none_with_1y_data`: verify graceful degradation
  - `test_sharpe_positive_with_gains`: verify positive Sharpe when returns > Rf
  - `test_sharpe_negative_with_losses`: verify negative Sharpe when returns < Rf
  - `test_std_dev_zero_for_constant_price`: verify std_dev ≈ 0
  - `test_std_dev_none_with_insufficient_data`: verify None when < 252 rows
  - `test_integration_with_calculate_technicals`: verify keys present in combined result

## Acceptance Criteria
1. `calculate_performance_metrics()` returns correct return % for all 4 periods
2. Sharpe ratio matches manual calculation: `(annualized_return - Rf) / annualized_std`
3. Std Dev is annualized (`daily_std * sqrt(252)`)
4. Missing data periods return `None` (not errors)
5. All 6 columns appear in Dashboard and Strong Buys sheets
6. All existing 110 tests still pass
7. New tests cover all edge cases (at least 7 new tests)
8. Spot check: `python main.py --tickers AAPL,MSFT,JPM` runs successfully with new columns populated

## Risk Factors
- **3-year price data**: yfinance `period="3y"` may be slow for 500 tickers in bulk mode. Mitigation: bulk download already uses threads.
- **Cache invalidation**: Old 1y cached data won't have 3y history. Mitigation: Users use `--refresh` flag or cache naturally expires after 24h.
