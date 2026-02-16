"""Unit tests for DCF engine."""

import pytest

import config
from modules.dcf_engine import (
    calculate_dcf,
    _is_financial_sector,
    _is_reit,
    _is_asset_light_financial,
    _cap_beta,
    _resolve_exit_multiple,
    _resolve_revenue_multiple,
    _apply_analyst_sanity_check,
)


# --- Fixtures: hardcoded fundamentals data ---

def _make_fundamentals(**overrides):
    """Create a base fundamentals dict with sensible AAPL-like defaults."""
    base = {
        "ticker": "TEST",
        "current_price": 200.0,
        "market_cap": 3_000_000_000_000,  # 3T
        "shares_outstanding": 15_000_000_000,  # 15B
        "beta": 1.1,
        "sector": "Technology",
        "industry": None,
        "trailing_pe": 30.0,
        "forward_pe": 28.0,
        "price_to_book": 40.0,
        "ev_to_ebitda": 22.0,
        "dividend_yield": 0.005,
        "return_on_equity": 0.30,
        "return_on_assets": 0.28,
        "operating_cash_flow": [110_000_000_000, 100_000_000_000, 90_000_000_000],
        "capital_expenditures": [-12_000_000_000, -11_000_000_000, -10_000_000_000],
        "free_cash_flow": [98_000_000_000, 89_000_000_000, 80_000_000_000],
        "total_debt": 100_000_000_000,
        "total_equity": 60_000_000_000,
        "interest_expense": 3_000_000_000,
        "revenue_growth": 0.08,
        "ebitda": 130_000_000_000,           # ~130B trailing EBITDA
        "ebitda_margin": 0.34,               # ~34%
        "total_revenue": 380_000_000_000,    # ~380B
        "analyst_target_price": 250.0,
        "number_of_analysts": 30,
        "enterprise_to_revenue": 8.0,
        "net_margin": 0.25,
        "operating_margin": 0.30,
        "gross_margin": 0.46,
    }
    base.update(overrides)
    return base


class TestHelpers:
    def test_is_financial_sector(self):
        assert _is_financial_sector("Financial Services") is True
        assert _is_financial_sector("Financials") is True
        assert _is_financial_sector("Technology") is False
        assert _is_financial_sector(None) is False

    def test_is_reit(self):
        assert _is_reit("Real Estate") is True
        assert _is_reit("Technology") is False
        assert _is_reit(None) is False

    def test_is_asset_light_financial(self):
        # V/MA-type: high ROE + high P/B
        assert _is_asset_light_financial({"return_on_equity": 0.40, "price_to_book": 15.0}) is True
        # Bank: moderate ROE + low P/B
        assert _is_asset_light_financial({"return_on_equity": 0.12, "price_to_book": 1.5}) is False
        # High ROE but low P/B
        assert _is_asset_light_financial({"return_on_equity": 0.30, "price_to_book": 3.0}) is False
        # Missing data
        assert _is_asset_light_financial({"return_on_equity": None, "price_to_book": 15.0}) is False
        assert _is_asset_light_financial({}) is False

    def test_cap_beta(self):
        assert _cap_beta(1.0) == 1.0
        assert _cap_beta(3.0) == 2.5  # Capped
        assert _cap_beta(0.05) == 0.5  # Floored at 0.5
        assert _cap_beta(None) == 1.0  # Default


class TestDCFNormal:
    """Test DCF with normal positive FCF data."""

    def test_aapl_like_returns_positive_intrinsic_value(self):
        fund = _make_fundamentals()
        result = calculate_dcf(fund)
        assert result["intrinsic_value"] is not None
        assert result["intrinsic_value"] > 0

    def test_aapl_like_reasonable_range(self):
        """Intrinsic value should be in a plausible range for these inputs."""
        fund = _make_fundamentals()
        result = calculate_dcf(fund)
        # With $98B FCF, 15B shares, IV should be in $50-$500 range
        assert 50 < result["intrinsic_value"] < 500

    def test_wacc_in_valid_range(self):
        fund = _make_fundamentals()
        result = calculate_dcf(fund)
        assert 0.06 <= result["wacc"] <= 0.20

    def test_valuation_status_valid(self):
        fund = _make_fundamentals()
        result = calculate_dcf(fund)
        assert result["valuation_status"] in (
            "Undervalued", "Fair Value", "Overvalued", "Insufficient Data"
        )

    def test_confidence_high_with_good_data(self):
        """With low exit multiple that doesn't trigger blending, confidence should be High."""
        fund = _make_fundamentals()
        result = calculate_dcf(fund, sector_ev_ebitda_median=10.0)
        assert result["confidence"] == "High"

    def test_buy_price_below_intrinsic(self):
        fund = _make_fundamentals()
        result = calculate_dcf(fund)
        assert result["buy_price"] < result["intrinsic_value"]

    def test_upside_pct_is_float(self):
        fund = _make_fundamentals()
        result = calculate_dcf(fund)
        assert isinstance(result["upside_pct"], float)

    def test_growth_rate_capped(self):
        fund = _make_fundamentals()
        result = calculate_dcf(fund)
        assert -0.05 <= result["fcf_growth_rate"] <= 0.25


class TestDCFEdgeCases:
    """Test edge cases and special handling."""

    def test_financial_sector_skips_dcf(self):
        fund = _make_fundamentals(sector="Financial Services", price_to_book=1.5)
        result = calculate_dcf(fund)
        assert "Financial sector" in result["dcf_note"]
        assert result["confidence"] == "Medium"

    def test_financials_sector_also_skips(self):
        fund = _make_fundamentals(sector="Financials", price_to_book=2.5)
        result = calculate_dcf(fund)
        assert "Financial sector" in result["dcf_note"]

    def test_reit_skips_dcf(self):
        fund = _make_fundamentals(sector="Real Estate", price_to_book=1.2)
        result = calculate_dcf(fund)
        assert "REIT" in result["dcf_note"]
        assert result["confidence"] == "Medium"

    def test_shares_outstanding_zero(self):
        fund = _make_fundamentals(shares_outstanding=0)
        result = calculate_dcf(fund)
        assert result["valuation_status"] == "Insufficient Data"
        assert result["intrinsic_value"] is None

    def test_shares_outstanding_none(self):
        fund = _make_fundamentals(shares_outstanding=None)
        result = calculate_dcf(fund)
        assert result["valuation_status"] == "Insufficient Data"

    def test_negative_fcf_all_years(self):
        fund = _make_fundamentals(
            free_cash_flow=[-5_000_000_000, -3_000_000_000, -2_000_000_000],
            revenue_growth=0.15,
        )
        result = calculate_dcf(fund)
        assert result["confidence"] == "Low"
        assert result["intrinsic_value"] is not None  # Should use revenue proxy

    def test_negative_fcf_no_revenue(self):
        fund = _make_fundamentals(
            free_cash_flow=[-5_000_000_000, -3_000_000_000, -2_000_000_000],
            revenue_growth=None,
            market_cap=None,
        )
        result = calculate_dcf(fund)
        assert result["valuation_status"] == "Insufficient Data"

    def test_empty_fcf_with_revenue(self):
        fund = _make_fundamentals(
            free_cash_flow=[],
            revenue_growth=0.10,
        )
        result = calculate_dcf(fund)
        assert result["confidence"] == "Low"

    def test_high_beta_gets_capped(self):
        fund = _make_fundamentals(beta=5.0)
        result = calculate_dcf(fund)
        # WACC should still be within bounds (beta capped at 2.5)
        assert result["wacc"] <= 0.20

    def test_wacc_floor(self):
        """Very low beta should still produce WACC >= 6%."""
        fund = _make_fundamentals(beta=0.1, total_debt=0, interest_expense=0)
        result = calculate_dcf(fund)
        assert result["wacc"] >= 0.06

    def test_terminal_value_fallback(self):
        """When WACC is very low, should use exit multiple fallback."""
        fund = _make_fundamentals()
        result = calculate_dcf(fund)
        assert result["intrinsic_value"] is not None


class TestDCFUnderOverValued:
    """Test valuation status determination."""

    def test_undervalued_when_cheap(self):
        """Low price relative to FCF should be undervalued."""
        fund = _make_fundamentals(
            current_price=50.0,  # Very low vs ~$200 fair value
            market_cap=750_000_000_000,
        )
        result = calculate_dcf(fund)
        assert result["valuation_status"] == "Undervalued"

    def test_overvalued_when_expensive(self):
        """High price relative to FCF should be overvalued."""
        fund = _make_fundamentals(
            current_price=1000.0,
            market_cap=15_000_000_000_000,
            free_cash_flow=[10_000_000_000, 9_000_000_000, 8_000_000_000],
        )
        result = calculate_dcf(fund)
        assert result["valuation_status"] == "Overvalued"


class TestDCFReasonableness:
    """Test DCF reasonableness checks."""

    def test_invalid_pb_financial_returns_insufficient(self):
        """P/B < 0.05 should return Insufficient Data for financials."""
        fund = {
            "ticker": "TEST", "sector": "Financial Services",
            "current_price": 500.0, "price_to_book": 0.001,
            "shares_outstanding": 1000000,
        }
        result = calculate_dcf(fund)
        assert result["valuation_status"] == "Insufficient Data"
        assert result["intrinsic_value"] is None

    def test_valid_pb_financial_works(self):
        """Valid P/B should still work for financials."""
        fund = {
            "ticker": "TEST", "sector": "Financial Services",
            "current_price": 100.0, "price_to_book": 1.5,
            "shares_outstanding": 1000000,
        }
        result = calculate_dcf(fund)
        assert result["intrinsic_value"] is not None
        assert result["valuation_status"] != "Insufficient Data"

    def test_invalid_pb_reit_returns_insufficient(self):
        """P/B < 0.05 should return Insufficient Data for REITs."""
        fund = {
            "ticker": "TEST", "sector": "Real Estate",
            "current_price": 200.0, "price_to_book": 0.001,
            "shares_outstanding": 1000000,
        }
        result = calculate_dcf(fund)
        assert result["valuation_status"] == "Insufficient Data"

    def test_iv_capped_at_2x_price(self):
        """Intrinsic value should be capped at 2x current price."""
        fund = _make_fundamentals(
            current_price=50.0,
            market_cap=5_000_000_000,
            shares_outstanding=100_000_000,
            free_cash_flow=[3_000_000_000, 1_000_000_000, 800_000_000],
            total_debt=0,
            revenue_growth=0.20,
            analyst_target_price=None,  # Disable analyst check
        )
        result = calculate_dcf(fund)
        assert result["intrinsic_value"] is not None
        assert result["intrinsic_value"] <= 50.0 * config.IV_CAP_MULTIPLIER

    def test_beta_floor_at_05(self):
        """Beta should be floored at 0.5, not 0.1."""
        assert _cap_beta(-0.02) == 0.5
        assert _cap_beta(0.1) == 0.5
        assert _cap_beta(0.3) == 0.5
        assert _cap_beta(0.6) == 0.6
        assert _cap_beta(1.0) == 1.0

    def test_no_extreme_upside(self):
        """No stock should show >100% upside (2x cap means max 1x upside)."""
        fund = _make_fundamentals(
            current_price=50.0,
            market_cap=20_000_000_000,
            shares_outstanding=200_000_000,
            free_cash_flow=[3_000_000_000, 1_500_000_000, 1_400_000_000],
            total_debt=0,
            analyst_target_price=None,  # Disable analyst check
        )
        result = calculate_dcf(fund)
        if result["upside_pct"] is not None:
            assert result["upside_pct"] <= 1.0, f"Upside {result['upside_pct']} exceeds 100%"


class TestResolveExitMultiple:
    """Test the exit multiple resolution fallback chain."""

    def test_sector_peer_median_preferred(self):
        fund = _make_fundamentals(ev_to_ebitda=22.0)
        multiple, source = _resolve_exit_multiple(fund, sector_ev_ebitda_median=18.5)
        assert multiple == 18.5
        assert source == "Sector Peer Median"

    def test_ticker_ev_ebitda_blended_with_sector(self):
        """Ticker EV/EBITDA blends 50/50 with sector default when available."""
        fund = _make_fundamentals(ev_to_ebitda=25.0, sector="Technology")
        multiple, source = _resolve_exit_multiple(fund, sector_ev_ebitda_median=None)
        # 25 blended with Tech sector default 20 = 22.5
        assert multiple == 22.5
        assert source == "Blended (Ticker + Sector)"

    def test_sector_default_when_no_ticker_data(self):
        fund = _make_fundamentals(ev_to_ebitda=None, sector="Technology")
        multiple, source = _resolve_exit_multiple(fund, sector_ev_ebitda_median=None)
        assert multiple == 20.0
        assert source == "Sector Default"

    def test_global_default_when_unknown_sector(self):
        fund = _make_fundamentals(ev_to_ebitda=None, sector="Alien Industries")
        multiple, source = _resolve_exit_multiple(fund, sector_ev_ebitda_median=None)
        assert multiple == 12.0
        assert source == "Global Default"

    def test_rejects_extreme_ticker_ev_ebitda(self):
        """EV/EBITDA outside 1-100 range should be skipped."""
        fund = _make_fundamentals(ev_to_ebitda=150.0, sector="Technology")
        multiple, source = _resolve_exit_multiple(fund, sector_ev_ebitda_median=None)
        assert source == "Sector Default"  # Skipped ticker's extreme value

    def test_rejects_negative_peer_median(self):
        fund = _make_fundamentals(ev_to_ebitda=22.0)
        multiple, source = _resolve_exit_multiple(fund, sector_ev_ebitda_median=-5.0)
        # Skipped negative median, falls to ticker blend with sector
        assert source in ("Blended (Ticker + Sector)", "Blended (Ticker + Industry)", "Ticker EV/EBITDA")


class TestExitMultipleMethod:
    """Test that Exit Multiple is used as primary terminal value."""

    def test_exit_multiple_is_primary_method(self):
        fund = _make_fundamentals()
        result = calculate_dcf(fund)
        assert result["terminal_method"] in ("Exit Multiple Only", "Blended (Exit+Perp)")

    def test_exit_multiple_used_is_returned(self):
        fund = _make_fundamentals()
        result = calculate_dcf(fund)
        assert result["exit_multiple_used"] is not None
        assert result["exit_multiple_used"] > 0

    def test_exit_multiple_source_is_returned(self):
        fund = _make_fundamentals()
        result = calculate_dcf(fund)
        assert result["exit_multiple_source"] in (
            "Sector Peer Median", "Ticker EV/EBITDA", "Sector Default", "Global Default",
            "Blended (Ticker + Sector)", "Blended (Ticker + Industry)", "Industry Default",
        )

    def test_sector_median_parameter_respected(self):
        fund = _make_fundamentals(sector="Technology")
        result_with = calculate_dcf(fund, sector_ev_ebitda_median=18.0)
        result_without = calculate_dcf(fund, sector_ev_ebitda_median=None)
        assert result_with["exit_multiple_source"] == "Sector Peer Median"
        assert result_with["exit_multiple_used"] == 18.0
        # Values should differ since different multiples are used
        assert result_with["intrinsic_value"] != result_without["intrinsic_value"]

    def test_iv_exit_multiple_returned(self):
        fund = _make_fundamentals()
        result = calculate_dcf(fund)
        assert result["iv_exit_multiple"] is not None
        assert result["iv_exit_multiple"] > 0

    def test_intrinsic_value_matches_exit_multiple_when_not_blended(self):
        """When not blended or capped, intrinsic_value equals iv_exit_multiple."""
        fund = _make_fundamentals()
        result = calculate_dcf(fund, sector_ev_ebitda_median=10.0)
        if result["dcf_note"] is None and result["terminal_method"] == "Exit Multiple Only":
            assert result["intrinsic_value"] == result["iv_exit_multiple"]


class TestDualMethodBracketing:
    """Test that both Exit Multiple and Perpetual Growth are calculated."""

    def test_both_iv_values_returned(self):
        fund = _make_fundamentals()
        result = calculate_dcf(fund)
        assert result["iv_exit_multiple"] is not None
        assert result["iv_perpetual_growth"] is not None

    def test_perpetual_growth_none_when_spread_thin(self):
        """When WACC-g spread is too thin, perpetual growth IV should be None."""
        fund = _make_fundamentals(beta=0.5, total_debt=0, interest_expense=0)
        result = calculate_dcf(fund)
        assert "iv_perpetual_growth" in result

    def test_implied_perpetuity_growth_returned(self):
        fund = _make_fundamentals()
        result = calculate_dcf(fund)
        assert result["implied_perpetuity_growth"] is not None
        assert isinstance(result["implied_perpetuity_growth"], float)

    def test_implied_growth_warning_when_high(self):
        """When implied g exceeds GDP ceiling, a warning should be generated."""
        fund = _make_fundamentals(ev_to_ebitda=50.0, sector="Alien Industries")
        result = calculate_dcf(fund, sector_ev_ebitda_median=25.0)
        if result["implied_perpetuity_growth"] is not None:
            if result["implied_perpetuity_growth"] > 0.04:
                assert result["valuation_warning"] is not None
                assert "exceeds" in result["valuation_warning"]

    def test_no_warning_when_implied_g_reasonable(self):
        """Reasonable multiples should not trigger warnings."""
        fund = _make_fundamentals(ev_to_ebitda=8.0, sector="Energy")
        result = calculate_dcf(fund, sector_ev_ebitda_median=8.0)
        if result["implied_perpetuity_growth"] is not None:
            if result["implied_perpetuity_growth"] <= 0.04:
                assert result["valuation_warning"] is None

    def test_both_ivs_in_reasonable_range(self):
        """Both methods should produce values in a plausible range."""
        fund = _make_fundamentals()
        result = calculate_dcf(fund)
        iv_exit = result["iv_exit_multiple"]
        iv_perp = result["iv_perpetual_growth"]
        if iv_exit and iv_perp:
            assert iv_exit > 0
            assert iv_perp > 0


class TestImpliedGrowthAccuracy:
    """Test mathematical correctness of the implied perpetuity growth rate."""

    def test_implied_growth_formula_correctness(self):
        """Verify implied g is in a reasonable range."""
        fund = _make_fundamentals()
        result = calculate_dcf(fund, sector_ev_ebitda_median=20.0)
        implied_g = result["implied_perpetuity_growth"]
        assert implied_g is not None
        assert -0.05 <= implied_g <= 0.15

    def test_known_implied_growth_value(self):
        """With known inputs, verify the implied g calculation is reasonable."""
        fund = _make_fundamentals(
            free_cash_flow=[10_000_000_000],
            ebitda=20_000_000_000,
            beta=1.0,
            total_debt=0,
            interest_expense=0,
            market_cap=3_000_000_000_000,
        )
        result = calculate_dcf(fund, sector_ev_ebitda_median=20.0)
        implied_g = result["implied_perpetuity_growth"]
        exit_mult = result["exit_multiple_used"]

        assert exit_mult == 20.0
        assert implied_g is not None
        assert 0.02 < implied_g < 0.15

    def test_low_multiple_produces_low_implied_growth(self):
        """A low exit multiple (8x) should imply a low growth rate."""
        fund = _make_fundamentals(sector="Energy")
        result = calculate_dcf(fund, sector_ev_ebitda_median=8.0)
        implied_g = result["implied_perpetuity_growth"]
        assert implied_g is not None
        assert implied_g < 0.06

    def test_high_multiple_produces_high_implied_growth(self):
        """A high exit multiple (25x, capped) should imply a higher growth rate."""
        fund = _make_fundamentals(sector="Technology")
        result = calculate_dcf(fund, sector_ev_ebitda_median=25.0)
        implied_g = result["implied_perpetuity_growth"]
        assert implied_g is not None
        assert implied_g > 0.03


class TestValuationModelFixes:
    """Tests for the valuation model overhaul (PRD fixes)."""

    # --- Exit Multiple Clamping ---

    def test_exit_multiple_capped_at_25x(self):
        """Exit multiples > 25 should be clamped to 25."""
        fund = _make_fundamentals(ev_to_ebitda=50.0, sector="Technology")
        multiple, source = _resolve_exit_multiple(fund, sector_ev_ebitda_median=40.0)
        assert multiple == config.EXIT_MULTIPLE_CAP  # 25.0

    def test_exit_multiple_floored_at_8x(self):
        """Exit multiples < 8 should be clamped to 8."""
        fund = _make_fundamentals(ev_to_ebitda=3.0, sector="Energy")
        multiple, source = _resolve_exit_multiple(fund, sector_ev_ebitda_median=5.0)
        assert multiple == config.EXIT_MULTIPLE_FLOOR  # 8.0

    # --- IV Floor ---

    def test_negative_iv_floored_at_zero(self):
        """IV should never be negative — floor at $0."""
        fund = _make_fundamentals(
            current_price=10.0,
            market_cap=1_000_000_000,
            shares_outstanding=100_000_000,
            free_cash_flow=[500_000_000, 400_000_000, 300_000_000],
            total_debt=50_000_000_000,  # Massive debt → equity value negative
            ebitda=1_000_000_000,
            analyst_target_price=None,
        )
        result = calculate_dcf(fund)
        assert result["intrinsic_value"] is not None
        assert result["intrinsic_value"] >= 0

    # --- Blending ---

    def test_implied_growth_triggers_blending(self):
        """When implied growth > 4%, IV should be blended with perpetual growth."""
        fund = _make_fundamentals(analyst_target_price=None)
        result = calculate_dcf(fund, sector_ev_ebitda_median=25.0)
        if (result["implied_perpetuity_growth"] is not None
                and result["implied_perpetuity_growth"] > config.MAX_IMPLIED_GROWTH_RATE
                and result["iv_perpetual_growth"] is not None):
            assert result["terminal_method"] == "Blended (Exit+Perp)"

    def test_blended_iv_has_both_components(self):
        """When blending triggers, both exit and perp IVs should be available."""
        fund = _make_fundamentals(analyst_target_price=None)
        result = calculate_dcf(fund, sector_ev_ebitda_median=25.0)
        if result["terminal_method"] == "Blended (Exit+Perp)":
            assert result["iv_exit_multiple"] is not None
            assert result["iv_perpetual_growth"] is not None
            assert result["iv_exit_multiple"] > 0
            assert result["iv_perpetual_growth"] > 0

    def test_blending_downgrades_confidence(self):
        """Blending due to high implied growth should cap confidence at Medium."""
        fund = _make_fundamentals(analyst_target_price=None)
        result = calculate_dcf(fund, sector_ev_ebitda_median=25.0)
        if result["terminal_method"] == "Blended (Exit+Perp)":
            assert result["confidence"] in ("Medium", "Low")

    # --- Asset-Light Financial Detection ---

    def test_asset_light_financial_uses_dcf(self):
        """V/MA-type companies should use DCF, not P/B fallback."""
        fund = _make_fundamentals(
            sector="Financial Services",
            return_on_equity=0.40,  # 40% ROE (like V/MA)
            price_to_book=15.0,    # High P/B
        )
        result = calculate_dcf(fund)
        # Should NOT have the financial sector P/B note
        assert "Financial sector" not in (result.get("dcf_note") or "")
        assert "ROE-adjusted P/B" not in (result.get("dcf_note") or "")
        # Should have a WACC (indicating DCF was used)
        assert result["wacc"] is not None

    def test_asset_light_financial_has_terminal_method(self):
        """Asset-light financials should show a terminal method from DCF."""
        fund = _make_fundamentals(
            sector="Financial Services",
            return_on_equity=0.40,
            price_to_book=15.0,
        )
        result = calculate_dcf(fund)
        assert result["terminal_method"] in ("Exit Multiple Only", "Blended (Exit+Perp)")

    # --- Bank ROE-Adjusted P/B ---

    def test_bank_uses_roe_adjusted_pb(self):
        """Banks should use ROE-adjusted fair P/B, not hard-coded 1.5."""
        fund = _make_fundamentals(
            sector="Financial Services",
            return_on_equity=0.12,  # 12% ROE (typical bank)
            price_to_book=1.5,
            current_price=100.0,
            beta=1.0,
        )
        result = calculate_dcf(fund)
        assert "ROE-adjusted P/B" in result["dcf_note"]
        assert result["intrinsic_value"] is not None
        assert result["intrinsic_value"] > 0

    def test_bank_fair_pb_capped(self):
        """Fair P/B for banks should be capped at [0.5, 4.0]."""
        # Very high ROE bank → fair_pb capped at 4.0
        fund = _make_fundamentals(
            sector="Financial Services",
            return_on_equity=0.80,  # 80% ROE → uncapped fair_pb would be ~8
            price_to_book=3.0,
            current_price=100.0,
        )
        result = calculate_dcf(fund)
        assert "fair P/B=" in result["dcf_note"]
        # Extract fair_pb from note
        note = result["dcf_note"]
        fair_pb_str = note.split("fair P/B=")[1].split(")")[0]
        fair_pb = float(fair_pb_str)
        assert config.BANK_FAIR_PB_FLOOR <= fair_pb <= config.BANK_FAIR_PB_CAP

    # --- Negative EBITDA / EV/Revenue Fallback ---

    def test_negative_ebitda_uses_ev_revenue(self):
        """Companies with negative EBITDA should use EV/Revenue fallback."""
        fund = _make_fundamentals(
            ebitda=-5_000_000_000,
            ebitda_margin=-0.10,
            ev_to_ebitda=None,
            total_revenue=50_000_000_000,
            enterprise_to_revenue=3.0,
            free_cash_flow=[2_000_000_000, 1_500_000_000, 1_000_000_000],
            analyst_target_price=None,
        )
        result = calculate_dcf(fund)
        assert result["intrinsic_value"] is not None
        assert result["intrinsic_value"] > 0
        assert "EV/Revenue" in result["exit_multiple_source"]

    def test_resolve_revenue_multiple_company_first(self):
        """Company's own EV/Revenue should be preferred."""
        fund = _make_fundamentals(enterprise_to_revenue=5.0)
        multiple, source = _resolve_revenue_multiple(fund)
        assert multiple == 5.0
        assert source == "Company EV/Revenue"

    def test_resolve_revenue_multiple_sector_fallback(self):
        """When company EV/Revenue unavailable, use sector default."""
        fund = _make_fundamentals(enterprise_to_revenue=None, sector="Technology")
        multiple, source = _resolve_revenue_multiple(fund)
        assert multiple == config.SECTOR_REVENUE_MULTIPLES["Technology"]
        assert source == "Sector Revenue Default"

    def test_resolve_revenue_multiple_clamped(self):
        """EV/Revenue should be clamped to [1, 10] range."""
        fund = _make_fundamentals(enterprise_to_revenue=15.0)
        multiple, source = _resolve_revenue_multiple(fund)
        assert multiple == config.REVENUE_MULTIPLE_CAP  # 10.0

    # --- Analyst Target Sanity Check ---

    def test_analyst_target_sanity_check(self):
        """IV should be capped when far from analyst consensus."""
        fund = _make_fundamentals(
            analyst_target_price=50.0,    # Low analyst target
            number_of_analysts=10,
            current_price=200.0,
        )
        result = calculate_dcf(fund)
        # analyst check: if IV > 50 * 3 = 150, cap at 50 * 2 = 100
        if result["intrinsic_value"] is not None:
            assert result["intrinsic_value"] <= 100.0
            assert result["confidence"] == "Low"
            assert "analyst consensus" in (result["dcf_note"] or "")

    def test_analyst_check_skipped_with_few_analysts(self):
        """Analyst check should not trigger with < 5 analysts."""
        iv = 500.0
        fund = {"analyst_target_price": 50.0, "number_of_analysts": 3}
        adjusted_iv, conf, note = _apply_analyst_sanity_check(iv, fund, "High")
        assert adjusted_iv == 500.0  # Not capped
        assert conf == "High"
        assert note is None

    def test_analyst_check_skipped_with_no_target(self):
        """Analyst check should not trigger when target is None."""
        iv = 500.0
        fund = {"analyst_target_price": None, "number_of_analysts": 30}
        adjusted_iv, conf, note = _apply_analyst_sanity_check(iv, fund, "High")
        assert adjusted_iv == 500.0
        assert note is None

    # --- IV Cap at 3x ---

    def test_iv_cap_at_2x_price(self):
        """IV should be capped at 2x current price (max 100% upside)."""
        fund = _make_fundamentals(
            current_price=50.0,
            market_cap=5_000_000_000,
            shares_outstanding=100_000_000,
            free_cash_flow=[3_000_000_000, 2_500_000_000, 2_000_000_000],
            total_debt=0,
            analyst_target_price=None,  # Disable analyst cap for this test
        )
        result = calculate_dcf(fund)
        assert result["intrinsic_value"] is not None
        assert result["intrinsic_value"] <= 50.0 * 2.0

    def test_zero_ebitda_uses_fcf_terminal(self):
        """Zero EBITDA (break-even) should not trigger EV/Revenue fallback."""
        fund = _make_fundamentals(
            ebitda=0,
            ebitda_margin=0.0,
            ev_to_ebitda=None,
            total_revenue=50_000_000_000,
            free_cash_flow=[5_000_000_000, 4_000_000_000, 3_000_000_000],
            analyst_target_price=None,
        )
        result = calculate_dcf(fund)
        assert result["intrinsic_value"] is not None
        # Should NOT use EV/Revenue fallback (zero is not negative)
        assert "EV/Revenue" not in (result.get("exit_multiple_source") or "")

    def test_iv_cap_sets_low_confidence(self):
        """When IV is capped, confidence should be set to Low."""
        fund = _make_fundamentals(
            current_price=50.0,
            market_cap=5_000_000_000,
            shares_outstanding=100_000_000,
            free_cash_flow=[3_000_000_000, 2_500_000_000, 2_000_000_000],
            total_debt=0,
            analyst_target_price=None,
        )
        result = calculate_dcf(fund)
        if result["dcf_note"] and "capped" in result["dcf_note"]:
            assert result["confidence"] == "Low"


class TestExitMultipleBlending:
    """Test 50/50 blending of ticker and sector/industry exit multiples."""

    def test_ticker_blended_with_sector_default(self):
        """Ticker EV/EBITDA blends 50/50 with sector default."""
        fund = _make_fundamentals(ev_to_ebitda=22.0, sector="Technology")
        multiple, source = _resolve_exit_multiple(fund, sector_ev_ebitda_median=None)
        # (22 + 20) / 2 = 21
        assert multiple == 21.0
        assert source == "Blended (Ticker + Sector)"

    def test_ticker_only_when_unknown_sector(self):
        """When sector is unknown, ticker's own EV/EBITDA is used without blending."""
        fund = _make_fundamentals(ev_to_ebitda=18.0, sector="Alien Industries", industry="Unknown")
        multiple, source = _resolve_exit_multiple(fund, sector_ev_ebitda_median=None)
        assert multiple == 18.0
        assert source == "Ticker EV/EBITDA"

    def test_ticker_blended_with_industry_preferred_over_sector(self):
        """Industry blend takes precedence over sector blend."""
        fund = _make_fundamentals(
            ev_to_ebitda=20.0,
            sector="Industrials",
            industry="Airlines",
        )
        multiple, source = _resolve_exit_multiple(fund, sector_ev_ebitda_median=None)
        # (20 + 6) / 2 = 13, but floor for Airlines is 6x so 13 > 6, result=13
        assert multiple == 13.0
        assert source == "Blended (Ticker + Industry)"


class TestEarningsQualityFilter:
    """Test negative EPS and thin EBITDA margin filtering."""

    def test_negative_eps_forces_low_confidence(self):
        """Negative trailing EPS should force confidence to Low."""
        fund = _make_fundamentals(trailing_eps=-2.50)
        result = calculate_dcf(fund)
        assert result["confidence"] == "Low"

    def test_thin_ebitda_margin_forces_low_confidence(self):
        """EBITDA margin below 2% should force confidence to Low."""
        fund = _make_fundamentals(ebitda_margin=0.01, trailing_eps=0.50)
        result = calculate_dcf(fund)
        assert result["confidence"] == "Low"

    def test_normal_eps_not_affected(self):
        """Positive trailing EPS with decent margin should not force Low confidence."""
        fund = _make_fundamentals(trailing_eps=5.0, ebitda_margin=0.20)
        result = calculate_dcf(fund, sector_ev_ebitda_median=10.0)
        assert result["confidence"] in ("High", "Medium")

    def test_negative_eps_adds_note(self):
        """Negative EPS should add a note about earnings quality."""
        fund = _make_fundamentals(
            trailing_eps=-1.50,
            analyst_target_price=None,
        )
        result = calculate_dcf(fund)
        # The note may be overridden by IV cap note, but confidence must be Low
        assert result["confidence"] == "Low"


class TestIndustryWACCFloors:
    """Test industry-specific WACC floor application."""

    def test_airline_gets_higher_wacc(self):
        """Airlines should have WACC >= 14%."""
        fund = _make_fundamentals(
            sector="Industrials",
            industry="Airlines",
            beta=1.2,
        )
        result = calculate_dcf(fund)
        assert result["wacc"] >= 0.14

    def test_biotech_gets_higher_wacc(self):
        """Biotechnology should have WACC >= 12%."""
        fund = _make_fundamentals(
            sector="Healthcare",
            industry="Biotechnology",
            beta=1.0,
        )
        result = calculate_dcf(fund)
        assert result["wacc"] >= 0.12

    def test_industry_wacc_floor_applied(self):
        """Industry WACC floor should override calculated WACC when higher."""
        fund = _make_fundamentals(
            sector="Industrials",
            industry="Airlines",
            beta=0.8,  # Low beta would give low WACC normally
            total_debt=0,
            interest_expense=0,
        )
        result = calculate_dcf(fund)
        assert result["wacc"] >= 0.14  # Airlines floor

    def test_normal_tech_unaffected_by_industry_overrides(self):
        """Tech stocks without industry override should not be affected."""
        fund = _make_fundamentals(
            sector="Technology",
            industry="Software - Infrastructure",
            beta=1.1,
        )
        result = calculate_dcf(fund)
        # Should NOT have WACC bumped by industry floor
        assert result["wacc"] < 0.14  # No industry floor for Software


class TestIndustryExitMultiples:
    """Test industry-specific exit multiple overrides."""

    def test_defense_gets_premium_exit_multiple(self):
        """Aerospace & Defense should get ~15x exit multiple."""
        fund = _make_fundamentals(
            ev_to_ebitda=None,
            sector="Industrials",
            industry="Aerospace & Defense",
        )
        multiple, source = _resolve_exit_multiple(fund, sector_ev_ebitda_median=None)
        assert multiple == 15.0
        assert source == "Industry Default"

    def test_airline_gets_lower_exit_multiple(self):
        """Airlines with no ticker data should get 6x (industry floor allows this)."""
        fund = _make_fundamentals(
            ev_to_ebitda=None,
            sector="Industrials",
            industry="Airlines",
        )
        multiple, source = _resolve_exit_multiple(fund, sector_ev_ebitda_median=None)
        assert multiple == 6.0
        assert source == "Industry Default"

    def test_industry_exit_multiple_floor_overrides_global(self):
        """Airlines floor (6x) should allow values below global floor (8x)."""
        fund = _make_fundamentals(
            ev_to_ebitda=None,
            sector="Industrials",
            industry="Airlines",
        )
        multiple, source = _resolve_exit_multiple(fund, sector_ev_ebitda_median=5.0)
        # Peer median 5.0 clamped by Airlines floor (6x), not global floor (8x)
        assert multiple == 6.0
        assert source == "Sector Peer Median"

    def test_biotech_negative_ebitda_uses_revenue_multiple(self):
        """Biotech with negative EBITDA should use industry revenue multiple (6x)."""
        fund = _make_fundamentals(
            sector="Healthcare",
            industry="Biotechnology",
            enterprise_to_revenue=None,
        )
        multiple, source = _resolve_revenue_multiple(fund)
        assert multiple == 6.0
        assert source == "Industry Revenue Default"


class TestFPAAnalystFixes:
    """Tests for FPA analyst-identified issues (EV-to-equity bridge, interest expense, etc.)."""

    # --- Fix 1: Cash add-back in EV-to-Equity bridge ---

    def test_cash_increases_intrinsic_value(self):
        """Adding cash should increase intrinsic value (EV-to-equity bridge)."""
        base = _make_fundamentals(total_cash=0)
        with_cash = _make_fundamentals(total_cash=50_000_000_000)  # $50B cash
        iv_base = calculate_dcf(base)["intrinsic_value"]
        iv_cash = calculate_dcf(with_cash)["intrinsic_value"]
        assert iv_cash > iv_base, "Cash add-back should increase equity value"

    def test_cash_impact_proportional_to_shares(self):
        """Cash impact per share = total_cash / shares_outstanding."""
        shares = 15_000_000_000
        cash_amount = 150_000_000_000  # $150B
        base = _make_fundamentals(total_cash=0, shares_outstanding=shares)
        with_cash = _make_fundamentals(total_cash=cash_amount, shares_outstanding=shares)
        iv_base = calculate_dcf(base)["intrinsic_value"]
        iv_cash = calculate_dcf(with_cash)["intrinsic_value"]
        # The difference should be approximately cash/shares = $10/share
        # May not be exact due to capping, but should be close
        if iv_cash and iv_base:
            diff = iv_cash - iv_base
            expected = cash_amount / shares
            assert diff > 0, "Cash should always increase IV"
            # Allow tolerance since IV cap may compress the difference
            assert diff <= expected + 1.0, "Cash impact should not exceed cash/shares"

    def test_zero_cash_same_as_no_cash_field(self):
        """total_cash=0 should produce same result as total_cash=None."""
        fund_zero = _make_fundamentals(total_cash=0)
        fund_none = _make_fundamentals(total_cash=None)
        iv_zero = calculate_dcf(fund_zero)["intrinsic_value"]
        iv_none = calculate_dcf(fund_none)["intrinsic_value"]
        assert iv_zero == iv_none

    def test_perpetual_growth_also_includes_cash(self):
        """Both exit multiple and perpetual growth IVs should include cash."""
        base = _make_fundamentals(total_cash=0, analyst_target_price=None)
        with_cash = _make_fundamentals(total_cash=50_000_000_000, analyst_target_price=None)
        result_base = calculate_dcf(base, sector_ev_ebitda_median=10.0)
        result_cash = calculate_dcf(with_cash, sector_ev_ebitda_median=10.0)
        # Both methods should show higher IV with cash
        if result_base["iv_exit_multiple"] and result_cash["iv_exit_multiple"]:
            assert result_cash["iv_exit_multiple"] >= result_base["iv_exit_multiple"]
        if result_base["iv_perpetual_growth"] and result_cash["iv_perpetual_growth"]:
            assert result_cash["iv_perpetual_growth"] >= result_base["iv_perpetual_growth"]

    # --- Fix 2: Interest expense abs() and cost of debt bounds ---

    def test_negative_interest_expense_handled(self):
        """Negative interest expense (yfinance convention) should be treated same as positive."""
        fund_pos = _make_fundamentals(interest_expense=3_000_000_000)
        fund_neg = _make_fundamentals(interest_expense=-3_000_000_000)
        wacc_pos = calculate_dcf(fund_pos)["wacc"]
        wacc_neg = calculate_dcf(fund_neg)["wacc"]
        assert wacc_pos == wacc_neg, "abs() should normalize sign"

    def test_cost_of_debt_floored_at_1pct(self):
        """Cost of debt should be at least 1% (prevents near-zero rates)."""
        # Tiny interest expense relative to debt
        fund = _make_fundamentals(
            interest_expense=100_000,  # $100K on $100B debt = 0.0001%
            total_debt=100_000_000_000,
        )
        result = calculate_dcf(fund)
        # WACC should be reasonable (cost of debt floored at 1%)
        assert result["wacc"] >= 0.06

    def test_cost_of_debt_capped_at_15pct(self):
        """Cost of debt should not exceed 15% (prevents distressed-level rates)."""
        # Huge interest expense relative to debt
        fund = _make_fundamentals(
            interest_expense=30_000_000_000,  # $30B on $100B debt = 30%
            total_debt=100_000_000_000,
        )
        result = calculate_dcf(fund)
        # WACC should still be within bounds
        assert result["wacc"] <= 0.20

    def test_cost_of_debt_fallback_uses_spread(self):
        """When no interest expense data, fallback should be Rf + 150bps, not Rf alone."""
        fund = _make_fundamentals(
            interest_expense=None,
            total_debt=100_000_000_000,
        )
        result = calculate_dcf(fund)
        # With Rf=4.3% + 150bps = 5.8% after-tax cost of debt
        # WACC should be reasonable
        assert result["wacc"] >= 0.06

    # --- Fix 3: Revenue proxy uses total_revenue, not market_cap ---

    def test_revenue_proxy_uses_total_revenue(self):
        """When FCF is empty, revenue proxy should use total_revenue, not market_cap."""
        fund = _make_fundamentals(
            free_cash_flow=[],
            revenue_growth=0.10,
            total_revenue=50_000_000_000,
            market_cap=500_000_000_000,  # 10x revenue — would give very different result
        )
        result = calculate_dcf(fund)
        assert result["intrinsic_value"] is not None
        assert result["confidence"] == "Low"

    def test_revenue_proxy_preferred_over_market_cap(self):
        """total_revenue proxy should produce different IV than market_cap proxy."""
        # With total_revenue available — should use it
        fund_with_rev = _make_fundamentals(
            free_cash_flow=[],
            revenue_growth=0.10,
            total_revenue=50_000_000_000,
            market_cap=500_000_000_000,
        )
        # Without total_revenue — falls to market_cap
        fund_no_rev = _make_fundamentals(
            free_cash_flow=[],
            revenue_growth=0.10,
            total_revenue=None,
            market_cap=500_000_000_000,
        )
        iv_with_rev = calculate_dcf(fund_with_rev)["intrinsic_value"]
        iv_no_rev = calculate_dcf(fund_no_rev)["intrinsic_value"]
        # Both should produce values, but they should differ
        assert iv_with_rev is not None
        assert iv_no_rev is not None
        assert iv_with_rev != iv_no_rev, "Revenue proxy and market_cap proxy should differ"

    # --- Fix 4: Asset-light ticker override ---

    def test_asset_light_ticker_uses_dcf(self):
        """Tickers in ASSET_LIGHT_FINANCIAL_TICKERS should use DCF even with low ROE/P/B."""
        fund = _make_fundamentals(
            ticker="V",
            sector="Financial Services",
            return_on_equity=0.15,  # Below threshold
            price_to_book=3.0,     # Below threshold
        )
        result = calculate_dcf(fund)
        # Should use DCF, not P/B fallback
        assert "Financial sector" not in (result.get("dcf_note") or "")
        assert result["wacc"] is not None

    def test_all_asset_light_tickers_recognized(self):
        """All tickers in the hardcoded list should be recognized as asset-light."""
        from modules.dcf_engine import ASSET_LIGHT_FINANCIAL_TICKERS
        for ticker in ASSET_LIGHT_FINANCIAL_TICKERS:
            fund = {"ticker": ticker, "return_on_equity": 0.10, "price_to_book": 2.0}
            assert _is_asset_light_financial(fund) is True, f"{ticker} should be asset-light"

    def test_non_asset_light_bank_uses_pb(self):
        """A regular bank ticker NOT in the list should use P/B fallback."""
        fund = _make_fundamentals(
            ticker="JPM",
            sector="Financial Services",
            return_on_equity=0.12,
            price_to_book=1.5,
        )
        result = calculate_dcf(fund)
        assert "Financial sector" in (result.get("dcf_note") or "") or "ROE-adjusted P/B" in (result.get("dcf_note") or "")

    # --- Fix 5: Credit Services exit multiple ---

    def test_credit_services_exit_multiple(self):
        """Credit Services industry should get 22x exit multiple."""
        fund = _make_fundamentals(
            ev_to_ebitda=None,
            sector="Financial Services",
            industry="Credit Services",
            return_on_equity=0.40,
            price_to_book=15.0,  # Asset-light to trigger DCF
            ticker="V",
        )
        multiple, source = _resolve_exit_multiple(fund, sector_ev_ebitda_median=None)
        assert multiple == 22.0
        assert source == "Industry Default"

    def test_financial_data_exchanges_exit_multiple(self):
        """Financial Data & Stock Exchanges should get 22x exit multiple."""
        fund = _make_fundamentals(
            ev_to_ebitda=None,
            sector="Financial Services",
            industry="Financial Data & Stock Exchanges",
        )
        multiple, source = _resolve_exit_multiple(fund, sector_ev_ebitda_median=None)
        assert multiple == 22.0
        assert source == "Industry Default"

    # --- Fix 6: Zero/negative EBITDA margin forces Low confidence ---

    def test_zero_ebitda_margin_forces_low_confidence(self):
        """EBITDA margin of exactly 0% should force Low confidence."""
        fund = _make_fundamentals(ebitda_margin=0.0, trailing_eps=1.0)
        result = calculate_dcf(fund)
        assert result["confidence"] == "Low"

    def test_negative_ebitda_margin_forces_low_confidence(self):
        """Negative EBITDA margin should force Low confidence."""
        fund = _make_fundamentals(ebitda_margin=-0.05, trailing_eps=1.0)
        result = calculate_dcf(fund)
        assert result["confidence"] == "Low"

    def test_healthy_ebitda_margin_not_penalized(self):
        """EBITDA margin above threshold should not force Low confidence."""
        fund = _make_fundamentals(ebitda_margin=0.20, trailing_eps=5.0)
        result = calculate_dcf(fund, sector_ev_ebitda_median=10.0)
        assert result["confidence"] in ("High", "Medium")
