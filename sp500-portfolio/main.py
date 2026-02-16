"""
S&P 500 Portfolio Decision-Making Tool
Main orchestrator — fetches data, runs analysis, generates Excel report.

Usage:
    python main.py                              # Full 500-ticker run
    python main.py --tickers AAPL,MSFT,JPM      # Specific tickers only
    python main.py --refresh                     # Force refresh cached data
    python main.py --output path/to/output.xlsx  # Custom output path
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone

from modules import cache
from modules.universe import get_sp500_tickers
from modules.fundamentals import fetch_fundamentals_batch
from modules.price_data import fetch_price_history, fetch_price_history_bulk
from modules.dcf_engine import calculate_dcf
from modules.relative_valuation import calculate_all_relative_valuations
from modules.technicals import calculate_technicals
from modules.signals import generate_signal
from excel_builder.builder import build_excel_report

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="S&P 500 Portfolio Decision-Making Tool"
    )
    parser.add_argument(
        '--refresh', action='store_true',
        help='Force refresh all cached data'
    )
    parser.add_argument(
        '--tickers', type=str, default=None,
        help='Comma-separated list of tickers to analyze (e.g., AAPL,MSFT,JPM)'
    )
    parser.add_argument(
        '--source', type=str, default='yfinance',
        choices=['yfinance'],
        help='Data source (default: yfinance)'
    )
    parser.add_argument(
        '--output', type=str, default=None,
        help='Custom output path for Excel report'
    )
    return parser.parse_args()


def _compute_sector_ev_ebitda_medians(all_fundamentals: dict) -> dict:
    """Compute median EV/EBITDA per sector from all fundamentals data."""
    from statistics import median
    sector_values = {}
    for fund in all_fundamentals.values():
        sector = fund.get("sector", "Unknown")
        ev_ebitda = fund.get("ev_to_ebitda")
        if ev_ebitda is not None and isinstance(ev_ebitda, (int, float)) and 1.0 < ev_ebitda < 100.0:
            sector_values.setdefault(sector, []).append(ev_ebitda)

    return {
        sector: median(values)
        for sector, values in sector_values.items()
        if len(values) >= 3
    }


def main():
    args = parse_args()
    start_time = time.time()

    print("=" * 60)
    print("  S&P 500 Portfolio Decision-Making Tool")
    print("=" * 60)
    print()

    # Phase 0: Initialize
    cache.init_db()

    if args.refresh:
        print("Clearing cache (--refresh flag)...")
        cache.clear_cache()

    # Phase 1: Get ticker universe
    print("Phase 1: Loading ticker universe...")
    phase_start = time.time()

    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(',')]
        print(f"  Using custom ticker list: {', '.join(tickers)}")
    else:
        ticker_df = get_sp500_tickers()
        tickers = ticker_df["ticker"].tolist()
        print(f"  Loaded {len(tickers)} S&P 500 tickers")

    print(f"  Phase 1 complete ({time.time() - phase_start:.1f}s)")
    print()

    # Phase 2: Fetch fundamentals
    print(f"Phase 2: Fetching fundamentals for {len(tickers)} tickers...")
    phase_start = time.time()
    all_fundamentals = fetch_fundamentals_batch(tickers)
    print(f"  Phase 2 complete ({time.time() - phase_start:.1f}s)")
    print()

    # Phase 3: Fetch price data
    print(f"Phase 3: Fetching price data for {len(tickers)} tickers...")
    phase_start = time.time()
    all_prices = fetch_price_history_bulk(tickers)
    print(f"  Phase 3 complete ({time.time() - phase_start:.1f}s)")
    print()

    # Phase 4: Run analysis
    print(f"Phase 4: Running analysis for {len(tickers)} tickers...")
    phase_start = time.time()

    # Calculate relative valuations (needs all fundamentals at once)
    all_relative = calculate_all_relative_valuations(all_fundamentals)

    # Compute sector median EV/EBITDA for Exit Multiple terminal value
    sector_medians = _compute_sector_ev_ebitda_medians(all_fundamentals)
    logger.info(f"Sector EV/EBITDA medians: {len(sector_medians)} sectors computed")

    results = []
    failures = []

    for ticker in tickers:
        try:
            fund = all_fundamentals.get(ticker, {})
            if not fund or fund.get('error'):
                failures.append((ticker, fund.get('error', 'No fundamentals data')))
                continue

            # DCF (with sector median EV/EBITDA for exit multiple)
            sector = fund.get('sector', 'Unknown')
            sector_median = sector_medians.get(sector)
            dcf = calculate_dcf(fund, sector_ev_ebitda_median=sector_median)

            # Relative valuation (already calculated)
            rel = all_relative.get(ticker, {})

            # Technicals
            price_df = all_prices.get(ticker)
            tech = calculate_technicals(price_df)

            # Signal
            sig = generate_signal(dcf, rel, tech)

            # IMPORTANT: Merge results with tech_ prefix for technicals to avoid key collision
            # Both fundamentals and technicals have 'current_price' key
            tech_prefixed = {f"tech_{k}": v for k, v in tech.items()}

            merged = {**fund, **dcf, **rel, **tech_prefixed, **sig}
            results.append(merged)

        except Exception as e:
            logger.error(f"{ticker}: analysis failed: {e}")
            failures.append((ticker, str(e)))

    print(f"  Analyzed: {len(results)} tickers")
    if failures:
        print(f"  Failed: {len(failures)} tickers")
    print(f"  Phase 4 complete ({time.time() - phase_start:.1f}s)")
    print()

    # Phase 5: Generate Excel report
    if not results:
        print("ERROR: No results to report. Exiting.")
        cache.close_db()
        sys.exit(1)

    print("Phase 5: Generating Excel report...")
    phase_start = time.time()

    if args.output:
        output_path = args.output
    else:
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        output_path = f"data/output/sp500_analysis_{timestamp}.xlsx"

    report_path = build_excel_report(results, output_path)
    file_size_kb = os.path.getsize(report_path) / 1024
    print(f"  Report saved: {report_path} ({file_size_kb:.1f} KB)")
    print(f"  Phase 5 complete ({time.time() - phase_start:.1f}s)")
    print()

    # Console Summary
    _print_summary(results, failures, report_path, start_time)

    cache.close_db()


def _print_summary(results, failures, report_path, start_time):
    """Print a console summary of analysis results."""
    print("=" * 60)
    print("  ANALYSIS SUMMARY")
    print("=" * 60)
    print()

    # Total stocks
    print(f"Total stocks analyzed: {len(results)}")
    if failures:
        print(f"Failed: {len(failures)}")
    print()

    # Signal distribution
    signal_counts = {}
    for r in results:
        # Clean signal (remove Low Confidence suffix)
        sig = r.get('signal', 'HOLD')
        clean_sig = sig.replace(' (Low Confidence)', '')
        signal_counts[clean_sig] = signal_counts.get(clean_sig, 0) + 1

    print("Signal Distribution:")
    for sig_name in ['STRONG BUY', 'BUY', 'HOLD', 'SELL', 'STRONG SELL']:
        count = signal_counts.get(sig_name, 0)
        bar = '#' * count
        print(f"  {sig_name:>12}: {count:>3} {bar}")
    print()

    # Top 10 by conviction (buy-side)
    buy_results = [r for r in results
                   if r.get('signal', '').replace(' (Low Confidence)', '') in ('STRONG BUY', 'BUY')]
    buy_results.sort(key=lambda r: (-r.get('conviction', 0), -(r.get('upside_pct') or 0)))

    if buy_results:
        print("Top 10 Buy Signals (by conviction):")
        for r in buy_results[:10]:
            ticker = r.get('ticker', '?')
            signal = r.get('signal', '?')
            conv = r.get('conviction', 0)
            upside = r.get('upside_pct')
            upside_str = f"{upside*100:+.1f}%" if upside is not None else "N/A"
            price = r.get('current_price')
            price_str = f"${price:.2f}" if price else "N/A"
            print(f"  {ticker:>6}: {signal:>15} | Conv: {conv}/5 | Upside: {upside_str:>8} | Price: {price_str}")
        print()

    # Data quality
    high_conf = sum(1 for r in results if r.get('confidence') == 'High')
    med_conf = sum(1 for r in results if r.get('confidence') == 'Medium')
    low_conf = sum(1 for r in results if r.get('confidence') == 'Low')
    print(f"Data Quality: High={high_conf}, Medium={med_conf}, Low={low_conf}")

    # Failures
    if failures:
        print()
        print(f"Failed tickers ({len(failures)}):")
        for ticker, error in failures[:10]:
            print(f"  {ticker}: {error[:60]}")
        if len(failures) > 10:
            print(f"  ... and {len(failures) - 10} more")

    elapsed = time.time() - start_time
    print()
    print(f"Total time: {elapsed:.1f}s")
    print(f"Report: {report_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
