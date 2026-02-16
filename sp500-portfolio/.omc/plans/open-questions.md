# Open Questions

## plan-iv-fixes-round2 - 2026-02-15

- [ ] **Margin of Safety on IV:** User wants IV itself reduced by 25%. Plan recommends keeping IV as fair value and surfacing `buy_price` prominently instead. Does the user agree, or do they want the displayed IV column to literally show `IV * 0.75`? — This changes the meaning of "Intrinsic Value" in the output from fair value to conservative buy target.

- [ ] **EXIT_MULTIPLE_FLOOR and Airlines 6x:** User wants Airlines at 6x exit multiple, but the global `EXIT_MULTIPLE_FLOOR = 8.0` clamps it to 8x. Should we lower the global floor from 8x to 6x, or add industry-specific floor overrides? — Lowering the global floor could affect other sectors that currently benefit from the 8x minimum.

- [ ] **Industry string stability from yfinance:** The sector-specific overrides rely on exact-match industry strings from yfinance (e.g., "Airlines", "Biotechnology", "Aerospace & Defense"). If yfinance changes these labels, overrides silently stop working. Should we add fuzzy matching or a normalization layer? — Adds complexity but improves resilience. A simple logging warning when a known high-risk sector has no industry override match could be a lighter alternative.

- [ ] **Technology DCF + Forward P/E blend:** User mentioned blending DCF with Forward P/E for Technology stocks. This would be a new terminal value method, not just a parameter tweak. Should this be deferred to Round 3, or is it a priority for this round? — Implementing a third valuation method significantly increases scope and test surface.

- [ ] **Energy normalized DCF:** User wants Energy stocks to use historical averages to normalize for commodity price sensitivity. yfinance only provides trailing data, not multi-year averages. Should we compute a 3-year average from available data, or defer this? — The current codebase already has up to 3 years of FCF history which could be used as a proxy for normalization.

- [ ] **WACC cap for stressed sectors:** The global WACC cap is 20%. With industry WACC floors of 14-16% for Airlines/Travel, the effective WACC range narrows to [14%, 20%]. Is 20% still the right ceiling, or should it be raised for distressed industries? — Most DCF models consider WACC > 20% unreliable.
