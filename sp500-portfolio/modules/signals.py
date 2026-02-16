"""
Signal generation module.
Combines fundamental and technical analysis into actionable signals.
"""

import logging
import config

logger = logging.getLogger(__name__)


def generate_signal(dcf_result: dict, relative_result: dict, technical_result: dict) -> dict:
    """
    Combine DCF, relative valuation, and technical analysis into a trading signal.

    Input dicts:
    - dcf_result: {intrinsic_value, buy_price, upside_pct, wacc, fcf_growth_rate, valuation_status, confidence, dcf_note}
      valuation_status is one of: "Undervalued", "Fair Value", "Overvalued", "Insufficient Data"
    - relative_result: {primary_multiple_name, primary_multiple_value, sector_median, sector_percentile, relative_status, relative_note}
      relative_status is one of: "Cheap vs Peers", "In-Line", "Expensive vs Peers", "Insufficient Peers", "N/A"
    - technical_result: {current_price, sma_20, upper_band, lower_band, percent_b, bandwidth, price_vs_upper, price_vs_lower, band_position, rsi}
      band_position is one of: "Above Upper", "Upper Half", "Lower Half", "Below Lower", "N/A"

    SIGNAL MATRIX (Fundamental × Technical):

    Undervalued + Below Lower Band = STRONG BUY
    Undervalued + Between Bands    = BUY         (Between = Upper Half or Lower Half)
    Undervalued + Above Upper Band = HOLD
    Fair Value  + Below Lower Band = BUY
    Fair Value  + Between Bands    = HOLD
    Fair Value  + Above Upper Band = SELL
    Overvalued  + Below Lower Band = HOLD
    Overvalued  + Between Bands    = SELL
    Overvalued  + Above Upper Band = STRONG SELL

    If valuation_status is "Insufficient Data", default signal to "HOLD"
    If band_position is "N/A", treat as "Between Bands"

    RSI Modifiers (applied AFTER matrix lookup):
    - If RSI < 30 AND signal is "BUY" -> upgrade to "STRONG BUY"
    - If RSI > 70 AND signal is "SELL" -> upgrade to "STRONG SELL"

    Low confidence modifier:
    - If dcf confidence is "Low", append " (Low Confidence)" to signal string

    Conviction Score (integer 1-5):
    - Start at 3 (neutral)
    - Undervalued: +1, Overvalued: -1
    - Near lower band (percent_b < 0.2): +1, Near upper band (percent_b > 0.8): -1
    - RSI confirms direction (RSI < 30 for buy signals, RSI > 70 for sell signals): +1
    - Cheap vs Peers: +1, Expensive vs Peers: -1
    - Cap between 1 and 5

    Rationale: Human-readable string explaining the signal.
    Format example: "STRONG BUY: Trading 35% below intrinsic value ($180 vs $277). Price near lower Bollinger Band ($175). RSI oversold at 28. Cheap vs sector peers (25th percentile EV/EBITDA)."

    Returns:
    {
        'signal': str,           # "STRONG BUY" | "BUY" | "HOLD" | "SELL" | "STRONG SELL" (possibly with " (Low Confidence)")
        'conviction': int,       # 1-5
        'rationale': str,        # Human-readable explanation
        'entry_price': float,    # Lower Bollinger Band (suggested entry)
        'exit_price': float,     # Upper Bollinger Band (suggested exit)
        'target_price': float,   # DCF intrinsic value
    }

    Edge cases:
    - If any input dict is None, use safe defaults (valuation_status="Insufficient Data", band_position="N/A", etc.)
    - If technical values are None (e.g., insufficient price data), entry_price and exit_price should be None
    - If intrinsic_value is None, target_price should be None
    """

    # Handle None inputs with safe defaults
    if dcf_result is None:
        dcf_result = {}
    if relative_result is None:
        relative_result = {}
    if technical_result is None:
        technical_result = {}

    # Extract DCF values
    valuation_status = dcf_result.get('valuation_status', 'Insufficient Data')
    intrinsic_value = dcf_result.get('intrinsic_value')
    buy_price = dcf_result.get('buy_price')
    upside_pct = dcf_result.get('upside_pct')
    confidence = dcf_result.get('confidence', 'Medium')

    # Extract relative valuation values
    relative_status = relative_result.get('relative_status', 'N/A')
    sector_percentile = relative_result.get('sector_percentile')
    primary_multiple_name = relative_result.get('primary_multiple_name', 'N/A')

    # Extract technical values
    band_position = technical_result.get('band_position', 'N/A')
    current_price = technical_result.get('current_price')
    lower_band = technical_result.get('lower_band')
    upper_band = technical_result.get('upper_band')
    percent_b = technical_result.get('percent_b')
    rsi = technical_result.get('rsi')

    # Treat "N/A" band position as "Between Bands"
    if band_position == 'N/A':
        band_position = 'Between Bands'

    # Normalize "Upper Half" or "Lower Half" to "Between Bands" for matrix lookup
    between_bands = band_position in ['Upper Half', 'Lower Half', 'Between Bands']

    # SIGNAL MATRIX LOOKUP
    signal = "HOLD"  # default

    if valuation_status == "Insufficient Data":
        signal = "HOLD"
    elif valuation_status == "Undervalued":
        if band_position == "Below Lower":
            signal = "STRONG BUY"
        elif between_bands:
            signal = "BUY"
        elif band_position == "Above Upper":
            signal = "HOLD"
    elif valuation_status == "Fair Value":
        if band_position == "Below Lower":
            signal = "BUY"
        elif between_bands:
            signal = "HOLD"
        elif band_position == "Above Upper":
            signal = "SELL"
    elif valuation_status == "Overvalued":
        if band_position == "Below Lower":
            signal = "HOLD"
        elif between_bands:
            signal = "SELL"
        elif band_position == "Above Upper":
            signal = "STRONG SELL"

    # RSI MODIFIERS (applied after matrix lookup)
    if rsi is not None:
        if rsi < 30 and signal == "BUY":
            signal = "STRONG BUY"
        elif rsi > 70 and signal == "SELL":
            signal = "STRONG SELL"

    # LOW CONFIDENCE MODIFIER
    if confidence == "Low":
        signal = f"{signal} (Low Confidence)"

    # CONVICTION SCORE (1-5)
    conviction = 3  # neutral starting point

    # Fundamental conviction
    if valuation_status == "Undervalued":
        conviction += 1
    elif valuation_status == "Overvalued":
        conviction -= 1

    # Technical band position
    if percent_b is not None:
        if percent_b < 0.2:
            conviction += 1
        elif percent_b > 0.8:
            conviction -= 1

    # RSI confirmation
    if rsi is not None:
        if signal.startswith("BUY") or signal.startswith("STRONG BUY"):
            if rsi < 30:
                conviction += 1
        elif signal.startswith("SELL") or signal.startswith("STRONG SELL"):
            if rsi > 70:
                conviction += 1

    # Relative valuation
    if relative_status == "Cheap vs Peers":
        conviction += 1
    elif relative_status == "Expensive vs Peers":
        conviction -= 1

    # Cap conviction between 1 and 5
    conviction = max(1, min(5, conviction))

    # BUILD RATIONALE
    rationale_parts = []

    # Clean signal for rationale (remove confidence suffix)
    clean_signal = signal.replace(" (Low Confidence)", "")
    rationale_parts.append(f"{clean_signal}:")

    # DCF component
    if intrinsic_value is not None and current_price is not None and upside_pct is not None:
        direction = "below" if upside_pct > 0 else "above"
        abs_upside = abs(upside_pct) * 100
        rationale_parts.append(
            f"Trading {abs_upside:.0f}% {direction} intrinsic value "
            f"(${current_price:.2f} vs ${intrinsic_value:.2f})."
        )
    elif valuation_status != "Insufficient Data":
        rationale_parts.append(f"Valuation: {valuation_status}.")

    # Technical component
    if lower_band is not None and upper_band is not None:
        if band_position == "Below Lower":
            rationale_parts.append(f"Price near lower Bollinger Band (${lower_band:.2f}).")
        elif band_position == "Above Upper":
            rationale_parts.append(f"Price near upper Bollinger Band (${upper_band:.2f}).")
        else:
            rationale_parts.append(f"Price between Bollinger Bands (${lower_band:.2f}-${upper_band:.2f}).")

    # RSI component
    if rsi is not None:
        if rsi < 30:
            rationale_parts.append(f"RSI oversold at {rsi:.0f}.")
        elif rsi > 70:
            rationale_parts.append(f"RSI overbought at {rsi:.0f}.")
        else:
            rationale_parts.append(f"RSI at {rsi:.0f}.")

    # Relative valuation component
    if relative_status == "Cheap vs Peers" and sector_percentile is not None:
        rationale_parts.append(
            f"Cheap vs sector peers ({sector_percentile * 100:.0f}th percentile {primary_multiple_name})."
        )
    elif relative_status == "Expensive vs Peers" and sector_percentile is not None:
        rationale_parts.append(
            f"Expensive vs sector peers ({sector_percentile * 100:.0f}th percentile {primary_multiple_name})."
        )
    elif relative_status == "In-Line":
        rationale_parts.append("In-line with sector peers.")

    rationale = " ".join(rationale_parts)

    # RETURN VALUES
    return {
        'signal': signal,
        'conviction': conviction,
        'rationale': rationale,
        'entry_price': lower_band,
        'exit_price': upper_band,
        'target_price': intrinsic_value,
    }
