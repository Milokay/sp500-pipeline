"""
Financial statement & ratio fetcher.
Fetches fundamental data for each ticker using yfinance.
"""

import logging
import time

import yfinance as yf
from tqdm import tqdm

from modules import cache

logger = logging.getLogger(__name__)


def _find_row(df, labels):
    """Find a row in a DataFrame by trying multiple label names (partial match)."""
    if df is None or df.empty:
        return None
    for label in labels:
        # Try exact match first
        if label in df.index:
            return df.loc[label]
        # Try partial match
        for idx in df.index:
            if label.lower() in str(idx).lower():
                return df.loc[idx]
    return None


def _safe_float(value, default=None):
    """Safely convert a value to float."""
    if value is None:
        return default
    try:
        result = float(value)
        # Check for NaN/Inf
        if result != result or result == float('inf') or result == float('-inf'):
            return default
        return result
    except (ValueError, TypeError):
        return default


def fetch_fundamentals(ticker: str) -> dict:
    """
    Fetch fundamental data for a single ticker.

    Returns dict with keys: ticker, current_price, market_cap, shares_outstanding,
    beta, sector, trailing_pe, forward_pe, price_to_book, ev_to_ebitda,
    dividend_yield, return_on_assets, return_on_equity, trailing_eps, forward_eps,
    ebitda_margin, net_margin, operating_margin, gross_margin, debt_to_equity,
    current_ratio, operating_cash_flow, capital_expenditures, free_cash_flow,
    total_debt, total_equity, interest_expense, revenue_growth, fetch_timestamp
    """
    # Check cache first
    if cache.is_cache_fresh("fundamentals", ticker):
        cached = cache.get_cached("fundamentals", ticker)
        if cached:
            logger.info(f"{ticker}: loaded from cache")
            return cached

    logger.info(f"{ticker}: fetching from yfinance...")
    result = {
        "ticker": ticker,
        "current_price": None,
        "market_cap": None,
        "shares_outstanding": None,
        "beta": None,
        "sector": None,
        "industry": None,
        "trailing_pe": None,
        "forward_pe": None,
        "price_to_book": None,
        "ev_to_ebitda": None,
        "dividend_yield": None,
        "return_on_assets": None,
        "return_on_equity": None,
        "trailing_eps": None,
        "forward_eps": None,
        "ebitda_margin": None,
        "net_margin": None,
        "operating_margin": None,
        "gross_margin": None,
        "debt_to_equity": None,
        "current_ratio": None,
        "operating_cash_flow": [],
        "capital_expenditures": [],
        "free_cash_flow": [],
        "total_debt": None,
        "total_cash": None,
        "total_equity": None,
        "interest_expense": None,
        "revenue_growth": None,
        "ebitda": None,
        "total_revenue": None,
        "analyst_target_price": None,
        "number_of_analysts": None,
        "enterprise_to_revenue": None,
        "fetch_timestamp": None,
    }

    try:
        stock = yf.Ticker(ticker)

        # === Info (price, ratios, beta, sector) ===
        info = stock.info
        if not info or not isinstance(info, dict):
            logger.warning(f"{ticker}: .info returned empty/invalid")
            result["fetch_timestamp"] = _now_iso()
            cache.set_cached("fundamentals", ticker, result)
            time.sleep(0.5)
            return result

        result["current_price"] = _safe_float(
            info.get("currentPrice") or info.get("regularMarketPrice")
        )
        result["market_cap"] = _safe_float(info.get("marketCap"))
        result["shares_outstanding"] = _safe_float(info.get("sharesOutstanding"))
        result["beta"] = _safe_float(info.get("beta"), default=1.0)
        result["sector"] = info.get("sector", "Unknown")
        result["industry"] = info.get("industry", "Unknown")
        result["trailing_pe"] = _safe_float(info.get("trailingPE"))
        result["forward_pe"] = _safe_float(info.get("forwardPE"))
        result["price_to_book"] = _safe_float(info.get("priceToBook"))
        result["ev_to_ebitda"] = _safe_float(info.get("enterpriseToEbitda"))
        result["dividend_yield"] = _safe_float(info.get("dividendYield"), default=0.0)
        result["return_on_assets"] = _safe_float(info.get("returnOnAssets"))
        result["return_on_equity"] = _safe_float(info.get("returnOnEquity"))
        result["trailing_eps"] = _safe_float(info.get("trailingEps"))
        result["forward_eps"] = _safe_float(info.get("forwardEps"))
        result["ebitda_margin"] = _safe_float(info.get("ebitdaMargins"))
        result["net_margin"] = _safe_float(info.get("profitMargins"))
        result["operating_margin"] = _safe_float(info.get("operatingMargins"))
        result["gross_margin"] = _safe_float(info.get("grossMargins"))
        result["debt_to_equity"] = _safe_float(info.get("debtToEquity"))
        result["current_ratio"] = _safe_float(info.get("currentRatio"))
        result["ebitda"] = _safe_float(info.get("ebitda"))
        result["total_revenue"] = _safe_float(info.get("totalRevenue"))
        result["analyst_target_price"] = _safe_float(info.get("targetMeanPrice"))
        result["number_of_analysts"] = _safe_float(info.get("numberOfAnalystOpinions"))
        result["enterprise_to_revenue"] = _safe_float(info.get("enterpriseToRevenue"))
        result["total_cash"] = _safe_float(info.get("totalCash"))

        # === Cash Flow Statement (last 3 years) ===
        try:
            cashflow = stock.cashflow
            if cashflow is not None and not cashflow.empty:
                # Operating Cash Flow - try multiple label names
                ocf_row = _find_row(cashflow, [
                    "Operating Cash Flow",
                    "Cash Flow From Operations",
                    "Total Cash From Operating Activities",
                    "Cash Flows From Operating Activities",
                ])
                if ocf_row is not None:
                    result["operating_cash_flow"] = [
                        _safe_float(v) for v in ocf_row.values[:3]
                        if _safe_float(v) is not None
                    ]

                # Capital Expenditures
                capex_row = _find_row(cashflow, [
                    "Capital Expenditure",
                    "Capital Expenditures",
                    "Purchase Of Property Plant And Equipment",
                ])
                if capex_row is not None:
                    result["capital_expenditures"] = [
                        _safe_float(v) for v in capex_row.values[:3]
                        if _safe_float(v) is not None
                    ]

                # Calculate Free Cash Flow = OCF + CapEx (CapEx is negative)
                if result["operating_cash_flow"] and result["capital_expenditures"]:
                    min_len = min(
                        len(result["operating_cash_flow"]),
                        len(result["capital_expenditures"]),
                    )
                    result["free_cash_flow"] = [
                        result["operating_cash_flow"][i] + result["capital_expenditures"][i]
                        for i in range(min_len)
                    ]
            else:
                logger.warning(f"{ticker}: no cashflow data available")
        except Exception as e:
            logger.warning(f"{ticker}: cashflow fetch error: {e}")

        # === Balance Sheet (debt, equity) ===
        try:
            balance = stock.balance_sheet
            if balance is not None and not balance.empty:
                # Total Debt
                debt_row = _find_row(balance, [
                    "Total Debt",
                    "Long Term Debt",
                    "Long Term Debt And Capital Lease Obligation",
                ])
                if debt_row is not None:
                    result["total_debt"] = _safe_float(debt_row.values[0])

                # Total Equity
                equity_row = _find_row(balance, [
                    "Stockholders Equity",
                    "Total Equity Gross Minority Interest",
                    "Common Stock Equity",
                ])
                if equity_row is not None:
                    result["total_equity"] = _safe_float(equity_row.values[0])
        except Exception as e:
            logger.warning(f"{ticker}: balance sheet fetch error: {e}")

        # === Income Statement (interest expense, revenue growth) ===
        try:
            income = stock.income_stmt
            if income is not None and not income.empty:
                # Interest Expense
                interest_row = _find_row(income, [
                    "Interest Expense",
                    "Interest Expense Non Operating",
                    "Net Interest Income",
                ])
                if interest_row is not None:
                    val = _safe_float(interest_row.values[0])
                    # Interest expense is sometimes positive, sometimes negative
                    result["interest_expense"] = abs(val) if val else None

                # Revenue Growth (YoY)
                rev_row = _find_row(income, [
                    "Total Revenue",
                    "Revenue",
                    "Operating Revenue",
                ])
                if rev_row is not None:
                    revenues = [_safe_float(v) for v in rev_row.values[:2]]
                    if (len(revenues) >= 2
                            and revenues[0] is not None
                            and revenues[1] is not None
                            and revenues[1] != 0):
                        result["revenue_growth"] = (revenues[0] - revenues[1]) / abs(revenues[1])
        except Exception as e:
            logger.warning(f"{ticker}: income statement fetch error: {e}")

    except Exception as e:
        logger.error(f"{ticker}: fundamental fetch failed: {e}")

    result["fetch_timestamp"] = _now_iso()
    cache.set_cached("fundamentals", ticker, result)
    time.sleep(0.5)  # Rate limiting
    return result


def fetch_fundamentals_batch(tickers: list[str]) -> dict[str, dict]:
    """
    Fetch fundamentals for multiple tickers with progress bar.
    Failed tickers are logged and skipped.
    """
    results = {}
    for ticker in tqdm(tickers, desc="Fetching fundamentals"):
        try:
            results[ticker] = fetch_fundamentals(ticker)
        except Exception as e:
            logger.error(f"{ticker}: batch fetch failed: {e}")
            results[ticker] = {"ticker": ticker, "error": str(e)}
    return results


def _now_iso() -> str:
    """Return current UTC time as ISO string."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
