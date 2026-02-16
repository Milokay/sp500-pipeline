"""
DCF (Discounted Cash Flow) intrinsic valuation calculator.
Calculates fair value per share using projected free cash flows.
"""

import logging

import config

logger = logging.getLogger(__name__)


def _is_financial_sector(sector: str) -> bool:
    """Check if ticker is in the financial sector."""
    if not sector:
        return False
    return sector.lower() in ("financial services", "financials")


def _is_reit(sector: str) -> bool:
    """Check if ticker is a REIT (skip DCF, use P/B only)."""
    if not sector:
        return False
    return sector.lower() in ("real estate",)


ASSET_LIGHT_FINANCIAL_TICKERS = {
    "V", "MA", "PYPL", "SPGI", "MCO", "MSCI", "FDS",
    "ICE", "NDAQ", "CBOE", "FIS", "FISV", "GPN",
}


def _is_asset_light_financial(fundamentals: dict) -> bool:
    """
    Detect asset-light financial companies that should use DCF instead of P/B.
    Covers: V, MA, PYPL, SPGI, MCO, MSCI, FDS, ICE, etc.
    These have high ROE and high P/B because their value is in intangibles, not book assets.
    Uses explicit ticker list for stability, with ROE/P/B heuristic as fallback.
    """
    ticker = fundamentals.get("ticker", "")
    if ticker in ASSET_LIGHT_FINANCIAL_TICKERS:
        return True
    roe = fundamentals.get("return_on_equity")
    pb = fundamentals.get("price_to_book")
    if roe is not None and pb is not None:
        return roe > config.ASSET_LIGHT_ROE_THRESHOLD and pb > config.ASSET_LIGHT_PB_THRESHOLD
    return False


def _cap_beta(beta: float) -> float:
    """Cap beta at 2.5 to avoid unrealistic WACC."""
    if beta is None:
        return 1.0
    return min(max(beta, config.BETA_FLOOR), 2.5)


def _handle_missing_shares(fundamentals: dict) -> dict:
    """Return insufficient data result when shares_outstanding is missing."""
    return {
        "intrinsic_value": None,
        "buy_price": None,
        "upside_pct": None,
        "wacc": None,
        "fcf_growth_rate": None,
        "valuation_status": "Insufficient Data",
        "confidence": "Low",
        "dcf_note": "Shares outstanding missing or zero — cannot calculate per-share value",
    }


def _handle_financial_company(fundamentals: dict) -> dict:
    """
    P/B-based valuation for traditional financial companies (banks, insurance).
    Uses ROE-adjusted fair P/B instead of hard-coded 1.5.
    fair_pb = ROE / cost_of_equity, capped at [BANK_FAIR_PB_FLOOR, BANK_FAIR_PB_CAP].
    """
    price = fundamentals.get("current_price")
    pb = fundamentals.get("price_to_book")
    roe = fundamentals.get("return_on_equity")

    # Sanity-check P/B values
    if pb is None or pb < 0.05 or pb > 200:
        return {
            "intrinsic_value": None,
            "buy_price": None,
            "upside_pct": None,
            "wacc": None,
            "fcf_growth_rate": None,
            "valuation_status": "Insufficient Data",
            "confidence": "Low",
            "dcf_note": "P/B ratio unavailable or unreliable",
        }

    # Calculate ROE-adjusted fair P/B
    beta = _cap_beta(fundamentals.get("beta", 1.0))
    cost_of_equity = config.RISK_FREE_RATE + beta * config.EQUITY_RISK_PREMIUM
    if roe is not None and roe > 0 and cost_of_equity > 0:
        fair_pb = roe / cost_of_equity
        fair_pb = max(config.BANK_FAIR_PB_FLOOR, min(fair_pb, config.BANK_FAIR_PB_CAP))
    else:
        fair_pb = 1.5  # Fallback

    upside = None
    if pb > 0 and price is not None:
        book_value_per_share = price / pb
        fair_value = book_value_per_share * fair_pb
        upside = (fair_value - price) / price
    else:
        fair_value = price

    # Determine status based on actual P/B vs fair P/B
    status = "Fair Value"
    if pb > 0 and fair_pb > 0:
        pb_ratio = pb / fair_pb
        if pb_ratio < 0.75:
            status = "Undervalued"
        elif pb_ratio > 1.5:
            status = "Overvalued"

    # Floor IV at 0
    if fair_value is not None and fair_value < config.IV_FLOOR:
        fair_value = config.IV_FLOOR

    return {
        "intrinsic_value": round(fair_value, 2) if fair_value else None,
        "buy_price": round(fair_value * (1 - config.MARGIN_OF_SAFETY), 2) if fair_value else None,
        "upside_pct": round(upside, 4) if upside is not None else None,
        "wacc": None,
        "fcf_growth_rate": None,
        "valuation_status": status,
        "confidence": "Medium",
        "dcf_note": f"Financial sector — using ROE-adjusted P/B (fair P/B={fair_pb:.2f})",
    }


def _handle_reit(fundamentals: dict) -> dict:
    """Skip DCF for REITs, return P/B-based stub (yfinance lacks FFO)."""
    price = fundamentals.get("current_price")
    pb = fundamentals.get("price_to_book")

    # Sanity-check P/B values
    if pb is None or pb < 0.05 or pb > 200:
        return {
            "intrinsic_value": None,
            "buy_price": None,
            "upside_pct": None,
            "wacc": None,
            "fcf_growth_rate": None,
            "valuation_status": "Insufficient Data",
            "confidence": "Low",
            "dcf_note": "P/B ratio unavailable or unreliable",
        }

    status = "Fair Value"
    if pb > 0:
        if pb < 1.0:
            status = "Undervalued"
        elif pb > 2.5:
            status = "Overvalued"

    upside = None
    if pb > 0 and price is not None:
        book_value_per_share = price / pb
        fair_value = book_value_per_share * 1.5
        upside = (fair_value - price) / price
    else:
        fair_value = price

    # Floor IV at 0
    if fair_value is not None and fair_value < config.IV_FLOOR:
        fair_value = config.IV_FLOOR

    return {
        "intrinsic_value": round(fair_value, 2) if fair_value else None,
        "buy_price": round(fair_value * (1 - config.MARGIN_OF_SAFETY), 2) if fair_value else None,
        "upside_pct": round(upside, 4) if upside is not None else None,
        "wacc": None,
        "fcf_growth_rate": None,
        "valuation_status": status,
        "confidence": "Medium",
        "dcf_note": "REIT — DCF skipped, using P/B-based valuation (FFO unavailable via yfinance)",
    }


def _resolve_exit_multiple(fundamentals: dict, sector_ev_ebitda_median: float = None) -> tuple:
    """
    Resolve the EV/EBITDA exit multiple using the fallback chain:
    1. Sector peer median (from relative valuation)
    2. Ticker's own EV/EBITDA (blended with industry/sector defaults if available)
    3. Industry default from config
    4. Sector default from config
    5. Global default from config

    Clamps result to [INDUSTRY_EXIT_MULTIPLE_FLOORS or EXIT_MULTIPLE_FLOOR, EXIT_MULTIPLE_CAP].
    Returns (multiple, source_description).
    """
    sector = fundamentals.get("sector", "")
    industry = fundamentals.get("industry", "")

    # Determine industry-specific floor (or use global)
    floor = config.INDUSTRY_EXIT_MULTIPLE_FLOORS.get(industry, config.EXIT_MULTIPLE_FLOOR)

    def clamp(val):
        return max(floor, min(val, config.EXIT_MULTIPLE_CAP))

    # 1. Sector peer median (best signal — live data)
    if sector_ev_ebitda_median is not None and sector_ev_ebitda_median > 0:
        return (clamp(sector_ev_ebitda_median), "Sector Peer Median")

    # 2. Ticker's own EV/EBITDA available?
    ticker_ev = fundamentals.get("ev_to_ebitda")
    ticker_valid = ticker_ev is not None and 1.0 < ticker_ev < 100.0

    if ticker_valid:
        industry_default = config.INDUSTRY_EXIT_MULTIPLES.get(industry)
        sector_default = config.SECTOR_EXIT_MULTIPLES.get(sector)

        if industry_default is not None:
            blended = (ticker_ev + industry_default) / 2
            return (clamp(blended), "Blended (Ticker + Industry)")
        elif sector_default is not None:
            blended = (ticker_ev + sector_default) / 2
            return (clamp(blended), "Blended (Ticker + Sector)")
        else:
            return (clamp(ticker_ev), "Ticker EV/EBITDA")

    # 3. No ticker data — use best available default
    industry_default = config.INDUSTRY_EXIT_MULTIPLES.get(industry)
    if industry_default is not None:
        return (clamp(industry_default), "Industry Default")

    sector_default = config.SECTOR_EXIT_MULTIPLES.get(sector)
    if sector_default is not None:
        return (clamp(sector_default), "Sector Default")

    # 4. Global default
    return (config.DEFAULT_EXIT_MULTIPLE, "Global Default")


def _resolve_revenue_multiple(fundamentals: dict) -> tuple:
    """
    Resolve EV/Revenue multiple for negative-EBITDA companies.
    1. Company's own enterprise_to_revenue (from yfinance)
    2. Industry default from config
    3. Sector default from config
    4. Global default

    Clamps to [REVENUE_MULTIPLE_FLOOR, REVENUE_MULTIPLE_CAP].
    Returns (multiple, source_description).
    """
    sector = fundamentals.get("sector", "")
    industry = fundamentals.get("industry", "")

    # 1. Company's own EV/Revenue
    ev_to_rev = fundamentals.get("enterprise_to_revenue")
    if ev_to_rev is not None and ev_to_rev > 0:
        multiple = max(config.REVENUE_MULTIPLE_FLOOR, min(ev_to_rev, config.REVENUE_MULTIPLE_CAP))
        return (multiple, "Company EV/Revenue")

    # 2. Industry-specific revenue multiple
    industry_rev = config.INDUSTRY_REVENUE_MULTIPLES.get(industry)
    if industry_rev is not None:
        return (industry_rev, "Industry Revenue Default")

    # 3. Sector default
    sector_default = config.SECTOR_REVENUE_MULTIPLES.get(sector)
    if sector_default is not None:
        return (sector_default, "Sector Revenue Default")

    # 4. Global default
    return (config.DEFAULT_REVENUE_MULTIPLE, "Global Revenue Default")


def _apply_analyst_sanity_check(intrinsic_value: float, fundamentals: dict, confidence: str) -> tuple:
    """
    If analyst target price is available with sufficient coverage,
    cap IV when it deviates too far from consensus.
    Returns (adjusted_iv, adjusted_confidence, note_or_none).
    """
    analyst_target = fundamentals.get("analyst_target_price")
    num_analysts = fundamentals.get("number_of_analysts")

    if (analyst_target is not None and analyst_target > 0
            and num_analysts is not None and num_analysts >= config.MIN_ANALYSTS_FOR_TARGET):
        if intrinsic_value > analyst_target * config.ANALYST_TARGET_MAX_DEVIATION:
            capped_iv = analyst_target * 2.0
            note = f"IV capped by analyst consensus (target=${analyst_target:.2f}, {int(num_analysts)} analysts)"
            return (capped_iv, "Low", note)
    return (intrinsic_value, confidence, None)


def calculate_dcf(fundamentals: dict, sector_ev_ebitda_median: float = None) -> dict:
    """
    Calculate intrinsic value per share using Discounted Cash Flow analysis.

    Uses Exit Multiple Method as the primary terminal value approach,
    with Perpetual Growth (Gordon Growth) as secondary. Blends both methods
    when implied perpetuity growth exceeds GDP ceiling.

    Input: fundamentals dict from fundamentals.py
           sector_ev_ebitda_median: median EV/EBITDA for the sector (optional)
    Returns dict with: intrinsic_value, buy_price, upside_pct, wacc,
    fcf_growth_rate, valuation_status, confidence, dcf_note,
    terminal_method, exit_multiple_used, exit_multiple_source,
    iv_exit_multiple, iv_perpetual_growth, implied_perpetuity_growth,
    valuation_warning
    """
    ticker = fundamentals.get("ticker", "Unknown")
    sector = fundamentals.get("sector", "")

    # --- Edge cases: skip DCF for special sectors ---
    # Asset-light financials (V, MA, SPGI, etc.) bypass the P/B fallback and use DCF
    if _is_financial_sector(sector) and not _is_asset_light_financial(fundamentals):
        logger.info(f"{ticker}: financial sector — skipping DCF")
        return _handle_financial_company(fundamentals)

    if _is_reit(sector):
        logger.info(f"{ticker}: REIT — skipping DCF")
        return _handle_reit(fundamentals)

    if _is_financial_sector(sector) and _is_asset_light_financial(fundamentals):
        logger.info(f"{ticker}: asset-light financial — using DCF")

    # --- Check shares outstanding ---
    shares = fundamentals.get("shares_outstanding")
    if not shares or shares <= 0:
        logger.warning(f"{ticker}: shares outstanding missing/zero")
        return _handle_missing_shares(fundamentals)

    # --- Earnings quality check ---
    earnings_quality_note = None
    force_low_confidence = False
    trailing_eps = fundamentals.get("trailing_eps")
    ebitda_margin_val = fundamentals.get("ebitda_margin")

    if trailing_eps is not None and trailing_eps < 0:
        force_low_confidence = True
        earnings_quality_note = f"Negative trailing EPS (${trailing_eps:.2f})"
    elif ebitda_margin_val is not None and ebitda_margin_val <= 0:
        force_low_confidence = True
        earnings_quality_note = f"Non-positive EBITDA margin ({ebitda_margin_val:.1%})"
    elif (ebitda_margin_val is not None and ebitda_margin_val > 0
          and ebitda_margin_val < config.MIN_EBITDA_MARGIN_FOR_DCF):
        force_low_confidence = True
        earnings_quality_note = f"Thin EBITDA margin ({ebitda_margin_val:.1%})"

    # --- Step 1: Get base FCF ---
    fcf_history = fundamentals.get("free_cash_flow", [])
    current_price = fundamentals.get("current_price")
    market_cap = fundamentals.get("market_cap")
    total_debt = fundamentals.get("total_debt", 0) or 0

    if not fcf_history or all(f is None for f in fcf_history):
        # No FCF data — try revenue-based proxy
        revenue_growth = fundamentals.get("revenue_growth")
        total_revenue_val = fundamentals.get("total_revenue")
        if revenue_growth is not None and total_revenue_val and total_revenue_val > 0:
            estimated_margin = 0.05
            base_fcf = total_revenue_val * estimated_margin
            growth_rate = max(revenue_growth * 0.5, 0.02)
            confidence = "Low"
            logger.info(f"{ticker}: no FCF data, using revenue-based proxy")
        elif revenue_growth is not None and market_cap:
            # Last resort: use market_cap if no revenue data
            base_fcf = market_cap * 0.05
            growth_rate = max(revenue_growth * 0.5, 0.02)
            confidence = "Low"
            logger.info(f"{ticker}: no FCF/revenue data, using market_cap proxy")
        else:
            logger.warning(f"{ticker}: insufficient data for DCF")
            return {
                "intrinsic_value": None,
                "buy_price": None,
                "upside_pct": None,
                "wacc": None,
                "fcf_growth_rate": None,
                "valuation_status": "Insufficient Data",
                "confidence": "Low",
                "dcf_note": "No FCF or revenue data available",
            }
    else:
        # Filter out None values
        fcf_history = [f for f in fcf_history if f is not None]
        base_fcf = fcf_history[0]  # Most recent year

        # Check if all FCF values are negative
        if all(f < 0 for f in fcf_history):
            revenue_growth = fundamentals.get("revenue_growth")
            total_revenue_val = fundamentals.get("total_revenue")
            if revenue_growth is not None and total_revenue_val and total_revenue_val > 0:
                estimated_margin = 0.05
                base_fcf = total_revenue_val * estimated_margin
                growth_rate = max(revenue_growth * 0.5, 0.02)
                confidence = "Low"
                logger.info(f"{ticker}: all negative FCF, using revenue proxy")
            elif revenue_growth is not None and market_cap:
                base_fcf = market_cap * 0.05
                growth_rate = max(revenue_growth * 0.5, 0.02)
                confidence = "Low"
                logger.info(f"{ticker}: all negative FCF, using market_cap proxy")
            else:
                return {
                    "intrinsic_value": None,
                    "buy_price": None,
                    "upside_pct": None,
                    "wacc": None,
                    "fcf_growth_rate": None,
                    "valuation_status": "Insufficient Data",
                    "confidence": "Low",
                    "dcf_note": "All FCF values negative, no revenue data for proxy",
                }
        else:
            # --- Step 2: Calculate FCF growth rate (CAGR) ---
            if len(fcf_history) >= 2 and fcf_history[-1] > 0 and fcf_history[0] > 0:
                years = len(fcf_history) - 1
                growth_rate = (fcf_history[0] / fcf_history[-1]) ** (1 / years) - 1
            elif len(fcf_history) >= 2:
                # Mixed positive/negative — use simple change
                if fcf_history[-1] != 0:
                    growth_rate = (fcf_history[0] - fcf_history[-1]) / abs(fcf_history[-1])
                else:
                    growth_rate = 0.05  # Default
            else:
                growth_rate = 0.05  # Default for single year

            # Cap growth rate
            growth_rate = max(-0.05, min(growth_rate, 0.25))

            # Sector-specific growth rate caps
            sector_lower = (sector or "").lower()
            if sector_lower in ("utilities", "energy"):
                growth_rate = min(growth_rate, 0.10)
            elif sector_lower in ("consumer staples", "consumer defensive"):
                growth_rate = min(growth_rate, 0.12)

            # Determine confidence
            if len(fcf_history) >= 3 and all(f > 0 for f in fcf_history) and fundamentals.get("beta"):
                confidence = "High"
            elif len(fcf_history) < 3 or any(f < 0 for f in fcf_history):
                confidence = "Medium"
            else:
                confidence = "High"

    # Apply earnings quality override
    if force_low_confidence:
        confidence = "Low"

    # --- Step 3: Project future FCF (5 years with growth decay) ---
    projected_fcf = []
    prev_fcf = base_fcf
    for year in range(1, config.DCF_PROJECTION_YEARS + 1):
        decay_factor = 1 - 0.1 * year  # 10% decay per year
        year_growth = growth_rate * max(decay_factor, 0.1)  # Floor decay at 0.1
        year_fcf = prev_fcf * (1 + year_growth)
        projected_fcf.append(year_fcf)
        prev_fcf = year_fcf

    # --- Step 3B: Get base EBITDA and project forward for terminal value ---
    base_ebitda = fundamentals.get("ebitda")
    ebitda_margin = fundamentals.get("ebitda_margin")
    total_revenue = fundamentals.get("total_revenue")

    # Fallback: estimate EBITDA from revenue * margin
    if (base_ebitda is None or base_ebitda < 0) and total_revenue and ebitda_margin and ebitda_margin > 0:
        base_ebitda = total_revenue * ebitda_margin

    # Fallback: derive from EV/EBITDA ratio
    if base_ebitda is None or base_ebitda < 0:
        ev_to_ebitda = fundamentals.get("ev_to_ebitda")
        if ev_to_ebitda and ev_to_ebitda > 1.0 and market_cap:
            estimated_ev = market_cap + total_debt
            base_ebitda = estimated_ev / ev_to_ebitda

    # Project EBITDA forward with same growth trajectory as FCF
    ebitda_year5 = None
    if base_ebitda and base_ebitda > 0:
        prev_ebitda = base_ebitda
        for year in range(1, config.DCF_PROJECTION_YEARS + 1):
            decay_factor = 1 - 0.1 * year
            year_growth = growth_rate * max(decay_factor, 0.1)
            prev_ebitda = prev_ebitda * (1 + year_growth)
        ebitda_year5 = prev_ebitda

    # --- Step 4: Calculate WACC ---
    beta = _cap_beta(fundamentals.get("beta", 1.0))
    cost_of_equity = config.RISK_FREE_RATE + beta * config.EQUITY_RISK_PREMIUM

    interest_expense = fundamentals.get("interest_expense")
    if interest_expense and total_debt and total_debt > 0:
        cost_of_debt_pretax = abs(interest_expense) / total_debt
        cost_of_debt_pretax = max(0.01, min(cost_of_debt_pretax, 0.15))  # Sanity bounds
        tax_rate = 0.21
        cost_of_debt = cost_of_debt_pretax * (1 - tax_rate)
    else:
        cost_of_debt = config.RISK_FREE_RATE + 0.015  # Fallback: Rf + 150bps (BBB spread)

    if market_cap and market_cap > 0:
        weight_equity = market_cap / (market_cap + total_debt)
        weight_debt = total_debt / (market_cap + total_debt)
        wacc = (weight_equity * cost_of_equity) + (weight_debt * cost_of_debt)
    else:
        wacc = config.DEFAULT_WACC

    # Apply industry-specific WACC floor
    industry = fundamentals.get("industry", "")
    industry_wacc_floor = config.INDUSTRY_WACC_FLOORS.get(industry)
    if industry_wacc_floor is not None:
        wacc = max(wacc, industry_wacc_floor)
    wacc = max(0.06, min(wacc, 0.20))  # Re-apply global bounds

    # --- Step 5: Terminal Value (Dual Method) ---
    fcf_year5 = projected_fcf[-1] if projected_fcf else base_fcf

    # --- 5A: Exit Multiple Method (PRIMARY) ---
    exit_multiple, exit_multiple_source = _resolve_exit_multiple(
        fundamentals, sector_ev_ebitda_median
    )
    if ebitda_year5 and ebitda_year5 > 0:
        terminal_value_exit = ebitda_year5 * exit_multiple
    elif total_revenue and total_revenue > 0 and (base_ebitda is None or base_ebitda < 0):
        # Negative EBITDA fallback: use EV/Revenue
        rev_multiple, rev_source = _resolve_revenue_multiple(fundamentals)
        # Project revenue forward
        prev_rev = total_revenue
        for year in range(1, config.DCF_PROJECTION_YEARS + 1):
            decay_factor = 1 - 0.1 * year
            year_growth = growth_rate * max(decay_factor, 0.1)
            prev_rev = prev_rev * (1 + year_growth)
        terminal_value_exit = prev_rev * rev_multiple
        exit_multiple_source = f"EV/Revenue ({rev_source})"
        exit_multiple = rev_multiple
        logger.info(f"{ticker}: negative EBITDA, using EV/Revenue fallback (x{rev_multiple:.1f})")
    else:
        # Last resort: apply exit multiple to FCF (may produce negative TV)
        terminal_value_exit = fcf_year5 * exit_multiple
        logger.info(f"{ticker}: EBITDA unavailable, applying exit multiple to FCF")

    # --- 5B: Perpetual Growth Method (SECONDARY / SANITY CHECK) ---
    wacc_g_spread = wacc - config.TERMINAL_GROWTH_RATE
    if wacc_g_spread >= config.MIN_WACC_G_SPREAD:
        terminal_value_perp = (
            fcf_year5 * (1 + config.TERMINAL_GROWTH_RATE)
            / wacc_g_spread
        )
    else:
        terminal_value_perp = None
        logger.warning(f"{ticker}: WACC-g spread < {config.MIN_WACC_G_SPREAD}, perpetual growth skipped")

    # --- 5C: Implied Perpetuity Growth Rate (sanity check) ---
    valuation_warning = None
    denominator = terminal_value_exit + fcf_year5
    if terminal_value_exit > 0 and denominator != 0:
        implied_g = (terminal_value_exit * wacc - fcf_year5) / denominator
        if implied_g > config.MAX_IMPLIED_GROWTH_RATE:
            valuation_warning = (
                f"Implied growth rate ({implied_g:.1%}) exceeds "
                f"GDP growth ceiling ({config.MAX_IMPLIED_GROWTH_RATE:.0%})"
            )
            logger.warning(f"{ticker}: {valuation_warning}")
    else:
        implied_g = None

    # --- Step 6: Present Value calculation ---
    pv_fcfs = sum(
        fcf / (1 + wacc) ** year
        for year, fcf in enumerate(projected_fcf, 1)
    )

    # Calculate IV from Exit Multiple
    total_cash = fundamentals.get("total_cash", 0) or 0
    pv_terminal_exit = terminal_value_exit / (1 + wacc) ** config.DCF_PROJECTION_YEARS
    ev_exit = pv_fcfs + pv_terminal_exit
    eq_exit = ev_exit - total_debt + total_cash
    iv_exit = eq_exit / shares

    # Calculate IV from Perpetual Growth
    iv_perp = None
    if terminal_value_perp is not None:
        pv_terminal_perp = terminal_value_perp / (1 + wacc) ** config.DCF_PROJECTION_YEARS
        ev_perp = pv_fcfs + pv_terminal_perp
        eq_perp = ev_perp - total_debt + total_cash
        iv_perp = eq_perp / shares
        if iv_perp < 0:
            iv_perp = None

    # --- Step 6B: Multi-method IV blending ---
    iv_method = "Exit Multiple Only"
    if iv_perp is not None and iv_perp > 0 and iv_exit > 0:
        # Blend when implied growth exceeds GDP ceiling
        if implied_g is not None and implied_g > config.MAX_IMPLIED_GROWTH_RATE:
            if confidence == "High":
                intrinsic_value = 0.6 * iv_exit + 0.4 * iv_perp
            elif confidence == "Medium":
                intrinsic_value = 0.5 * iv_exit + 0.5 * iv_perp
            else:  # Low
                intrinsic_value = 0.4 * iv_exit + 0.6 * iv_perp
            # Downgrade confidence when blending due to high implied growth
            if confidence == "High":
                confidence = "Medium"
            iv_method = "Blended (Exit+Perp)"
            logger.info(f"{ticker}: blending IV methods due to high implied growth ({implied_g:.1%})")
        else:
            intrinsic_value = iv_exit
    else:
        intrinsic_value = iv_exit

    # --- Floor IV at 0 (never negative) ---
    if intrinsic_value < config.IV_FLOOR:
        intrinsic_value = config.IV_FLOOR
        confidence = "Low"
        logger.info(f"{ticker}: IV floored at $0 (was negative)")

    # --- Cap intrinsic value at 2x current price ---
    dcf_note = None
    if current_price and current_price > 0 and intrinsic_value > current_price * config.IV_CAP_MULTIPLIER:
        intrinsic_value = current_price * config.IV_CAP_MULTIPLIER
        confidence = "Low"
        dcf_note = f"Intrinsic value capped at {config.IV_CAP_MULTIPLIER:.0f}x current price (model limitation)"

    # Also cap perpetual growth IV for display
    if iv_perp is not None and current_price and current_price > 0:
        if iv_perp > current_price * config.IV_CAP_MULTIPLIER:
            iv_perp = current_price * config.IV_CAP_MULTIPLIER
    # Floor iv_exit for display
    if iv_exit < config.IV_FLOOR:
        iv_exit = config.IV_FLOOR

    # --- Analyst target sanity check ---
    analyst_note = None
    intrinsic_value, confidence, analyst_note = _apply_analyst_sanity_check(
        intrinsic_value, fundamentals, confidence
    )
    if analyst_note:
        dcf_note = analyst_note

    # Add earnings quality note if not already set
    if earnings_quality_note and dcf_note is None:
        dcf_note = earnings_quality_note

    # --- Step 7: Margin of Safety ---
    buy_price = intrinsic_value * (1 - config.MARGIN_OF_SAFETY) if intrinsic_value > 0 else 0

    # --- Step 8: Valuation Status ---
    if current_price and current_price > 0 and intrinsic_value and intrinsic_value > 0:
        upside_pct = (intrinsic_value - current_price) / current_price
    else:
        upside_pct = None

    if upside_pct is not None:
        if upside_pct > config.MARGIN_OF_SAFETY:
            valuation_status = "Undervalued"
        elif upside_pct < config.SELL_DOWNSIDE:
            valuation_status = "Overvalued"
        else:
            valuation_status = "Fair Value"
    else:
        valuation_status = "Insufficient Data"

    return {
        "intrinsic_value": round(intrinsic_value, 2) if intrinsic_value is not None else None,
        "buy_price": round(buy_price, 2) if buy_price is not None else None,
        "upside_pct": round(upside_pct, 4) if upside_pct is not None else None,
        "wacc": round(wacc, 4),
        "fcf_growth_rate": round(growth_rate, 4),
        "valuation_status": valuation_status,
        "confidence": confidence,
        "dcf_note": dcf_note,
        "terminal_method": iv_method,
        "exit_multiple_used": round(exit_multiple, 2),
        "exit_multiple_source": exit_multiple_source,
        "iv_exit_multiple": round(iv_exit, 2) if iv_exit is not None else None,
        "iv_perpetual_growth": round(iv_perp, 2) if iv_perp is not None else None,
        "implied_perpetuity_growth": round(implied_g, 4) if implied_g is not None else None,
        "valuation_warning": valuation_warning,
    }
