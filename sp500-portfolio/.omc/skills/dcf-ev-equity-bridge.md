---
id: dcf-ev-equity-bridge
name: DCF EV-to-Equity Bridge Validation
description: Financial model code often omits cash add-back in the Enterprise Value to Equity Value conversion, systematically understating every valuation
source: FPA analyst review of dcf_engine.py — found missing cash in EV-to-equity bridge despite 156 passing tests
triggers:
  - "enterprise value"
  - "equity value"
  - "intrinsic value per share"
  - "ev minus debt"
  - "dcf valuation"
  - "missing cash"
  - "undervalued systematic"
quality: high
---

# DCF EV-to-Equity Bridge Validation

## The Insight

When converting Enterprise Value to Equity Value in code, the cash add-back is the most commonly omitted step. The correct formula is:

```
Equity Value = Enterprise Value - Total Debt + Cash & Equivalents
```

Code implementations frequently write `equity = ev - debt` and forget `+ cash`. This produces a **systematic undervaluation** across every stock in the universe. The error is invisible to unit tests unless you specifically test for it, because the math still "works" — it just produces consistently wrong numbers.

## Why This Matters

For a company like AAPL (~$160B cash, ~$110B debt), omitting cash understates equity value by ~$50B, or ~$3.30/share. For cash-rich tech companies (GOOG ~$100B, META ~$40B), the per-share impact is even larger. The error biases the entire screener toward showing everything as undervalued.

The insidious part: all tests pass, all values are positive and "reasonable-looking," and the model appears to work correctly. Only a domain expert (FPA analyst) reviewing the financial logic — not the code logic — catches it.

## Recognition Pattern

Look for this whenever you see DCF code that:
- Converts from enterprise value to equity value
- Calculates intrinsic value per share from discounted cash flows
- Has a line like `equity = ev - total_debt` without a `+ cash` term
- References `dcf_engine.py` lines 544-546 or similar EV-to-equity bridge

Also watch for these related sign/omission errors in the same codebase:
- Interest expense used without `abs()` (sign varies by data provider)
- Revenue proxy using `market_cap * margin` (circular — market_cap is the output)
- Stale comments after changing constants (e.g., "3x cap" when config says 2x)

## The Approach

When building or reviewing any DCF model in code:

1. **Audit the EV-to-equity bridge explicitly.** Check for: `-debt`, `+cash`, `-minority_interest`, `-preferred_stock`. The first two are critical; the last two are nice-to-have for S&P 500.

2. **Use FPA analyst review for financial logic.** Code-level tests verify math correctness, not financial correctness. A model can pass 200 tests and still have a systematic $50B error per company. Route the DCF engine through `fpa-analyst` (opus) after implementation.

3. **Test for cash impact specifically.** Write a test like:
   ```python
   def test_cash_increases_iv():
       base = _make_fundamentals(total_cash=0)
       with_cash = _make_fundamentals(total_cash=50_000_000_000)
       iv_base = calculate_dcf(base)["intrinsic_value"]
       iv_cash = calculate_dcf(with_cash)["intrinsic_value"]
       assert iv_cash > iv_base  # Cash should increase equity value
   ```

4. **Check interest expense sign convention.** yfinance uses negative values (expense). Other providers may use positive. Always `abs()` before dividing by total_debt, and add sanity bounds (1%-15%).

## Example

```python
# WRONG (missing cash):
ev = pv_fcfs + pv_terminal
equity = ev - total_debt
iv = equity / shares

# CORRECT:
ev = pv_fcfs + pv_terminal
cash = fundamentals.get("total_cash", 0) or 0
equity = ev - total_debt + cash
iv = equity / shares
```

The `total_cash` field needs to be fetched in `fundamentals.py` from yfinance's `info.get("totalCash")` or balance sheet.
