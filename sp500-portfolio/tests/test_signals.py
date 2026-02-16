"""Unit tests for signal generation module."""

import pytest

from modules.signals import generate_signal


# --- Fixtures: hardcoded result dicts ---

def _make_dcf(status="Fair Value", intrinsic=200.0, upside=0.0, confidence="High"):
    """Create a DCF result dict."""
    return {
        "intrinsic_value": intrinsic,
        "buy_price": intrinsic * 0.75 if intrinsic else None,
        "upside_pct": upside,
        "wacc": 0.09,
        "fcf_growth_rate": 0.08,
        "valuation_status": status,
        "confidence": confidence,
        "dcf_note": None,
    }


def _make_relative(status="In-Line", percentile=0.5, multiple_name="EV/EBITDA"):
    """Create a relative valuation result dict."""
    return {
        "primary_multiple_name": multiple_name,
        "primary_multiple_value": 15.0,
        "sector_median": 14.0,
        "sector_percentile": percentile,
        "relative_status": status,
        "relative_note": None,
    }


def _make_technical(position="Upper Half", price=200.0, rsi=50.0, percent_b=0.6):
    """Create a technical analysis result dict."""
    return {
        "current_price": price,
        "sma_20": 195.0,
        "upper_band": 210.0,
        "lower_band": 180.0,
        "percent_b": percent_b,
        "bandwidth": 0.15,
        "price_vs_upper": -0.05,
        "price_vs_lower": 0.11,
        "band_position": position,
        "rsi": rsi,
    }


class TestSignalMatrix:
    """Test every cell of the 3x3 signal matrix."""

    # Row 1: Undervalued
    def test_undervalued_below_lower(self):
        sig = generate_signal(
            _make_dcf("Undervalued", 280, 0.40),
            _make_relative(),
            _make_technical("Below Lower", 200, 50, -0.1),
        )
        assert sig["signal"] == "STRONG BUY"

    def test_undervalued_between_bands_upper(self):
        sig = generate_signal(
            _make_dcf("Undervalued", 280, 0.40),
            _make_relative(),
            _make_technical("Upper Half", 200, 50, 0.7),
        )
        assert sig["signal"] == "BUY"

    def test_undervalued_between_bands_lower(self):
        sig = generate_signal(
            _make_dcf("Undervalued", 280, 0.40),
            _make_relative(),
            _make_technical("Lower Half", 200, 50, 0.3),
        )
        assert sig["signal"] == "BUY"

    def test_undervalued_above_upper(self):
        sig = generate_signal(
            _make_dcf("Undervalued", 280, 0.40),
            _make_relative(),
            _make_technical("Above Upper", 200, 50, 1.2),
        )
        assert sig["signal"] == "HOLD"

    # Row 2: Fair Value
    def test_fair_value_below_lower(self):
        sig = generate_signal(
            _make_dcf("Fair Value", 200, 0.0),
            _make_relative(),
            _make_technical("Below Lower", 200, 50, -0.1),
        )
        assert sig["signal"] == "BUY"

    def test_fair_value_between_bands(self):
        sig = generate_signal(
            _make_dcf("Fair Value", 200, 0.0),
            _make_relative(),
            _make_technical("Upper Half", 200, 50, 0.6),
        )
        assert sig["signal"] == "HOLD"

    def test_fair_value_above_upper(self):
        sig = generate_signal(
            _make_dcf("Fair Value", 200, 0.0),
            _make_relative(),
            _make_technical("Above Upper", 200, 50, 1.2),
        )
        assert sig["signal"] == "SELL"

    # Row 3: Overvalued
    def test_overvalued_below_lower(self):
        sig = generate_signal(
            _make_dcf("Overvalued", 150, -0.25),
            _make_relative(),
            _make_technical("Below Lower", 200, 50, -0.1),
        )
        assert sig["signal"] == "HOLD"

    def test_overvalued_between_bands(self):
        sig = generate_signal(
            _make_dcf("Overvalued", 150, -0.25),
            _make_relative(),
            _make_technical("Upper Half", 200, 50, 0.6),
        )
        assert sig["signal"] == "SELL"

    def test_overvalued_above_upper(self):
        sig = generate_signal(
            _make_dcf("Overvalued", 150, -0.25),
            _make_relative(),
            _make_technical("Above Upper", 200, 50, 1.2),
        )
        assert sig["signal"] == "STRONG SELL"

    # Insufficient Data
    def test_insufficient_data_defaults_hold(self):
        sig = generate_signal(
            _make_dcf("Insufficient Data", None, None),
            _make_relative(),
            _make_technical("Lower Half", 200, 50, 0.3),
        )
        assert sig["signal"] == "HOLD"


class TestRSIModifiers:
    """Test RSI-based signal upgrades."""

    def test_rsi_below_30_upgrades_buy_to_strong_buy(self):
        """BUY + RSI < 30 should become STRONG BUY."""
        sig = generate_signal(
            _make_dcf("Fair Value", 200, 0.0),
            _make_relative(),
            _make_technical("Below Lower", 200, 25, -0.1),
        )
        assert sig["signal"] == "STRONG BUY"

    def test_rsi_above_70_upgrades_sell_to_strong_sell(self):
        """SELL + RSI > 70 should become STRONG SELL."""
        sig = generate_signal(
            _make_dcf("Fair Value", 200, 0.0),
            _make_relative(),
            _make_technical("Above Upper", 200, 75, 1.2),
        )
        assert sig["signal"] == "STRONG SELL"

    def test_rsi_below_30_does_not_upgrade_hold(self):
        """HOLD should NOT be upgraded by RSI < 30."""
        sig = generate_signal(
            _make_dcf("Overvalued", 150, -0.25),
            _make_relative(),
            _make_technical("Below Lower", 200, 25, -0.1),
        )
        assert sig["signal"] == "HOLD"

    def test_rsi_above_70_does_not_upgrade_hold(self):
        """HOLD should NOT be upgraded by RSI > 70."""
        sig = generate_signal(
            _make_dcf("Undervalued", 280, 0.40),
            _make_relative(),
            _make_technical("Above Upper", 200, 75, 1.2),
        )
        assert sig["signal"] == "HOLD"

    def test_rsi_neutral_no_modifier(self):
        """RSI in 30-70 range should not modify signal."""
        sig = generate_signal(
            _make_dcf("Fair Value", 200, 0.0),
            _make_relative(),
            _make_technical("Below Lower", 200, 50, -0.1),
        )
        assert sig["signal"] == "BUY"  # No upgrade


class TestConviction:
    """Test conviction score calculation."""

    def test_conviction_range(self):
        """Conviction should always be between 1 and 5."""
        # Test many combinations
        for status in ["Undervalued", "Fair Value", "Overvalued"]:
            for pos in ["Below Lower", "Upper Half", "Above Upper"]:
                for rsi in [20, 50, 80]:
                    for rel in ["Cheap vs Peers", "In-Line", "Expensive vs Peers"]:
                        sig = generate_signal(
                            _make_dcf(status, 200, 0.0),
                            _make_relative(rel),
                            _make_technical(pos, 200, rsi),
                        )
                        assert 1 <= sig["conviction"] <= 5, (
                            f"Conviction {sig['conviction']} out of range for "
                            f"{status}/{pos}/RSI={rsi}/{rel}"
                        )

    def test_max_conviction(self):
        """Best case: Undervalued + Below Lower + RSI<30 + Cheap vs Peers = 5."""
        sig = generate_signal(
            _make_dcf("Undervalued", 280, 0.40),
            _make_relative("Cheap vs Peers", 0.15),
            _make_technical("Below Lower", 200, 25, 0.1),
        )
        assert sig["conviction"] == 5

    def test_min_conviction(self):
        """Worst case: Overvalued + Above Upper + RSI>70 + Expensive = 1."""
        sig = generate_signal(
            _make_dcf("Overvalued", 150, -0.25),
            _make_relative("Expensive vs Peers", 0.85),
            _make_technical("Above Upper", 200, 75, 0.9),
        )
        assert sig["conviction"] == 1

    def test_neutral_conviction(self):
        """Fair Value + Between + neutral RSI + In-Line = 3."""
        sig = generate_signal(
            _make_dcf("Fair Value", 200, 0.0),
            _make_relative("In-Line", 0.5),
            _make_technical("Upper Half", 200, 50, 0.6),
        )
        assert sig["conviction"] == 3


class TestLowConfidence:
    """Test low confidence annotation."""

    def test_low_confidence_appended(self):
        """Low confidence should append '(Low Confidence)' to signal."""
        sig = generate_signal(
            _make_dcf("Undervalued", 280, 0.40, confidence="Low"),
            _make_relative(),
            _make_technical("Lower Half", 200, 50, 0.3),
        )
        assert "(Low Confidence)" in sig["signal"]
        assert sig["signal"].startswith("BUY")

    def test_high_confidence_no_suffix(self):
        """High confidence should not add any suffix."""
        sig = generate_signal(
            _make_dcf("Undervalued", 280, 0.40, confidence="High"),
            _make_relative(),
            _make_technical("Lower Half", 200, 50, 0.3),
        )
        assert "(Low Confidence)" not in sig["signal"]


class TestRationale:
    """Test rationale string generation."""

    def test_rationale_non_empty(self):
        """Rationale should always be a non-empty string."""
        sig = generate_signal(
            _make_dcf("Undervalued", 280, 0.40),
            _make_relative(),
            _make_technical("Lower Half", 200, 50, 0.3),
        )
        assert isinstance(sig["rationale"], str)
        assert len(sig["rationale"]) > 10

    def test_rationale_contains_signal(self):
        """Rationale should start with the signal type."""
        sig = generate_signal(
            _make_dcf("Undervalued", 280, 0.40),
            _make_relative(),
            _make_technical("Below Lower", 200, 25, -0.1),
        )
        assert sig["rationale"].startswith("STRONG BUY:")

    def test_rationale_contains_upside_percentage(self):
        """Rationale should mention the upside percentage."""
        sig = generate_signal(
            _make_dcf("Undervalued", 280, 0.40),
            _make_relative(),
            _make_technical("Lower Half", 200, 50, 0.3),
        )
        assert "40%" in sig["rationale"]


class TestReturnValues:
    """Test return dict structure and values."""

    def test_entry_price_is_lower_band(self):
        """entry_price should be the lower Bollinger band."""
        sig = generate_signal(
            _make_dcf(),
            _make_relative(),
            _make_technical("Upper Half", 200, 50, 0.6),
        )
        assert sig["entry_price"] == 180.0

    def test_exit_price_is_upper_band(self):
        """exit_price should be the upper Bollinger band."""
        sig = generate_signal(
            _make_dcf(),
            _make_relative(),
            _make_technical("Upper Half", 200, 50, 0.6),
        )
        assert sig["exit_price"] == 210.0

    def test_target_price_is_intrinsic(self):
        """target_price should be the DCF intrinsic value."""
        sig = generate_signal(
            _make_dcf("Undervalued", 280, 0.40),
            _make_relative(),
            _make_technical(),
        )
        assert sig["target_price"] == 280.0

    def test_entry_lt_exit(self):
        """entry_price should be less than exit_price."""
        sig = generate_signal(
            _make_dcf(),
            _make_relative(),
            _make_technical(),
        )
        assert sig["entry_price"] < sig["exit_price"]


class TestEdgeCases:
    """Test edge cases with None inputs."""

    def test_all_none_inputs(self):
        """All None inputs should return HOLD with conviction 3."""
        sig = generate_signal(None, None, None)
        assert sig["signal"] == "HOLD"
        assert sig["conviction"] == 3
        assert sig["entry_price"] is None
        assert sig["exit_price"] is None
        assert sig["target_price"] is None

    def test_none_dcf(self):
        sig = generate_signal(None, _make_relative(), _make_technical())
        assert sig["signal"] == "HOLD"

    def test_none_relative(self):
        sig = generate_signal(_make_dcf("Undervalued", 280, 0.40), None, _make_technical("Lower Half"))
        assert "BUY" in sig["signal"]

    def test_none_technical(self):
        """None technical should use N/A band position (treated as between)."""
        sig = generate_signal(
            _make_dcf("Undervalued", 280, 0.40),
            _make_relative(),
            None,
        )
        assert sig["signal"] == "BUY"
        assert sig["entry_price"] is None

    def test_na_band_position_treated_as_between(self):
        """N/A band position should be treated as between bands."""
        sig = generate_signal(
            _make_dcf("Undervalued", 280, 0.40),
            _make_relative(),
            _make_technical("N/A", 200, 50, None),
        )
        assert sig["signal"] == "BUY"
