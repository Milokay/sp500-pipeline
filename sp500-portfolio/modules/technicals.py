"""
Technical analysis module.
Calculates Bollinger Bands and RSI from price data.
"""

import logging
import numpy as np
import pandas as pd
import config

logger = logging.getLogger(__name__)


def calculate_bollinger_bands(price_df: pd.DataFrame) -> dict:
    """
    Calculate Bollinger Bands from price DataFrame.

    Input: DataFrame with 'Close' column, at least 20 rows

    Calculations:
    - SMA_20 = price_df['Close'].rolling(window=20).mean()
    - STD_20 = price_df['Close'].rolling(window=20).std()
    - Upper_Band = SMA_20 + (BOLLINGER_STD_DEV * STD_20)
    - Lower_Band = SMA_20 - (BOLLINGER_STD_DEV * STD_20)
    - %B = (Current_Price - Lower_Band) / (Upper_Band - Lower_Band)
    - Bandwidth = (Upper_Band - Lower_Band) / SMA_20

    Use the LAST row (most recent) for all returned values.
    - price_vs_upper = (current - upper) / upper
    - price_vs_lower = (current - lower) / lower
    - band_position: "Above Upper" if %B > 1, "Upper Half" if 0.5-1, "Lower Half" if 0-0.5, "Below Lower" if %B < 0

    Returns dict with: current_price, sma_20, upper_band, lower_band, percent_b, bandwidth,
    price_vs_upper, price_vs_lower, band_position

    Edge cases:
    - If price_df is None or empty or has fewer than BOLLINGER_WINDOW rows, return dict with all None values and band_position="N/A"
    - If upper == lower (zero bandwidth), set percent_b to 0.5
    """
    # Initialize result dictionary with None values
    result = {
        'current_price': None,
        'sma_20': None,
        'upper_band': None,
        'lower_band': None,
        'percent_b': None,
        'bandwidth': None,
        'price_vs_upper': None,
        'price_vs_lower': None,
        'band_position': 'N/A'
    }

    # Handle edge cases
    if price_df is None or price_df.empty or len(price_df) < config.BOLLINGER_WINDOW:
        logger.warning(f"Insufficient data for Bollinger Bands calculation. Need at least {config.BOLLINGER_WINDOW} rows.")
        return result

    # Calculate SMA and Standard Deviation
    sma_20 = price_df['Close'].rolling(window=config.BOLLINGER_WINDOW).mean()
    std_20 = price_df['Close'].rolling(window=config.BOLLINGER_WINDOW).std()

    # Calculate Bollinger Bands
    upper_band = sma_20 + (config.BOLLINGER_STD_DEV * std_20)
    lower_band = sma_20 - (config.BOLLINGER_STD_DEV * std_20)

    # Get most recent values
    current_price = float(price_df['Close'].iloc[-1])
    sma_val = float(sma_20.iloc[-1])
    upper_val = float(upper_band.iloc[-1])
    lower_val = float(lower_band.iloc[-1])

    # Calculate %B
    if upper_val == lower_val:
        # Zero bandwidth edge case
        percent_b = 0.5
    else:
        percent_b = (current_price - lower_val) / (upper_val - lower_val)

    # Calculate Bandwidth
    bandwidth = (upper_val - lower_val) / sma_val

    # Calculate price vs bands
    price_vs_upper = (current_price - upper_val) / upper_val
    price_vs_lower = (current_price - lower_val) / lower_val

    # Determine band position
    if percent_b > 1:
        band_position = "Above Upper"
    elif percent_b >= 0.5:
        band_position = "Upper Half"
    elif percent_b >= 0:
        band_position = "Lower Half"
    else:
        band_position = "Below Lower"

    # Build result dictionary with rounded values
    result = {
        'current_price': round(current_price, 2),
        'sma_20': round(sma_val, 2),
        'upper_band': round(upper_val, 2),
        'lower_band': round(lower_val, 2),
        'percent_b': round(percent_b, 4),
        'bandwidth': round(bandwidth, 4),
        'price_vs_upper': round(price_vs_upper, 4),
        'price_vs_lower': round(price_vs_lower, 4),
        'band_position': band_position
    }

    return result


def calculate_rsi(price_df: pd.DataFrame, period: int = None) -> float:
    """
    Calculate RSI (Relative Strength Index).

    Default period from config.RSI_PERIOD (14).

    RSI = 100 - (100 / (1 + RS))
    RS = Average Gain over period / Average Loss over period

    Use Wilder's smoothing (exponential moving average):
    - First avg_gain = mean of gains over first `period` days
    - First avg_loss = mean of losses over first `period` days
    - Subsequent: avg_gain = (prev_avg_gain * (period-1) + current_gain) / period
    - Same for avg_loss

    Returns most recent RSI value (0-100).

    Edge cases:
    - If price_df is None or empty or has fewer than period+1 rows, return 50.0 (neutral)
    - If avg_loss is 0 (all gains), return 100.0
    - If avg_gain is 0 (all losses), return 0.0
    """
    if period is None:
        period = config.RSI_PERIOD

    # Handle edge cases
    if price_df is None or price_df.empty or len(price_df) < period + 1:
        logger.warning(f"Insufficient data for RSI calculation. Need at least {period + 1} rows.")
        return 50.0

    # Calculate price changes
    delta = price_df['Close'].diff()

    # Separate gains and losses
    gain = delta.copy()
    loss = delta.copy()
    gain[gain < 0] = 0
    loss[loss > 0] = 0
    loss = abs(loss)

    # Calculate first average gain and loss (simple mean of first period)
    avg_gain = gain.iloc[1:period+1].mean()
    avg_loss = loss.iloc[1:period+1].mean()

    # Apply Wilder's smoothing for subsequent values
    for i in range(period + 1, len(price_df)):
        current_gain = gain.iloc[i]
        current_loss = loss.iloc[i]

        avg_gain = (avg_gain * (period - 1) + current_gain) / period
        avg_loss = (avg_loss * (period - 1) + current_loss) / period

    # Calculate RSI
    if avg_loss == 0:
        # All gains, no losses
        return 100.0
    elif avg_gain == 0:
        # All losses, no gains
        return 0.0
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)


def calculate_performance_metrics(price_df: pd.DataFrame) -> dict:
    """
    Calculate portfolio performance metrics from price history.

    Returns dict with:
      return_1m, return_6m, return_1y, return_3y: simple price returns
      std_dev_52w: annualized standard deviation of daily returns (252 trading days)
      sharpe_52w: 52-week Sharpe ratio = (annualized return - Rf) / annualized std dev

    Edge cases:
      - If insufficient data for a return period, that metric is None
      - If std_dev is 0 or None, Sharpe is None
    """
    result = {
        'return_1m': None,
        'return_6m': None,
        'return_1y': None,
        'return_3y': None,
        'std_dev_52w': None,
        'sharpe_52w': None,
    }

    if price_df is None or price_df.empty or 'Close' not in price_df.columns:
        return result

    closes = price_df['Close']
    current_price = float(closes.iloc[-1])
    n = len(closes)

    # --- Return calculations (simple price return) ---
    periods = {
        'return_1m': 21,
        'return_6m': 126,
        'return_1y': 252,
        'return_3y': 756,
    }
    for key, trading_days in periods.items():
        if n > trading_days:
            past_price = float(closes.iloc[-(trading_days + 1)])
            if past_price > 0:
                result[key] = round((current_price - past_price) / past_price, 4)

    # --- 52-week Standard Deviation (annualized) ---
    # Need 253 prices to get 252 daily returns via pct_change()
    if n >= 253:
        daily_returns = closes.iloc[-253:].pct_change().dropna()
        if len(daily_returns) > 1:
            daily_std = float(daily_returns.std())
            annualized_std = daily_std * np.sqrt(252)
            result['std_dev_52w'] = round(annualized_std, 4)

            # --- 52-week Sharpe Ratio ---
            if result['return_1y'] is not None and annualized_std > 0:
                sharpe = (result['return_1y'] - config.RISK_FREE_RATE) / annualized_std
                result['sharpe_52w'] = round(sharpe, 2)

    return result


def calculate_technicals(price_df: pd.DataFrame) -> dict:
    """
    Combine Bollinger Bands, RSI, and performance metrics into a single result dict.
    """
    result = calculate_bollinger_bands(price_df)
    result['rsi'] = calculate_rsi(price_df)
    perf = calculate_performance_metrics(price_df)
    result.update(perf)
    return result
