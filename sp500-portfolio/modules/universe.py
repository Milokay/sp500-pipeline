"""
S&P 500 ticker universe fetcher.
Fetches and maintains the current list of S&P 500 tickers with sector/industry metadata.
"""

import logging
from io import StringIO

import pandas as pd
import requests

from modules import cache

logger = logging.getLogger(__name__)

# Hardcoded fallback list (subset - used if Wikipedia scrape fails)
FALLBACK_TICKERS = [
    {"ticker": "AAPL", "company_name": "Apple Inc.", "sector": "Information Technology", "sub_industry": "Technology Hardware, Storage & Peripherals"},
    {"ticker": "MSFT", "company_name": "Microsoft Corporation", "sector": "Information Technology", "sub_industry": "Systems Software"},
    {"ticker": "AMZN", "company_name": "Amazon.com Inc.", "sector": "Consumer Discretionary", "sub_industry": "Broadline Retail"},
    {"ticker": "NVDA", "company_name": "NVIDIA Corporation", "sector": "Information Technology", "sub_industry": "Semiconductors"},
    {"ticker": "GOOGL", "company_name": "Alphabet Inc. Class A", "sector": "Communication Services", "sub_industry": "Interactive Media & Services"},
    {"ticker": "META", "company_name": "Meta Platforms Inc.", "sector": "Communication Services", "sub_industry": "Interactive Media & Services"},
    {"ticker": "BRK-B", "company_name": "Berkshire Hathaway Inc.", "sector": "Financials", "sub_industry": "Multi-Sector Holdings"},
    {"ticker": "JPM", "company_name": "JPMorgan Chase & Co.", "sector": "Financials", "sub_industry": "Diversified Banks"},
    {"ticker": "JNJ", "company_name": "Johnson & Johnson", "sector": "Health Care", "sub_industry": "Pharmaceuticals"},
    {"ticker": "V", "company_name": "Visa Inc.", "sector": "Financials", "sub_industry": "Transaction & Payment Processing Services"},
    {"ticker": "XOM", "company_name": "Exxon Mobil Corporation", "sector": "Energy", "sub_industry": "Integrated Oil & Gas"},
    {"ticker": "PG", "company_name": "Procter & Gamble Co.", "sector": "Consumer Staples", "sub_industry": "Household Products"},
    {"ticker": "UNH", "company_name": "UnitedHealth Group Inc.", "sector": "Health Care", "sub_industry": "Managed Health Care"},
    {"ticker": "MA", "company_name": "Mastercard Inc.", "sector": "Financials", "sub_industry": "Transaction & Payment Processing Services"},
    {"ticker": "HD", "company_name": "The Home Depot Inc.", "sector": "Consumer Discretionary", "sub_industry": "Home Improvement Retail"},
    {"ticker": "CVX", "company_name": "Chevron Corporation", "sector": "Energy", "sub_industry": "Integrated Oil & Gas"},
    {"ticker": "MRK", "company_name": "Merck & Co. Inc.", "sector": "Health Care", "sub_industry": "Pharmaceuticals"},
    {"ticker": "ABBV", "company_name": "AbbVie Inc.", "sector": "Health Care", "sub_industry": "Biotechnology"},
    {"ticker": "PEP", "company_name": "PepsiCo Inc.", "sector": "Consumer Staples", "sub_industry": "Soft Drinks & Non-alcoholic Beverages"},
    {"ticker": "KO", "company_name": "The Coca-Cola Company", "sector": "Consumer Staples", "sub_industry": "Soft Drinks & Non-alcoholic Beverages"},
    {"ticker": "LLY", "company_name": "Eli Lilly and Company", "sector": "Health Care", "sub_industry": "Pharmaceuticals"},
    {"ticker": "COST", "company_name": "Costco Wholesale Corporation", "sector": "Consumer Staples", "sub_industry": "Hypermarkets & Super Centers"},
    {"ticker": "WMT", "company_name": "Walmart Inc.", "sector": "Consumer Staples", "sub_industry": "Hypermarkets & Super Centers"},
    {"ticker": "DIS", "company_name": "The Walt Disney Company", "sector": "Communication Services", "sub_industry": "Movies & Entertainment"},
    {"ticker": "CSCO", "company_name": "Cisco Systems Inc.", "sector": "Information Technology", "sub_industry": "Communications Equipment"},
    {"ticker": "VZ", "company_name": "Verizon Communications Inc.", "sector": "Communication Services", "sub_industry": "Integrated Telecommunication Services"},
    {"ticker": "INTC", "company_name": "Intel Corporation", "sector": "Information Technology", "sub_industry": "Semiconductors"},
    {"ticker": "CRM", "company_name": "Salesforce Inc.", "sector": "Information Technology", "sub_industry": "Application Software"},
    {"ticker": "BA", "company_name": "The Boeing Company", "sector": "Industrials", "sub_industry": "Aerospace & Defense"},
    {"ticker": "NKE", "company_name": "NIKE Inc.", "sector": "Consumer Discretionary", "sub_industry": "Footwear"},
]


def get_sp500_tickers() -> pd.DataFrame:
    """
    Fetch the current list of S&P 500 tickers with sector/industry metadata.

    Strategy:
    1. Check SQLite cache first
    2. Scrape Wikipedia table
    3. Fall back to hardcoded list if scrape fails

    Returns DataFrame with columns: [ticker, company_name, sector, sub_industry]
    """
    # Check cache first
    if cache.is_cache_fresh("ticker_universe", "ALL"):
        cached_data = cache.get_all_cached("ticker_universe")
        if cached_data:
            df = pd.DataFrame(cached_data)
            # Drop cache metadata columns if present
            df = df[[c for c in ["ticker", "company_name", "sector", "sub_industry"] if c in df.columns]]
            logger.info(f"Loaded {len(df)} tickers from cache")
            return df

    # Try Wikipedia scrape
    try:
        logger.info("Fetching S&P 500 tickers from Wikipedia...")
        # Use requests with a proper User-Agent to avoid 403 Forbidden
        headers = {
            "User-Agent": "SP500PortfolioTool/1.0 (educational project)"
        }
        response = requests.get(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        tables = pd.read_html(StringIO(response.text))
        df = tables[0]

        # Map columns
        column_mapping = {
            "Symbol": "ticker",
            "Security": "company_name",
            "GICS Sector": "sector",
            "GICS Sub-Industry": "sub_industry",
        }
        df = df.rename(columns=column_mapping)
        df = df[["ticker", "company_name", "sector", "sub_industry"]]

        # Clean tickers: replace '.' with '-' for yfinance compatibility
        df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)

        # Remove any duplicates
        df = df.drop_duplicates(subset="ticker")

        # Cache all tickers
        _cache_universe(df)

        logger.info(f"Fetched {len(df)} tickers from Wikipedia")
        return df

    except Exception as e:
        logger.warning(f"Wikipedia scrape failed: {e}. Using fallback ticker list.")
        df = pd.DataFrame(FALLBACK_TICKERS)
        _cache_universe(df)
        return df


def _cache_universe(df: pd.DataFrame) -> None:
    """Cache the ticker universe to SQLite."""
    # Cache a sentinel row to track freshness
    cache.set_cached("ticker_universe", "ALL", {
        "company_name": "SENTINEL",
        "sector": "ALL",
        "sub_industry": "ALL",
    })

    # Cache each ticker
    for _, row in df.iterrows():
        cache.set_cached("ticker_universe", row["ticker"], {
            "company_name": row["company_name"],
            "sector": row["sector"],
            "sub_industry": row["sub_industry"],
        })


def get_sector_tickers(sector: str) -> list[str]:
    """Get all tickers in a specific sector."""
    df = get_sp500_tickers()
    return df[df["sector"] == sector]["ticker"].tolist()


def get_ticker_sector(ticker: str) -> str:
    """Look up the sector for a single ticker."""
    df = get_sp500_tickers()
    match = df[df["ticker"] == ticker]
    if match.empty:
        return "Unknown"
    return match.iloc[0]["sector"]
