#!/usr/bin/env python3
"""Advanced Session 2 tests: cache, batch, bulk, edge cases"""

import sys
import time
sys.path.insert(0, '.')

from modules.fundamentals import fetch_fundamentals, fetch_fundamentals_batch
from modules.price_data import fetch_price_history, fetch_price_history_bulk

test_tickers = ['AAPL', 'MSFT']

print("=== Test 1: Cache reload speed ===")
# First fetch (should be from cache based on previous run)
start = time.time()
data1 = fetch_fundamentals('AAPL')
elapsed1 = time.time() - start
print(f"First AAPL fetch: {elapsed1:.3f}s")

# Second fetch (should be instant from cache)
start = time.time()
data2 = fetch_fundamentals('AAPL')
elapsed2 = time.time() - start
print(f"Second AAPL fetch: {elapsed2:.3f}s")
print(f"Cache speedup: {elapsed1/elapsed2 if elapsed2 > 0 else 'instant'}x")
print(f"Data identical: {data1 == data2}")

print("\n=== Test 2: Batch fundamentals ===")
batch_result = fetch_fundamentals_batch(test_tickers)
print(f"Batch returned {len(batch_result)} tickers")
for t in test_tickers:
    if t in batch_result and 'error' not in batch_result[t]:
        print(f"{t}: price=${batch_result[t].get('current_price', 'N/A')}")
    else:
        print(f"{t}: ERROR")

print("\n=== Test 3: Bulk price download ===")
bulk_result = fetch_price_history_bulk(test_tickers)
print(f"Bulk returned {len(bulk_result)} tickers")
for t in test_tickers:
    df = bulk_result.get(t)
    if df is not None and not df.empty:
        print(f"{t}: {len(df)} days")
    else:
        print(f"{t}: EMPTY")

print("\n=== Test 4: Individual vs Bulk comparison ===")
individual_aapl = fetch_price_history('AAPL')
bulk_aapl = bulk_result.get('AAPL')
if individual_aapl is not None and bulk_aapl is not None:
    print(f"Individual AAPL: {len(individual_aapl)} rows")
    print(f"Bulk AAPL: {len(bulk_aapl)} rows")
    print(f"Same length: {len(individual_aapl) == len(bulk_aapl)}")
    print(f"Same columns: {list(individual_aapl.columns) == list(bulk_aapl.columns)}")

print("\n=== Test 5: Edge case - JPM FCF handling ===")
jpm_data = fetch_fundamentals('JPM')
print(f"JPM free_cash_flow: {jpm_data.get('free_cash_flow')} (expected: empty list for banks)")
print(f"JPM revenue_growth: {jpm_data.get('revenue_growth')} (can be None)")

print("\n=== Test 6: Helper function verification ===")
# Test _safe_float handling
from modules.fundamentals import _safe_float
print(f"_safe_float(None): {_safe_float(None)}")
print(f"_safe_float('invalid'): {_safe_float('invalid')}")
print(f"_safe_float(float('nan')): {_safe_float(float('nan'))}")
print(f"_safe_float(float('inf')): {_safe_float(float('inf'))}")
print(f"_safe_float(42.5): {_safe_float(42.5)}")

print("\n=== All tests complete ===")
