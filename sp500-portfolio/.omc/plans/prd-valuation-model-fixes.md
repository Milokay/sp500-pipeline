# PRD: Valuation Model Overhaul

## Problem Statement
The current DCF model produces implausible intrinsic values for a significant portion of the S&P 500:
- **400% upside** on FOXA/FOX/DELL (IV cap at 5x is too loose)
- **Negative IVs** on BA (-$102), MRNA (-$120), DOW (-$1) from positive multiples on negative EBITDA
- **Financial mispricing**: Visa IV=$30 (90% "overvalued"), Mastercard IV=$13 (97% "overvalued") because P/B is the wrong lens for asset-light financials
- **Implied growth ignored**: Many stocks have implied perpetuity growth of 6-14% but the model doesn't cap or blend
- **Static sector multiples**: All Tech companies get 20x regardless of quality/margins

If the model says half the S&P 500 is >50% mispriced, the model is wrong.

## Goals
1. Eliminate negative intrinsic values (floor at $0, use EV/Revenue fallback)
2. Cap exit multiples at a realistic 8x-25x range
3. Hard-cap IV when implied perpetuity growth exceeds GDP ceiling (blend methods)
4. Fix financial sector: use DCF for asset-light companies (V, MA, SPGI), ROE-adjusted P/B for banks
5. Blend Exit Multiple and Perpetual Growth IVs weighted by confidence
6. Add analyst target price as a sanity-check anchor
7. Tighten IV cap from 5x to 3x current price

## Non-Goals
- Building a full DDM (Dividend Discount Model) — too complex for this iteration
- Using paid data sources (stick to yfinance)
- Changing signal generation logic (signals.py unchanged)
- Portfolio-level optimization

## Technical Design

### Phase 1: Sanity Guards (config.py + dcf_engine.py)

**File: `config.py`**
- Add `EXIT_MULTIPLE_FLOOR = 8.0` and `EXIT_MULTIPLE_CAP = 25.0`
- Reduce `IV_CAP_MULTIPLIER` from `5.0` to `3.0`
- Add `IV_FLOOR = 0.0` (never return negative IV)
- Add `IMPLIED_GROWTH_BLEND_THRESHOLD = 0.04` (when implied g > this, blend methods)

**File: `modules/dcf_engine.py`**
- In `_resolve_exit_multiple()`: clamp returned multiple to `[EXIT_MULTIPLE_FLOOR, EXIT_MULTIPLE_CAP]`
- After calculating `intrinsic_value`: `intrinsic_value = max(intrinsic_value, config.IV_FLOOR)`
- When `implied_g > MAX_IMPLIED_GROWTH_RATE` AND `iv_perp` is available:
  - Blend: `intrinsic_value = 0.5 * iv_exit + 0.5 * iv_perp` (average both methods)
  - Set confidence to max "Medium" when blending

### Phase 2: Negative EBITDA / Negative FCF Fallback (dcf_engine.py + fundamentals.py)

**File: `modules/fundamentals.py`**
- Add `analyst_target_price` field: `info.get("targetMeanPrice")`
- Add `number_of_analysts` field: `info.get("numberOfAnalystOpinions")`
- Add `forward_revenue_estimate` field: `info.get("revenueEstimate")` or derive from `totalRevenue * (1 + revenueGrowth)`

**File: `modules/dcf_engine.py`**
- When EBITDA is negative or unavailable AND FCF is negative:
  - Use EV/Revenue approach: `terminal_value = revenue_year5 * ev_to_revenue_multiple`
  - `ev_to_revenue_multiple` = company's own `enterpriseToRevenue` from yfinance (capped at 1x-10x)
  - If unavailable, use sector default revenue multiples (new config constant)
- Never return negative intrinsic value — floor at `config.IV_FLOOR`
- When analyst target price is available with >= 5 analysts:
  - Use as additional sanity check: if IV differs by > 3x from analyst target, cap IV at 2x analyst target and set confidence to "Low"

### Phase 3: Financial Sector Reclassification (dcf_engine.py)

**File: `modules/dcf_engine.py`**
- Add `_is_asset_light_financial(fundamentals)` function:
  - Returns True if sector is Financial Services AND ROE > 25% AND P/B > 5
  - Covers: V, MA, PYPL, SPGI, MCO, MSCI, FDS, ICE, COIN, etc.
  - These companies should use standard DCF (not P/B fallback)
- Modify `calculate_dcf()`:
  - If `_is_asset_light_financial()`: skip the P/B fallback, run full DCF
  - For banks/insurance (non-asset-light financials):
    - Use ROE-adjusted fair P/B: `fair_pb = ROE / cost_of_equity`
    - `fair_value = book_value_per_share * fair_pb`
    - This replaces the hard-coded P/B=1.5 assumption
    - Cap fair_pb at range [0.5, 4.0] for safety

### Phase 4: Multi-Method IV Blending (dcf_engine.py)

**File: `modules/dcf_engine.py`**
- After computing `iv_exit` and `iv_perp`, blend based on confidence:
  - If both are available and positive:
    - High confidence: `IV = 0.6 * iv_exit + 0.4 * iv_perp`
    - Medium confidence: `IV = 0.5 * iv_exit + 0.5 * iv_perp`
    - Low confidence: `IV = 0.4 * iv_exit + 0.6 * iv_perp` (lean toward conservative perpetual growth)
  - If analyst target is available (>= 5 analysts), add as third anchor:
    - `IV = weight_exit * iv_exit + weight_perp * iv_perp + 0.2 * analyst_target`
    - Reduce other weights proportionally
  - If only one method available, use that one (current behavior)
- Add `blended_iv` field to result dict for transparency
- Add `iv_method` field: "Exit Multiple Only", "Perpetual Growth Only", "Blended (Exit+Perp)", "Blended (Exit+Perp+Analyst)"

### Phase 5: Tests

**File: `tests/test_dcf.py`**
- `test_exit_multiple_capped_at_25x`: verify multiples > 25 get capped
- `test_exit_multiple_floored_at_8x`: verify multiples < 8 get floored
- `test_negative_iv_floored_at_zero`: verify negative IV becomes 0
- `test_implied_growth_triggers_blending`: verify blending when implied g > 4%
- `test_asset_light_financial_uses_dcf`: verify V/MA-type companies run DCF
- `test_bank_uses_roe_adjusted_pb`: verify banks use ROE/Ke for fair P/B
- `test_negative_ebitda_uses_ev_revenue`: verify EV/Revenue fallback
- `test_analyst_target_sanity_check`: verify IV capped when far from analyst target
- `test_blended_iv_calculation`: verify blending weights
- `test_iv_cap_at_3x_price`: verify tighter cap

## Acceptance Criteria
1. Zero negative intrinsic values across all 503 S&P 500 tickers
2. No stock shows > 300% upside (3x cap)
3. Visa, Mastercard, SPGI use DCF (not P/B fallback) and show reasonable IVs
4. Banks use ROE-adjusted fair P/B (not hard-coded 1.5)
5. BA, MRNA, DOW show positive IVs via EV/Revenue fallback
6. When implied g > 4%, IV is blended (not single-method)
7. Exit multiples are always in [8, 25] range
8. All existing tests still pass
9. At least 10 new tests covering the fixes
10. Spot check: `python main.py --tickers AAPL,V,MA,BA,MRNA,JPM` produces sensible values

## Risk Factors
- **yfinance analyst target**: `targetMeanPrice` may be None for some tickers. Mitigation: analyst anchor is optional, only used when available with >= 5 analysts.
- **Asset-light financial detection**: ROE/P/B thresholds may misclassify some companies. Mitigation: conservative thresholds (ROE > 25% AND P/B > 5) to minimize false positives.
- **Blending weights**: No "correct" weight exists. Mitigation: use equal weights as default, can tune later.
- **EV/Revenue multiples**: Wide variation by sector. Mitigation: use company's own `enterpriseToRevenue` from yfinance, capped at [1, 10].
