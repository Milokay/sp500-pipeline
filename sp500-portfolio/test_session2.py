#!/usr/bin/env python3
"""Test Session 2 implementation: fundamentals.py and price_data.py"""

import sys
sys.path.insert(0, '.')

from modules.fundamentals import fetch_fundamentals
from modules.price_data import fetch_price_history

# Test fundamentals
print("=== Testing fundamentals.py ===")
test_tickers = ['AAPL', 'MSFT', 'JPM', 'XOM', 'PG']
for t in test_tickers:
    data = fetch_fundamentals(t)
    fcf = data.get('free_cash_flow', [])
    fcf_str = str(fcf[:3]) if fcf else '[]'
    print(f"{t}: price=${data.get('current_price', 'N/A')}, beta={data.get('beta', 'N/A')}, FCF={fcf_str}, rev_growth={data.get('revenue_growth', 'N/A')}")

print("\n=== Testing price_data.py ===")
for t in test_tickers:
    df = fetch_price_history(t)
    if not df.empty:
        nan_count = df['Close'].isna().sum()
        latest = df['Close'].iloc[-1]
        print(f"{t}: {len(df)} days, cols={list(df.columns)}, NaN in Close: {nan_count}, latest=${latest:.2f}")
    else:
        print(f"{t}: EMPTY DATAFRAME")
