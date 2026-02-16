import os
from dotenv import load_dotenv

load_dotenv()

# === API Keys ===
FMP_API_KEY = os.getenv("FMP_API_KEY", "")  # Financial Modeling Prep (optional)

# === DCF Assumptions ===
RISK_FREE_RATE = 0.043          # 10-Year US Treasury yield (update periodically)
EQUITY_RISK_PREMIUM = 0.055     # Long-term market premium
TERMINAL_GROWTH_RATE = 0.025    # 2.5% perpetuity growth
DEFAULT_WACC = 0.10             # Fallback if WACC calculation fails
DCF_PROJECTION_YEARS = 5        # Years to project FCF forward
MARGIN_OF_SAFETY = 0.25         # 25% discount required for "Undervalued" label
BETA_FLOOR = 0.5                # Minimum beta value (prevents unrealistically low WACC)
IV_CAP_MULTIPLIER = 2.0         # Cap intrinsic value at this multiple of current price (max 100% upside)
IV_FLOOR = 0.0                  # Never return negative intrinsic value
MIN_WACC_G_SPREAD = 0.03        # Minimum WACC-growth spread for Gordon Growth (3%)

# === Exit Multiple Method (Primary Terminal Value) ===
# Sector default EV/EBITDA exit multiples (used when peer median unavailable)
SECTOR_EXIT_MULTIPLES = {
    "Technology": 20.0,
    "Information Technology": 20.0,
    "Communication Services": 14.0,
    "Healthcare": 15.0,
    "Consumer Discretionary": 14.0,
    "Consumer Cyclical": 14.0,
    "Consumer Staples": 14.0,
    "Consumer Defensive": 14.0,
    "Industrials": 12.0,
    "Materials": 10.0,
    "Basic Materials": 10.0,
    "Energy": 8.0,
    "Utilities": 10.0,
    "Real Estate": 16.0,
    "Financial Services": 10.0,
    "Financials": 10.0,
}
DEFAULT_EXIT_MULTIPLE = 12.0    # Fallback for unknown sectors
EXIT_MULTIPLE_FLOOR = 8.0      # Minimum exit multiple (prevents undervaluation)
EXIT_MULTIPLE_CAP = 25.0       # Maximum exit multiple (prevents overvaluation)
MAX_IMPLIED_GROWTH_RATE = 0.04  # 4% — flag if implied g exceeds GDP growth ceiling

# === EV/Revenue Fallback (for negative EBITDA companies) ===
SECTOR_REVENUE_MULTIPLES = {
    "Technology": 6.0,
    "Information Technology": 6.0,
    "Communication Services": 3.0,
    "Healthcare": 4.0,
    "Consumer Discretionary": 1.5,
    "Consumer Cyclical": 1.5,
    "Consumer Staples": 1.5,
    "Consumer Defensive": 1.5,
    "Industrials": 1.5,
    "Materials": 1.0,
    "Basic Materials": 1.0,
    "Energy": 1.0,
    "Utilities": 1.5,
    "Real Estate": 4.0,
}
DEFAULT_REVENUE_MULTIPLE = 2.0  # Fallback for unknown sectors
REVENUE_MULTIPLE_FLOOR = 1.0
REVENUE_MULTIPLE_CAP = 10.0

# === Earnings Quality Filter ===
MIN_EBITDA_MARGIN_FOR_DCF = 0.02  # Below 2%, force Low confidence

# === Industry-Specific Overrides ===
# WACC floors (applied AFTER company-specific WACC calc)
INDUSTRY_WACC_FLOORS = {
    "Biotechnology": 0.12,
    "Drug Manufacturers - Specialty & Generic": 0.10,
    "Airlines": 0.14,
    "Travel Services": 0.12,
    "Oil & Gas E&P": 0.11,
    "Oil & Gas Midstream": 0.09,
}

# Industry exit multiple defaults (blended 50/50 with ticker's own when available)
INDUSTRY_EXIT_MULTIPLES = {
    "Aerospace & Defense": 15.0,
    "Airlines": 6.0,
    "Biotechnology": 12.0,
    "Credit Services": 22.0,
    "Financial Data & Stock Exchanges": 22.0,
}

# Industry-specific exit multiple FLOORS (override global EXIT_MULTIPLE_FLOOR)
INDUSTRY_EXIT_MULTIPLE_FLOORS = {
    "Airlines": 6.0,          # Allow 6x for airlines (global floor is 8x)
}

# Industry revenue multiples (for negative-EBITDA fallback)
INDUSTRY_REVENUE_MULTIPLES = {
    "Biotechnology": 6.0,
    "Drug Manufacturers - Specialty & Generic": 4.0,
}

# === Analyst Target Sanity Check ===
MIN_ANALYSTS_FOR_TARGET = 5     # Minimum analysts for target price to be used
ANALYST_TARGET_MAX_DEVIATION = 3.0  # Cap IV at 2x analyst target if IV > 3x target

# === Asset-Light Financial Detection ===
ASSET_LIGHT_ROE_THRESHOLD = 0.25    # ROE > 25%
ASSET_LIGHT_PB_THRESHOLD = 5.0      # P/B > 5x
BANK_FAIR_PB_FLOOR = 0.5            # Min fair P/B for banks
BANK_FAIR_PB_CAP = 4.0              # Max fair P/B for banks

# === Technical Analysis ===
BOLLINGER_WINDOW = 20           # 20-day SMA
BOLLINGER_STD_DEV = 2           # 2 standard deviations
RSI_PERIOD = 14                 # 14-day RSI (supplementary)

# === Signal Thresholds ===
STRONG_BUY_UPSIDE = 0.30       # 30%+ upside AND near lower band
BUY_UPSIDE = 0.15              # 15%+ upside
SELL_DOWNSIDE = -0.10           # 10%+ overvalued
STRONG_SELL_DOWNSIDE = -0.25    # 25%+ overvalued AND near upper band

# === Data Source Priority ===
# "yfinance" = free, no key needed, rate-limited
# "fmp" = Financial Modeling Prep, needs API key, 250 calls/day free tier
# "polygon" = Polygon.io, needs API key, paid plans for full access
DATA_SOURCE = "yfinance"        # Change to "fmp" or "polygon" if you have keys

# === Cache ===
CACHE_EXPIRY_HOURS = 24         # Re-fetch data after this many hours
SQLITE_DB_PATH = "data/sp500_cache.db"
