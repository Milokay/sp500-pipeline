"""Unit tests for technical analysis module."""

import pytest
import numpy as np
import pandas as pd

from modules.technicals import (
    calculate_bollinger_bands,
    calculate_rsi,
    calculate_performance_metrics,
    calculate_technicals,
)


# --- Fixtures: synthetic price data ---

def _make_price_df(prices: list[float]) -> pd.DataFrame:
    """Create a price DataFrame from a list of close prices."""
    dates = pd.date_range("2025-01-01", periods=len(prices), freq="B")
    return pd.DataFrame(
        {
            "Open": prices,
            "High": [p * 1.01 for p in prices],
            "Low": [p * 0.99 for p in prices],
            "Close": prices,
            "Volume": [1_000_000] * len(prices),
        },
        index=dates,
    )


def _make_constant_price_df(price: float = 100.0, n: int = 50) -> pd.DataFrame:
    """Create a DataFrame with constant close prices (SMA == price, std == 0)."""
    return _make_price_df([price] * n)


def _make_rising_price_df(start: float = 100.0, n: int = 50) -> pd.DataFrame:
    """Create a steadily rising price series."""
    prices = [start + i * 0.5 for i in range(n)]
    return _make_price_df(prices)


def _make_falling_price_df(start: float = 200.0, n: int = 50) -> pd.DataFrame:
    """Create a steadily falling price series."""
    prices = [start - i * 0.5 for i in range(n)]
    return _make_price_df(prices)


class TestBollingerBands:
    """Test Bollinger Bands calculation."""

    def test_constant_price_sma_equals_price(self):
        """With constant prices, SMA should equal the price."""
        df = _make_constant_price_df(100.0)
        result = calculate_bollinger_bands(df)
        assert result["sma_20"] == 100.0

    def test_constant_price_percent_b(self):
        """With constant prices, std=0, so percent_b should be 0.5 (edge case)."""
        df = _make_constant_price_df(100.0)
        result = calculate_bollinger_bands(df)
        assert result["percent_b"] == 0.5

    def test_upper_gt_sma_gt_lower(self):
        """Upper band should be > SMA > Lower band for varying prices."""
        df = _make_rising_price_df()
        result = calculate_bollinger_bands(df)
        assert result["upper_band"] > result["sma_20"]
        assert result["sma_20"] > result["lower_band"]

    def test_band_position_upper_half(self):
        """Rising prices should be in the Upper Half."""
        df = _make_rising_price_df()
        result = calculate_bollinger_bands(df)
        # Last price is highest, so should be in upper half or above
        assert result["band_position"] in ("Upper Half", "Above Upper")

    def test_band_position_lower_half(self):
        """Falling prices should be in the Lower Half or Below."""
        df = _make_falling_price_df()
        result = calculate_bollinger_bands(df)
        assert result["band_position"] in ("Lower Half", "Below Lower")

    def test_percent_b_range(self):
        """Percent B should be in a reasonable range for normal data."""
        df = _make_rising_price_df()
        result = calculate_bollinger_bands(df)
        assert -1.0 <= result["percent_b"] <= 2.0

    def test_bandwidth_positive(self):
        """Bandwidth should be positive for varying prices."""
        df = _make_rising_price_df()
        result = calculate_bollinger_bands(df)
        assert result["bandwidth"] > 0

    def test_price_vs_bands(self):
        """price_vs_upper and price_vs_lower should be floats."""
        df = _make_rising_price_df()
        result = calculate_bollinger_bands(df)
        assert isinstance(result["price_vs_upper"], float)
        assert isinstance(result["price_vs_lower"], float)

    def test_exactly_20_rows(self):
        """With exactly 20 rows, should still calculate (minimum window)."""
        df = _make_price_df([100 + i for i in range(20)])
        result = calculate_bollinger_bands(df)
        assert result["sma_20"] is not None
        assert result["band_position"] != "N/A"

    def test_fewer_than_20_rows_returns_na(self):
        """With fewer than 20 rows, should return all None with N/A position."""
        df = _make_price_df([100 + i for i in range(15)])
        result = calculate_bollinger_bands(df)
        assert result["sma_20"] is None
        assert result["upper_band"] is None
        assert result["lower_band"] is None
        assert result["band_position"] == "N/A"

    def test_none_input_returns_na(self):
        """None DataFrame should return N/A."""
        result = calculate_bollinger_bands(None)
        assert result["band_position"] == "N/A"
        assert result["current_price"] is None

    def test_empty_df_returns_na(self):
        """Empty DataFrame should return N/A."""
        df = pd.DataFrame()
        result = calculate_bollinger_bands(df)
        assert result["band_position"] == "N/A"

    def test_valid_band_position_strings(self):
        """band_position should always be one of the 5 valid strings."""
        for df_func in [_make_rising_price_df, _make_falling_price_df, _make_constant_price_df]:
            df = df_func()
            result = calculate_bollinger_bands(df)
            assert result["band_position"] in (
                "Above Upper", "Upper Half", "Lower Half", "Below Lower", "N/A"
            )


class TestRSI:
    """Test RSI calculation."""

    def test_all_gains_near_100(self):
        """Steadily rising prices should give RSI near 100."""
        df = _make_rising_price_df(100, 50)
        rsi = calculate_rsi(df)
        assert rsi > 90

    def test_all_losses_near_0(self):
        """Steadily falling prices should give RSI near 0."""
        df = _make_falling_price_df(200, 50)
        rsi = calculate_rsi(df)
        assert rsi < 10

    def test_constant_price_neutral(self):
        """Constant prices should give RSI at neutral point."""
        # With no price changes, gains=losses=0, should return neutral
        df = _make_constant_price_df(100, 50)
        rsi = calculate_rsi(df)
        # With zero gains and zero losses, RSI is undefined but we handle it
        assert 0 <= rsi <= 100

    def test_rsi_range(self):
        """RSI should always be between 0 and 100."""
        for df_func in [_make_rising_price_df, _make_falling_price_df]:
            df = df_func()
            rsi = calculate_rsi(df)
            assert 0 <= rsi <= 100

    def test_insufficient_data_returns_50(self):
        """With insufficient data, should return 50.0 (neutral)."""
        df = _make_price_df([100, 101, 102])  # Only 3 rows, need 15
        rsi = calculate_rsi(df)
        assert rsi == 50.0

    def test_none_input_returns_50(self):
        """None input should return 50.0."""
        assert calculate_rsi(None) == 50.0

    def test_empty_df_returns_50(self):
        """Empty DataFrame should return 50.0."""
        assert calculate_rsi(pd.DataFrame()) == 50.0

    def test_custom_period(self):
        """Custom period should work."""
        df = _make_rising_price_df(100, 50)
        rsi_7 = calculate_rsi(df, period=7)
        rsi_14 = calculate_rsi(df, period=14)
        # Both should be valid
        assert 0 <= rsi_7 <= 100
        assert 0 <= rsi_14 <= 100


class TestCalculateTechnicals:
    """Test the combined calculate_technicals function."""

    def test_returns_bollinger_plus_rsi(self):
        """Should return bollinger dict with an added rsi field."""
        df = _make_rising_price_df()
        result = calculate_technicals(df)
        # Should have all bollinger keys
        assert "current_price" in result
        assert "sma_20" in result
        assert "upper_band" in result
        assert "lower_band" in result
        assert "percent_b" in result
        assert "bandwidth" in result
        assert "band_position" in result
        # Should also have RSI
        assert "rsi" in result
        assert 0 <= result["rsi"] <= 100

    def test_insufficient_data_has_rsi(self):
        """Even with insufficient data for bands, RSI should be present."""
        df = _make_price_df([100 + i for i in range(5)])
        result = calculate_technicals(df)
        assert result["band_position"] == "N/A"
        assert "rsi" in result

    def test_none_input(self):
        """None input should return valid structure with defaults."""
        result = calculate_technicals(None)
        assert result["band_position"] == "N/A"
        assert result["rsi"] == 50.0

    def test_performance_metrics_keys_present(self):
        """calculate_technicals should include performance metric keys."""
        df = _make_rising_price_df(n=300)
        result = calculate_technicals(df)
        for key in ['return_1m', 'return_6m', 'return_1y', 'std_dev_52w', 'sharpe_52w']:
            assert key in result


class TestPerformanceMetrics:
    """Test portfolio performance metrics calculation."""

    def test_returns_with_sufficient_data(self):
        """All 4 return periods should be populated with 800+ rows."""
        prices = [100.0 + i * 0.1 for i in range(800)]
        df = _make_price_df(prices)
        result = calculate_performance_metrics(df)
        assert result['return_1m'] is not None
        assert result['return_6m'] is not None
        assert result['return_1y'] is not None
        assert result['return_3y'] is not None

    def test_return_3y_none_with_1y_data(self):
        """3-year return should be None when only 1 year of data exists."""
        prices = [100.0 + i * 0.1 for i in range(260)]
        df = _make_price_df(prices)
        result = calculate_performance_metrics(df)
        assert result['return_1y'] is not None
        assert result['return_3y'] is None

    def test_return_1m_positive_for_rising(self):
        """Rising prices should have positive 1M return."""
        prices = [100.0 + i * 0.5 for i in range(50)]
        df = _make_price_df(prices)
        result = calculate_performance_metrics(df)
        assert result['return_1m'] is not None
        assert result['return_1m'] > 0

    def test_sharpe_positive_with_strong_gains(self):
        """Strong gains over 1 year should produce positive Sharpe."""
        # 30% annual return: 100 -> 130 over 252 days
        prices = [100.0 * (1 + 0.30 * i / 300) for i in range(300)]
        df = _make_price_df(prices)
        result = calculate_performance_metrics(df)
        assert result['sharpe_52w'] is not None
        assert result['sharpe_52w'] > 0

    def test_sharpe_negative_with_losses(self):
        """Losses over 1 year should produce negative Sharpe."""
        # -20% annual return: 100 -> 80 over 300 days
        prices = [100.0 * (1 - 0.20 * i / 300) for i in range(300)]
        df = _make_price_df(prices)
        result = calculate_performance_metrics(df)
        assert result['sharpe_52w'] is not None
        assert result['sharpe_52w'] < 0

    def test_std_dev_near_zero_for_constant_price(self):
        """Constant prices should have near-zero std dev."""
        df = _make_constant_price_df(100.0, n=300)
        result = calculate_performance_metrics(df)
        # Constant price → daily returns all 0 → std_dev = 0
        assert result['std_dev_52w'] is not None
        assert result['std_dev_52w'] < 0.001

    def test_std_dev_none_with_insufficient_data(self):
        """Std dev should be None when < 252 rows."""
        prices = [100.0 + i * 0.1 for i in range(100)]
        df = _make_price_df(prices)
        result = calculate_performance_metrics(df)
        assert result['std_dev_52w'] is None
        assert result['sharpe_52w'] is None

    def test_none_input_returns_all_none(self):
        """None input should return dict with all None values."""
        result = calculate_performance_metrics(None)
        assert result['return_1m'] is None
        assert result['std_dev_52w'] is None
        assert result['sharpe_52w'] is None

    def test_empty_df_returns_all_none(self):
        """Empty DataFrame should return dict with all None values."""
        result = calculate_performance_metrics(pd.DataFrame())
        assert result['return_1m'] is None
