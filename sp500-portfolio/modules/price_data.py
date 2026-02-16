"""
Historical OHLCV price data fetcher.
Fetches daily price data for technical analysis using yfinance.
"""

import json
import logging
import time

import pandas as pd
import yfinance as yf
from tqdm import tqdm

from modules import cache

logger = logging.getLogger(__name__)


def fetch_price_history(ticker: str, period: str = "5y") -> pd.DataFrame:
    """
    Fetch historical daily OHLCV data for a single ticker.

    Returns DataFrame with columns: Open, High, Low, Close, Volume
    Index is DatetimeIndex sorted ascending.
    """
    # Check cache first
    if cache.is_cache_fresh("price_history", ticker):
        cached = cache.get_cached("price_history", ticker)
        if cached:
            try:
                df = pd.DataFrame(json.loads(cached) if isinstance(cached, str) else cached)
                if "_json_data" in cached:
                    df = pd.read_json(cached["_json_data"])
                else:
                    df = pd.DataFrame(cached)
                    if "Date" in df.columns:
                        df["Date"] = pd.to_datetime(df["Date"])
                        df = df.set_index("Date")
                    elif "date" in df.columns:
                        df["date"] = pd.to_datetime(df["date"])
                        df = df.set_index("date")
                        df.index.name = "Date"
                df = df.sort_index()
                logger.info(f"{ticker}: loaded {len(df)} rows from cache")
                return df
            except Exception as e:
                logger.warning(f"{ticker}: cache deserialization failed: {e}, re-fetching")

    logger.info(f"{ticker}: fetching price history from yfinance...")
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)

        if df is None or df.empty:
            logger.warning(f"{ticker}: no price data returned")
            return pd.DataFrame()

        # Ensure we have the required columns
        required_cols = ["Open", "High", "Low", "Close", "Volume"]
        for col in required_cols:
            if col not in df.columns:
                logger.warning(f"{ticker}: missing column '{col}'")

        # Keep only required columns (drop Dividends, Stock Splits if present)
        available_cols = [c for c in required_cols if c in df.columns]
        df = df[available_cols]

        # Drop rows with NaN Close prices
        if "Close" in df.columns:
            df = df.dropna(subset=["Close"])

        # Sort by date ascending
        df = df.sort_index()

        # Warn if insufficient data for Bollinger Bands
        if len(df) < 20:
            logger.warning(f"{ticker}: only {len(df)} rows (need 20+ for Bollinger Bands)")

        # Cache the data
        _cache_price_data(ticker, df)

        time.sleep(0.3)  # Rate limiting
        return df

    except Exception as e:
        logger.error(f"{ticker}: price fetch failed: {e}")
        time.sleep(0.3)
        return pd.DataFrame()


def fetch_price_history_bulk(
    tickers: list[str], period: str = "5y"
) -> dict[str, pd.DataFrame]:
    """
    Bulk download price history for multiple tickers.
    Uses yf.download() for efficiency, falls back to individual fetches.
    """
    results = {}

    try:
        logger.info(f"Bulk downloading price data for {len(tickers)} tickers...")
        data = yf.download(
            tickers, period=period, group_by="ticker", threads=True, progress=False
        )

        if data is not None and not data.empty:
            for ticker in tqdm(tickers, desc="Processing price data"):
                try:
                    if len(tickers) == 1:
                        # Single ticker: data is not multi-level
                        ticker_df = data.copy()
                    else:
                        # Multi-ticker: extract by ticker from multi-level columns
                        if ticker in data.columns.get_level_values(0):
                            ticker_df = data[ticker].copy()
                        else:
                            logger.warning(f"{ticker}: not found in bulk download")
                            ticker_df = pd.DataFrame()

                    if not ticker_df.empty:
                        # Drop NaN Close rows
                        if "Close" in ticker_df.columns:
                            ticker_df = ticker_df.dropna(subset=["Close"])

                        # Keep only required columns
                        required_cols = ["Open", "High", "Low", "Close", "Volume"]
                        available = [c for c in required_cols if c in ticker_df.columns]
                        ticker_df = ticker_df[available]
                        ticker_df = ticker_df.sort_index()

                        # Cache individually
                        _cache_price_data(ticker, ticker_df)
                        results[ticker] = ticker_df
                    else:
                        results[ticker] = pd.DataFrame()

                except Exception as e:
                    logger.warning(f"{ticker}: bulk processing error: {e}")
                    results[ticker] = pd.DataFrame()
        else:
            raise ValueError("Bulk download returned empty data")

    except Exception as e:
        logger.warning(f"Bulk download failed: {e}. Falling back to individual fetches.")
        for ticker in tqdm(tickers, desc="Fetching price data individually"):
            results[ticker] = fetch_price_history(ticker, period=period)

    return results


def _cache_price_data(ticker: str, df: pd.DataFrame) -> None:
    """Cache price DataFrame to SQLite as JSON."""
    if df.empty:
        return

    # Convert to serializable format
    cache_data = {
        "Date": [d.isoformat() for d in df.index],
    }
    for col in df.columns:
        cache_data[col] = df[col].tolist()

    cache.set_cached("price_history", ticker, cache_data)
