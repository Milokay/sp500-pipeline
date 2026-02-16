# PRD: Fix Intrinsic Value — Switch to Exit Multiple Method

## Problem Statement

The current DCF engine in `modules/dcf_engine.py` uses the **Perpetual Growth (Gordon Growth) Model** as its primary terminal value method. This approach is highly sensitive to the growth rate (`g`) and discount rate (`WACC`), where tiny changes (e.g., 2% to 2.5% in `g`) cause massive swings in intrinsic value. The result: intrinsic values that frequently diverge wildly from market prices, triggering unreliable buy/sell signals.

The Exit Multiple Method is only used as a **last-resort fallback** when `WACC - g < 0.03`, with a **hardcoded 15x FCF multiple** that ignores sector differences entirely.

### Current Behavior (dcf_engine.py:282-293)
```python
# Uses exit multiple ONLY when WACC-g spread is thin
if (wacc - config.TERMINAL_GROWTH_RATE) < config.MIN_WACC_G_SPREAD:
    terminal_value = fcf_year5 * 15  # Hardcoded, no sector awareness
else:
    terminal_value = fcf_year5 * (1 + config.TERMINAL_GROWTH_RATE) / (wacc - config.TERMINAL_GROWTH_RATE)
```

### Why This Is Wrong
1. **Perpetual Growth is too sensitive**: A 0.5% change in `g` can swing terminal value by 30-50%
2. **Exit Multiple fallback is naive**: 15x FCF for all sectors is wrong (software trades at 20x+ EBITDA, utilities at 8x)
3. **No dual-method bracketing**: Professional analysts calculate BOTH methods and cross-validate
4. **No sanity check**: No implied perpetuity growth rate validation
5. **Uses FCF multiple, not EV/EBITDA**: Industry standard for exit multiples is EV/EBITDA

## Goals

1. **Switch primary terminal value to Exit Multiple Method** using sector-specific EV/EBITDA multiples
2. **Keep Perpetual Growth as secondary/sanity check** — calculate both, report both
3. **Add Implied Perpetuity Growth Rate** sanity check (flag when implied `g` > GDP growth)
4. **Use actual sector peer median EV/EBITDA** when available (data already exists via `relative_valuation.py` and `fundamentals.py:ev_to_ebitda`)
5. **Fall back to sector default multiples** when peer data is insufficient
6. **Update Excel report** to show both methods and the sanity check
7. **Update tests** to validate the new dual-method approach

## Non-Goals

- No changes to the WACC calculation logic (Steps 1-4 of DCF)
- No changes to FCF projection logic (growth decay model)
- No changes to the signal generation matrix in `signals.py`
- No changes to relative valuation module (it already works correctly)
- No changes to data fetching in `fundamentals.py` (ev_to_ebitda already fetched)
- No new API calls or data sources

## Technical Constraints

- **Data available**: `ev_to_ebitda` is already fetched per-ticker in `fundamentals.py:119`
- **Sector peer medians**: Already computed in `relative_valuation.py` — can be passed to DCF or recomputed
- **yfinance limitation**: Some tickers may have `ev_to_ebitda = None`
- **Python 3.10+**: Type hints used throughout
- **Existing tests**: 25+ tests in `tests/test_dcf.py` must continue passing (with updates)

## Data Flow

```
fundamentals.py (fetches ev_to_ebitda per ticker)
       |
       v
main.py (calculates all_relative valuations, then calls calculate_dcf per ticker)
       |
       v  [CHANGE: pass sector_ev_ebitda_median into calculate_dcf]
dcf_engine.py (uses Exit Multiple as primary terminal value)
       |
       v
signals.py (unchanged — still uses intrinsic_value, upside_pct)
       |
       v
builder.py (updated — show both methods + sanity check)
```

## Implementation Phases

### Phase 1: Config Updates (`config.py`)

Add sector-specific default EV/EBITDA exit multiples as a fallback table:

```python
# Sector default EV/EBITDA exit multiples (used when peer median unavailable)
SECTOR_EXIT_MULTIPLES = {
    "Technology": 20.0,
    "Information Technology": 20.0,
    "Communication Services": 14.0,
    "Healthcare": 15.0,
    "Consumer Discretionary": 14.0,
    "Consumer Cyclical": 14.0,
    "Consumer Staples": 14.0,
    "Consumer Defensive": 14.0,
    "Industrials": 12.0,
    "Materials": 10.0,
    "Basic Materials": 10.0,
    "Energy": 8.0,
    "Utilities": 10.0,
    "Real Estate": 16.0,  # Rarely used (REITs skip DCF)
    "Financial Services": 10.0,  # Rarely used (financials skip DCF)
    "Financials": 10.0,
}
DEFAULT_EXIT_MULTIPLE = 12.0  # Fallback for unknown sectors

# GDP growth ceiling for implied perpetuity growth sanity check
MAX_IMPLIED_GROWTH_RATE = 0.04  # 4% — flag if implied g exceeds this
```

### Phase 2: DCF Engine Updates (`modules/dcf_engine.py`)

**Change function signature:**
```python
def calculate_dcf(fundamentals: dict, sector_ev_ebitda_median: float = None) -> dict:
```

**Replace Step 5 (Terminal Value) with dual-method approach:**

1. **Exit Multiple Method (PRIMARY)**:
   - Use `sector_ev_ebitda_median` if available (from relative_valuation peer data)
   - Else use ticker's own `ev_to_ebitda` from fundamentals
   - Else fall back to `config.SECTOR_EXIT_MULTIPLES[sector]`
   - Else fall back to `config.DEFAULT_EXIT_MULTIPLE`
   - `terminal_value_exit = fcf_year5 * exit_multiple`

2. **Perpetual Growth Method (SECONDARY/SANITY CHECK)**:
   - Keep existing Gordon Growth calculation
   - `terminal_value_perp = fcf_year5 * (1 + g) / (WACC - g)`
   - Only calculate if `(WACC - g) >= MIN_WACC_G_SPREAD`, else set to None

3. **Implied Perpetuity Growth Rate**:
   - `implied_g = WACC - (fcf_year5 / terminal_value_exit)`
   - Flag if `implied_g > MAX_IMPLIED_GROWTH_RATE`

4. **Use Exit Multiple terminal value** for the enterprise value calculation

**New output fields added to return dict:**
```python
{
    # Existing fields (updated values)
    "intrinsic_value": ...,       # Now based on Exit Multiple method
    "terminal_method": "Exit Multiple",  # Which method was used

    # New fields
    "exit_multiple_used": 15.2,   # The actual EV/EBITDA multiple used
    "exit_multiple_source": "Sector Peer Median",  # or "Ticker EV/EBITDA", "Sector Default", "Global Default"
    "iv_exit_multiple": 185.50,   # Intrinsic value via Exit Multiple
    "iv_perpetual_growth": 210.30,  # Intrinsic value via Perpetual Growth (or None)
    "implied_perpetuity_growth": 0.035,  # Implied g from exit multiple
    "valuation_warning": None,    # or "Implied growth rate (5.2%) exceeds GDP growth ceiling (4%)"
}
```

### Phase 3: Main Orchestrator Update (`main.py`)

Pass sector median EV/EBITDA into `calculate_dcf`:

```python
# After calculating all_relative, extract sector medians
sector_medians = _compute_sector_ev_ebitda_medians(all_fundamentals)

# In the per-ticker loop:
sector = fund.get('sector', 'Unknown')
sector_median = sector_medians.get(sector)
dcf = calculate_dcf(fund, sector_ev_ebitda_median=sector_median)
```

Add helper function `_compute_sector_ev_ebitda_medians()` to compute median EV/EBITDA per sector from all_fundamentals.

### Phase 4: Excel Report Updates (`excel_builder/builder.py`)

**Dashboard sheet**: Add columns after "Intrinsic Value":
- "IV (Exit Multiple)" — `iv_exit_multiple`
- "IV (Perp Growth)" — `iv_perpetual_growth`
- "Exit Multiple" — `exit_multiple_used`
- "Implied g" — `implied_perpetuity_growth`

**Assumptions sheet**: Add new rows:
- "Terminal Value Method" = "Exit Multiple (Primary)"
- "Default Exit Multiple" = config value
- "Max Implied Growth Rate" = config value
- Sector exit multiples table

**Data Quality sheet**: Show `valuation_warning` in Notes column.

### Phase 5: Test Updates (`tests/test_dcf.py`)

1. **Update existing tests**: Add assertions for new output fields
2. **New test class `TestExitMultipleMethod`**:
   - Test exit multiple is used as primary terminal value
   - Test sector_ev_ebitda_median parameter is respected
   - Test fallback chain: peer median -> ticker EV/EBITDA -> sector default -> global default
   - Test implied perpetuity growth rate calculation
   - Test valuation warning when implied g exceeds ceiling
3. **New test class `TestDualMethodBracketing`**:
   - Test both IV values are returned
   - Test perpetual growth returns None when WACC-g spread is too thin
   - Test exit multiple IV and perpetual growth IV are in reasonable range of each other

## Acceptance Criteria

- [ ] **AC1**: `calculate_dcf()` uses Exit Multiple as primary terminal value method
- [ ] **AC2**: Sector-specific EV/EBITDA multiples are used (not hardcoded 15x)
- [ ] **AC3**: Both `iv_exit_multiple` and `iv_perpetual_growth` are returned in results
- [ ] **AC4**: Implied perpetuity growth rate is calculated and returned
- [ ] **AC5**: Warning is generated when implied g > 4% (GDP ceiling)
- [ ] **AC6**: Exit multiple source chain works: peer median > ticker EV/EBITDA > sector default > global default
- [ ] **AC7**: All existing tests pass (updated for new fields)
- [ ] **AC8**: New tests cover exit multiple logic, fallback chain, and sanity checks
- [ ] **AC9**: Excel report shows both IV methods and implied growth rate
- [ ] **AC10**: `python main.py --tickers AAPL,MSFT,JPM` runs successfully with new logic
- [ ] **AC11**: Intrinsic values are closer to market prices than before (spot-check 5-10 tickers)

## Files Modified

| File | Change Type | Description |
|------|------------|-------------|
| `config.py` | Add | Sector exit multiples table, MAX_IMPLIED_GROWTH_RATE |
| `modules/dcf_engine.py` | Modify | Dual-method terminal value, Exit Multiple primary |
| `main.py` | Modify | Compute sector medians, pass to calculate_dcf |
| `excel_builder/builder.py` | Modify | New columns for dual IV + implied g |
| `tests/test_dcf.py` | Modify | Update existing + add new test classes |

## Risk & Mitigation

| Risk | Mitigation |
|------|-----------|
| Some tickers have no EV/EBITDA data | Fallback chain ensures a multiple is always available |
| Sector medians skewed by outliers | Use median (not mean); already robust |
| Exit multiple may reflect market bubbles | Perpetual Growth as sanity check catches this |
| Breaking existing tests | Update test assertions before changing engine |

## Next Steps

After PRD approval, execute with:
```
/oh-my-claudecode:ralph "Implement the intrinsic value exit multiple PRD"
```
