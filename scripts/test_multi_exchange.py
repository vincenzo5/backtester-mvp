"""
Test script for multi-exchange data collection system.

Tests the exchange discovery and data fetching with:
- BTC/USD: Established market with deep history
- SUI/USD: Recent coin with limited history

This script validates that the system correctly identifies which exchange
has the earliest data and fetches it successfully.
"""

import os
import sys
import yaml
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.exchange_discovery import find_best_exchange
from data.fetcher import create_exchange, fetch_historical, MarketNotFoundError, FetchError
from data.cache_manager import (
    get_cache_path, read_cache, write_cache, delete_cache,
    get_manifest_entry
)


def load_metadata():
    """Load exchange metadata configuration."""
    with open('config/markets.yaml', 'r') as f:
        return yaml.safe_load(f)


def test_market(symbol: str, timeframe: str, exchanges: list):
    """Test exchange discovery and data fetching for a single market/timeframe."""
    print(f"\n{'='*80}")
    print(f"Testing {symbol} {timeframe}")
    print(f"{'='*80}")
    
    # Step 1: Find best exchange
    print(f"\n1. Discovering best exchange among {exchanges}...")
    best_exchange, earliest_date = find_best_exchange(symbol, timeframe, exchanges)
    
    if best_exchange is None:
        print(f"   ✗ No exchange found with data for {symbol} {timeframe}")
        return False
    
    print(f"   ✓ Best exchange: {best_exchange}")
    print(f"   ✓ Earliest date: {earliest_date.date() if earliest_date else 'N/A'}")
    
    # Step 2: Delete existing cache (clean slate)
    print(f"\n2. Cleaning existing cache...")
    cache_path = get_cache_path(symbol, timeframe)
    if cache_path.exists():
        delete_cache(symbol, timeframe)
        print(f"   ✓ Deleted existing cache")
    else:
        print(f"   - No existing cache found")
    
    # Step 3: Fetch data from best exchange
    print(f"\n3. Fetching data from {best_exchange}...")
    try:
        exchange = create_exchange(best_exchange, enable_rate_limit=True)
        
        # Use earliest date found as start, or default to 2017-01-01
        fetch_start = earliest_date.strftime('%Y-%m-%d') if earliest_date else "2017-01-01"
        end_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
        
        print(f"   Fetching from {fetch_start} to {end_date}...")
        df, api_requests = fetch_historical(
            exchange, symbol, timeframe,
            fetch_start, end_date,
            auto_find_earliest=True,
            source_exchange=best_exchange
        )
        
        if df.empty:
            print(f"   ✗ No data fetched")
            return False
        
        print(f"   ✓ Fetched {len(df):,} candles in {api_requests} API requests")
        print(f"   ✓ Date range: {df.index.min().date()} to {df.index.max().date()}")
        
        # Step 4: Save to cache
        print(f"\n4. Saving to cache...")
        write_cache(symbol, timeframe, df, source_exchange=best_exchange)
        print(f"   ✓ Saved to {cache_path}")
        
        # Step 5: Verify manifest
        print(f"\n5. Verifying manifest...")
        manifest_entry = get_manifest_entry(symbol, timeframe)
        if manifest_entry and 'source_exchange' in manifest_entry:
            if manifest_entry['source_exchange'] == best_exchange:
                print(f"   ✓ Manifest correctly stores source_exchange: {best_exchange}")
            else:
                print(f"   ✗ Manifest source_exchange mismatch: expected {best_exchange}, got {manifest_entry.get('source_exchange')}")
                return False
        else:
            print(f"   ✗ Manifest missing source_exchange field")
            return False
        
        # Step 6: Verify cache can be read
        print(f"\n6. Verifying cache read...")
        cached_df = read_cache(symbol, timeframe)
        if cached_df.empty:
            print(f"   ✗ Cache read returned empty DataFrame")
            return False
        
        if len(cached_df) != len(df):
            print(f"   ✗ Cache read returned {len(cached_df)} candles, expected {len(df)}")
            return False
        
        print(f"   ✓ Cache read successful: {len(cached_df):,} candles")
        
        # Step 7: Verify CSV format (should not have source_exchange column)
        print(f"\n7. Verifying CSV format...")
        import pandas as pd
        csv_df = pd.read_csv(cache_path, index_col='datetime', parse_dates=True)
        if 'source_exchange' in csv_df.columns:
            print(f"   ✗ CSV should not contain source_exchange column")
            return False
        
        print(f"   ✓ CSV format correct (no source_exchange column)")
        
        print(f"\n{'='*80}")
        print(f"✓ {symbol} {timeframe} test PASSED")
        print(f"{'='*80}")
        return True
        
    except (MarketNotFoundError, FetchError) as e:
        print(f"   ✗ Fetch error: {str(e)}")
        return False
    except Exception as e:
        print(f"   ✗ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run test suite."""
    print("=" * 80)
    print("Multi-Exchange Data Collection Test Suite")
    print("=" * 80)
    
    # Load metadata
    metadata = load_metadata()
    exchanges = metadata.get('exchanges', ['coinbase', 'binance', 'kraken'])
    
    print(f"\nExchanges to test: {exchanges}")
    print(f"Test markets:")
    print(f"  - BTC/USD (established, deep history)")
    print(f"  - SUI/USD (recent, limited history)")
    print(f"Test timeframe: 1d")
    
    results = {}
    
    # Test BTC/USD
    results['BTC/USD'] = test_market('BTC/USD', '1d', exchanges)
    
    # Test SUI/USD
    results['SUI/USD'] = test_market('SUI/USD', '1d', exchanges)
    
    # Print summary
    print(f"\n\n{'='*80}")
    print("Test Summary")
    print(f"{'='*80}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for market, result in results.items():
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"  {market}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print(f"\n✓ All tests PASSED")
        return 0
    else:
        print(f"\n✗ Some tests FAILED")
        return 1


if __name__ == '__main__':
    exit(main())

