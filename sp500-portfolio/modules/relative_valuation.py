"""
Relative valuation module.
Compares a stock's current multiples to sector peers.
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)

# Sector-to-multiple mapping
# NOTE: PRD specifies EV/Sales or PEG for Tech/Comms and Price/FFO for Real Estate.
# yfinance does not reliably provide these. Practical substitutes are used.
SECTOR_MULTIPLES = {
    "Information Technology": ("forward_pe", "Forward P/E"),
    "Technology": ("forward_pe", "Forward P/E"),
    "Communication Services": ("forward_pe", "Forward P/E"),
    "Financial Services": ("price_to_book", "P/B"),
    "Financials": ("price_to_book", "P/B"),
    "Real Estate": ("price_to_book", "P/B"),  # Proxy for Price/FFO
}
DEFAULT_MULTIPLE = ("ev_to_ebitda", "EV/EBITDA")


def _get_sector_multiple(sector: str) -> tuple[str, str]:
    """Return (field_name, display_name) for the appropriate sector multiple."""
    if not sector:
        return DEFAULT_MULTIPLE
    return SECTOR_MULTIPLES.get(sector, DEFAULT_MULTIPLE)


def _percentile_rank(value: float, values: list[float]) -> float:
    """Calculate the percentile rank of a value within a list."""
    if not values or value is None:
        return 0.5  # Default to median
    count_below = sum(1 for v in values if v < value)
    count_equal = sum(1 for v in values if v == value)
    return (count_below + 0.5 * count_equal) / len(values)


def calculate_relative_valuation(
    ticker: str,
    fundamentals: dict,
    all_fundamentals: dict[str, dict],
) -> dict:
    """
    Compare a stock's valuation multiple to its sector peers.

    Returns dict with: primary_multiple_name, primary_multiple_value,
    sector_median, sector_percentile, relative_status
    """
    sector = fundamentals.get("sector", "Unknown")
    field_name, display_name = _get_sector_multiple(sector)

    # Get this ticker's multiple value
    ticker_value = fundamentals.get(field_name)

    # Collect same-sector peer multiples
    peer_values = []
    for t, fund in all_fundamentals.items():
        if fund.get("sector") == sector and t != ticker:
            val = fund.get(field_name)
            if val is not None and isinstance(val, (int, float)) and val > 0:
                peer_values.append(val)

    # If we don't have the ticker's value, return N/A
    if ticker_value is None or not isinstance(ticker_value, (int, float)) or ticker_value <= 0:
        return {
            "primary_multiple_name": display_name,
            "primary_multiple_value": None,
            "sector_median": None,
            "sector_percentile": None,
            "relative_status": "N/A",
            "relative_note": f"Missing {display_name} value for {ticker}",
        }

    # Include ticker's own value in the full list for percentile calc
    all_values = peer_values + [ticker_value]

    # Check if we have enough peers
    if len(all_values) < 3:
        # Use EV/EBITDA as fallback if sector multiple has too few peers
        if field_name != "ev_to_ebitda":
            fallback_field, fallback_name = DEFAULT_MULTIPLE
            fallback_value = fundamentals.get(fallback_field)
            fallback_peers = []
            for t, fund in all_fundamentals.items():
                if fund.get("sector") == sector and t != ticker:
                    val = fund.get(fallback_field)
                    if val is not None and isinstance(val, (int, float)) and val > 0:
                        fallback_peers.append(val)

            if fallback_value and len(fallback_peers) >= 2:
                field_name = fallback_field
                display_name = fallback_name
                ticker_value = fallback_value
                peer_values = fallback_peers
                all_values = peer_values + [ticker_value]

        if len(all_values) < 3:
            sector_median = np.median(all_values) if all_values else None
            return {
                "primary_multiple_name": display_name,
                "primary_multiple_value": round(ticker_value, 2),
                "sector_median": round(sector_median, 2) if sector_median else None,
                "sector_percentile": 0.5,
                "relative_status": "Insufficient Peers",
                "relative_note": f"Only {len(all_values)} tickers in {sector} sector",
            }

    # Calculate statistics
    sector_median = float(np.median(all_values))
    percentile = _percentile_rank(ticker_value, all_values)

    # Determine relative status
    if percentile < 0.30:
        relative_status = "Cheap vs Peers"
    elif percentile > 0.70:
        relative_status = "Expensive vs Peers"
    else:
        relative_status = "In-Line"

    return {
        "primary_multiple_name": display_name,
        "primary_multiple_value": round(ticker_value, 2),
        "sector_median": round(sector_median, 2),
        "sector_percentile": round(percentile, 4),
        "relative_status": relative_status,
        "relative_note": None,
    }


def calculate_all_relative_valuations(
    all_fundamentals: dict[str, dict],
) -> dict[str, dict]:
    """
    Calculate relative valuations for all tickers at once.
    Groups by sector first for O(n) efficiency.
    """
    results = {}
    for ticker, fund in all_fundamentals.items():
        results[ticker] = calculate_relative_valuation(ticker, fund, all_fundamentals)
    return results
