# IV Fixes Round 2 — Implementation Plan (v2, post-review)

**Date:** 2026-02-15
**Scope:** 5 code changes + 1 data enhancement across 4 files
**Estimated complexity:** MEDIUM
**Baseline:** 141 tests passing, all Round 1 PRD fixes shipped
**Review status:** Architect APPROVED WITH CONCERNS, Critic REJECTED v1 — all feedback addressed in v2

---

## Context

The user reviewed the latest Excel output and identified remaining IV issues. After codebase analysis, 1 of the original 5 user-requested fixes is already implemented (company-specific WACC). The remaining work is config changes, an earnings-quality filter, a sector-specific valuation layer, and Excel column additions.

### What Already Works (No Changes Needed)

- **Company-specific WACC** (Fix 1): Fully implemented at `dcf_engine.py:412-432`. Uses beta via CAPM, interest_expense/total_debt for cost of debt, market-cap-weighted WACC. Capped [6%, 20%]. No action required.

### Design Decisions (Resolved)

1. **Margin of Safety on IV:** IV stays as raw fair value. A new "Buy Price" column (IV * 0.75) is added to Excel output. This preserves academic IV semantics while giving the user a visible conservative target.

2. **EXIT_MULTIPLE_FLOOR for Airlines:** Use `INDUSTRY_EXIT_MULTIPLE_FLOORS` config dict for per-industry clamping. Global floor stays at 8x. Airlines get 6x floor via industry-specific override.

3. **Tech P/E blend and Energy normalized DCF:** Deferred to Round 3.

---

## Guardrails

### Must Have
- All 141 existing tests continue to pass
- IV remains the raw fair value estimate (no margin of safety baked in)
- Changes are backward-compatible with existing data pipeline and cache
- Every new code path has at least 1 test

### Must NOT Have
- No changes to `fundamentals.py` fetch logic beyond adding `industry` field
- No changes to `signals.py` signal matrix logic
- No new external dependencies
- No architecture changes (no new files, no class hierarchies)
- No WACC column in Excel (scope creep — only Buy Price)

### Cache Compatibility Note
Existing cached fundamentals data will lack the new `industry` field. `fundamentals.get("industry", "")` defaults safely to empty string, so all industry overrides silently skip. Users should clear cache or wait 24h for natural expiry to get full industry-specific treatment.

---

## Task Flow

```
Task 1 (config.py) ─────────────────────────────────┐
Task 2 (fundamentals.py) ───────────────────────────┤
Task 3 (dcf_engine.py: unified rewrite) ────────────┤
Task 4 (excel_builder/builder.py) ──────────────────┤
Task 5 (tests/test_dcf.py) ────────────────────────-┘
```

Tasks 1+2 are independent config/data changes. Task 3 is the core engine rewrite (merges old Tasks 2+3+4). Task 4 is the Excel column addition. Task 5 validates everything.

---

## Detailed TODOs

### Task 1: Config Changes

**File:** `config.py`

**Changes:**
```python
# Change existing:
IV_CAP_MULTIPLIER = 2.0              # Was 3.0 — max upside now 100%

# Add new constants:
MIN_EBITDA_MARGIN_FOR_DCF = 0.02     # Below 2%, force Low confidence

# Industry WACC floors (applied AFTER company-specific WACC calc)
INDUSTRY_WACC_FLOORS = {
    "Biotechnology": 0.12,
    "Drug Manufacturers - Specialty & Generic": 0.10,
    "Airlines": 0.14,
    "Travel Services": 0.12,
    "Oil & Gas E&P": 0.11,
    "Oil & Gas Midstream": 0.09,
}

# Industry exit multiple defaults (blended 50/50 with ticker's own when available)
INDUSTRY_EXIT_MULTIPLES = {
    "Aerospace & Defense": 15.0,
    "Airlines": 6.0,
    "Biotechnology": 12.0,
}

# Industry-specific exit multiple FLOORS (override global EXIT_MULTIPLE_FLOOR)
INDUSTRY_EXIT_MULTIPLE_FLOORS = {
    "Airlines": 6.0,          # Allow 6x for airlines (global floor is 8x)
}

# Industry revenue multiples (for negative-EBITDA fallback)
INDUSTRY_REVENUE_MULTIPLES = {
    "Biotechnology": 6.0,
    "Drug Manufacturers - Specialty & Generic": 4.0,
}
```

**Acceptance Criteria:**
- `config.IV_CAP_MULTIPLIER == 2.0`
- All 4 new dicts defined
- `MIN_EBITDA_MARGIN_FOR_DCF == 0.02`

**Effort:** Trivial

---

### Task 2: Add `industry` field to fundamentals.py

**File:** `modules/fundamentals.py`

**Changes:**
Add `"industry": None` to the result dict default (line 71 area), and fetch it:
```python
result["industry"] = info.get("industry", "Unknown")
```

**Acceptance Criteria:**
- `fetch_fundamentals("AAPL")["industry"]` returns a non-None string
- Old cached data returns `None` for industry (backward-compatible)

**Effort:** Trivial

---

### Task 3: DCF Engine Changes (unified rewrite)

**File:** `modules/dcf_engine.py`

This task combines the exit multiple blend, earnings filter, and industry overrides into a single coherent set of changes. Architect and Critic both required merging these to avoid dead code paths.

#### 3A: Rewrite `_resolve_exit_multiple()` — unified fallback chain

Replace the entire function body with this 5-branch structure:

```
_resolve_exit_multiple(fundamentals, sector_ev_ebitda_median=None):
  sector = fundamentals.get("sector", "")
  industry = fundamentals.get("industry", "")

  # Determine industry-specific floor (or use global)
  floor = INDUSTRY_EXIT_MULTIPLE_FLOORS.get(industry, EXIT_MULTIPLE_FLOOR)

  # Helper to clamp
  def clamp(val):
      return max(floor, min(val, EXIT_MULTIPLE_CAP))

  # 1. Sector peer median (best signal — live data)
  if sector_ev_ebitda_median is not None and sector_ev_ebitda_median > 0:
      return (clamp(sector_ev_ebitda_median), "Sector Peer Median")

  # 2. Ticker's own EV/EBITDA available?
  ticker_ev = fundamentals.get("ev_to_ebitda")
  ticker_valid = ticker_ev is not None and 1.0 < ticker_ev < 100.0

  if ticker_valid:
      # Find best reference to blend with: industry > sector > none
      industry_default = INDUSTRY_EXIT_MULTIPLES.get(industry)
      sector_default = SECTOR_EXIT_MULTIPLES.get(sector)

      if industry_default is not None:
          blended = (ticker_ev + industry_default) / 2
          return (clamp(blended), "Blended (Ticker + Industry)")
      elif sector_default is not None:
          blended = (ticker_ev + sector_default) / 2
          return (clamp(blended), "Blended (Ticker + Sector)")
      else:
          return (clamp(ticker_ev), "Ticker EV/EBITDA")

  # 3. No ticker data — use best available default
  industry_default = INDUSTRY_EXIT_MULTIPLES.get(industry)
  if industry_default is not None:
      return (clamp(industry_default), "Industry Default")

  sector_default = SECTOR_EXIT_MULTIPLES.get(sector)
  if sector_default is not None:
      return (clamp(sector_default), "Sector Default")

  # 4. Global default
  return (DEFAULT_EXIT_MULTIPLE, "Global Default")
```

**Key change from v1:** Uses `INDUSTRY_EXIT_MULTIPLE_FLOORS` for per-industry clamping. Airlines get floor=6x while everything else gets floor=8x.

#### 3B: Update `_resolve_revenue_multiple()` — industry lookup

Add industry check before sector check:
```python
industry = fundamentals.get("industry", "")

# 1. Company's own EV/Revenue (unchanged)
# 2. Industry-specific revenue multiple (NEW)
industry_rev = INDUSTRY_REVENUE_MULTIPLES.get(industry)
if industry_rev is not None:
    return (industry_rev, "Industry Revenue Default")
# 3. Sector default (unchanged)
# 4. Global default (unchanged)
```

#### 3C: Add earnings-quality filter in `calculate_dcf()`

Insert after shares_outstanding validation, before FCF processing:
```python
# --- Earnings quality check ---
earnings_quality_note = None
force_low_confidence = False
trailing_eps = fundamentals.get("trailing_eps")
ebitda_margin_val = fundamentals.get("ebitda_margin")

if trailing_eps is not None and trailing_eps < 0:
    force_low_confidence = True
    earnings_quality_note = f"Negative trailing EPS (${trailing_eps:.2f})"
elif (ebitda_margin_val is not None and ebitda_margin_val > 0
      and ebitda_margin_val < config.MIN_EBITDA_MARGIN_FOR_DCF):
    force_low_confidence = True
    earnings_quality_note = f"Thin EBITDA margin ({ebitda_margin_val:.1%})"
```

After confidence is determined:
```python
if force_low_confidence:
    confidence = "Low"
```

At the end, if `earnings_quality_note` and `dcf_note is None`:
```python
dcf_note = earnings_quality_note
```

#### 3D: Add industry WACC floor in `calculate_dcf()`

After existing WACC calculation (line 432):
```python
# Apply industry-specific WACC floor
industry = fundamentals.get("industry", "")
industry_wacc_floor = config.INDUSTRY_WACC_FLOORS.get(industry)
if industry_wacc_floor is not None:
    wacc = max(wacc, industry_wacc_floor)
wacc = max(0.06, min(wacc, 0.20))  # Re-apply global bounds
```

**Acceptance Criteria:**
- Exit multiple blend: ticker=22, sector=20 (Tech) -> result=21, source="Blended (Ticker + Sector)"
- Exit multiple blend: ticker=22, industry="Airlines" -> blend with 6.0 -> result=14, source="Blended (Ticker + Industry)"
- Airlines with no ticker EV/EBITDA: result=6.0, source="Industry Default" (floor=6x allows this)
- Airlines WACC >= 14%
- Biotech WACC >= 12%
- Defense exit multiple ~15x
- Biotech negative EBITDA uses 6x Revenue
- Negative EPS -> confidence="Low"
- EBITDA margin 1% -> confidence="Low"
- Normal tech stock unaffected
- All new `exit_multiple_source` values: "Blended (Ticker + Industry)", "Blended (Ticker + Sector)", "Industry Default", "Industry Revenue Default"

**Effort:** Medium

---

### Task 4: Add Buy Price Column to Excel

**File:** `excel_builder/builder.py`

**Approach:** Add "Buy Price" as the LAST column in both Dashboard and Strong Buys sheets. This avoids shifting 50+ hardcoded column indices (architect recommendation). The user can reorder columns in Excel.

**Changes:**
- Append `'Buy Price'` to the `headers` list in `_build_dashboard_sheet`
- Add cell-writing logic for `buy_price` with `$#,##0.00` format at the new last column
- Repeat for `_build_strong_buys_sheet`
- No conditional formatting changes needed (new column at end)

**Acceptance Criteria:**
- "Buy Price" column appears as last column in Dashboard sheet
- "Buy Price" column appears as last column in Strong Buys sheet
- Values = IV * 0.75, formatted as currency
- All other columns unchanged (no index shifting)
- Existing conditional formatting intact

**Effort:** Small (append-only, no index changes)

---

### Task 5: Update and Add Tests

**File:** `tests/test_dcf.py`

#### Test fixture update
Add `"industry": None` to `_make_fundamentals()` default dict. This makes the fixture explicitly forward-compatible.

#### Tests to update (4):
1. `test_iv_cap_at_3x_price` -> rename to `test_iv_cap_at_2x_price`, change literal `3.0` to `2.0`
2. `test_no_extreme_upside` -> max upside from `<= 2.0` to `<= 1.0`
3. `test_ticker_ev_ebitda_used_when_no_peer_median` -> with Tech sector, ticker=25 blends with sector=20, result=22.5, source="Blended (Ticker + Sector)"
4. `test_exit_multiple_source_is_returned` -> add "Blended (Ticker + Sector)", "Blended (Ticker + Industry)", "Industry Default" to valid sources

#### New tests to add (12+):
1. `test_ticker_blended_with_sector_default` — ticker=22, sector=20 -> 21
2. `test_ticker_only_when_unknown_sector` — unknown sector, no blend
3. `test_negative_eps_forces_low_confidence` — trailing_eps=-2.50 -> confidence="Low"
4. `test_thin_ebitda_margin_forces_low_confidence` — ebitda_margin=0.01 -> confidence="Low"
5. `test_normal_eps_not_affected` — trailing_eps=5.0 -> confidence unaffected
6. `test_airline_gets_higher_wacc` — industry="Airlines" -> WACC >= 14%
7. `test_biotech_gets_higher_wacc` — industry="Biotechnology" -> WACC >= 12%
8. `test_defense_gets_premium_exit_multiple` — industry="Aerospace & Defense" -> ~15x
9. `test_airline_gets_lower_exit_multiple` — industry="Airlines" -> 6x (industry floor allows this)
10. `test_biotech_negative_ebitda_uses_revenue_multiple` — biotech + negative EBITDA -> 6x Revenue
11. `test_normal_tech_unaffected_by_industry_overrides` — industry="Software - Infrastructure" -> no override
12. `test_industry_wacc_floor_applied` — generic industry floor test
13. `test_industry_exit_multiple_floor_overrides_global` — Airlines gets 6x not clamped to 8x

Example test pattern for industry tests:
```python
def test_airline_gets_higher_wacc(self):
    f = _make_fundamentals(
        sector="Industrials",
        industry="Airlines",
        beta=1.2,
    )
    result = calculate_dcf(f)
    assert result["wacc"] >= 0.14
```

**Acceptance Criteria:**
- All 141 existing tests pass (with 4 updates)
- All 13 new tests pass
- Total test count >= 154

**Effort:** Medium

---

## Execution Order

1. **Task 1** (config.py) — trivial, do first
2. **Task 2** (fundamentals.py) — trivial, parallel with Task 1
3. **Task 3** (dcf_engine.py) — medium, core engine work
4. **Task 4** (excel_builder) — small, parallel with Task 3
5. **Task 5** (tests) — medium, must be last

Tasks 1+2 are independent and can run in parallel. Task 3 depends on both. Task 4 is independent. Task 5 validates all.

---

## Success Criteria

1. `python -m pytest tests/test_dcf.py` — all tests pass (154+)
2. IV cap: no stock shows > 100% upside (was 200%)
3. Negative-EPS stocks show "(Low Confidence)"
4. Exit multiples blend ticker + best reference (industry > sector) when available
5. Airlines WACC >= 14%, exit multiple ~6x
6. Biotech WACC >= 12%, negative-EBITDA uses 6x Revenue
7. Defense exit multiple ~15x
8. Buy Price column in Excel
9. No regressions for normal stocks
10. Cache backward-compatible (old data works, new data adds industry)

---

## Risk Notes

- **Industry string matching:** yfinance `industry` values are free-text. Config dicts use exact match. If yfinance changes labels, overrides silently stop working. Mitigation: log when a Financial/Energy/Healthcare sector stock has no industry override match.
- **50/50 blend for extreme cases:** ticker=5x, sector=20x -> blend=12.5x. This is acceptable — the blend anchors outliers toward sector norms. No special handling for extreme divergence.
- **Test fragility:** Tests updated to use config constants where possible instead of hardcoded literals.
