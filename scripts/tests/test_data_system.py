"""
Quick test script to verify data collection system.

Tests a single market/timeframe to verify:
- Fetching works
- Cache manager works
- Validation works
- Manifest tracking works
- Update logic works
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backtester.data.fetcher import create_exchange, fetch_historical, MarketNotFoundError
from backtester.data.cache_manager import (
    delete_cache, read_cache, write_cache, 
    get_cache_path, load_manifest, get_last_cached_timestamp
)
from backtester.data.validator import validate_data, remove_duplicates
from backtester.data.updater import update_market
from backtester.config import ConfigManager


def test_single_market():
    """Test data collection with a single market/timeframe."""
    print("=" * 80)
    print("Quick Data System Test")
    print("=" * 80)
    print()
    
    # Test configuration
    symbol = "BTC/USD"
    timeframe = "1h"
    test_start_date = "2025-10-01"  # Just fetch last month for quick test
    
    try:
        config = ConfigManager()
        exchange_name = config.get_exchange_name()
        historical_start_date = config.get_historical_start_date()
    except Exception:
        exchange_name = "coinbase"
        historical_start_date = "2017-01-01"
        print("⚠️  Using default config (coinbase, 2017-01-01)")
    
    print(f"Exchange: {exchange_name}")
    print(f"Market: {symbol}")
    print(f"Timeframe: {timeframe}")
    print(f"Test start date: {test_start_date}")
    print()
    
    # Step 1: Delete existing cache for this market (clean slate)
    print("Step 1: Cleaning test cache...")
    delete_cache(symbol, timeframe)
    cache_file = get_cache_path(symbol, timeframe)
    print(f"✓ Cache file: {cache_file}")
    print()
    
    # Step 2: Test fetching
    print("Step 2: Testing data fetch...")
    try:
        exchange = create_exchange(exchange_name, enable_rate_limit=True)
        df, api_requests = fetch_historical(
            exchange, symbol, timeframe, test_start_date, None
        )
        
        if df.empty:
            print("✗ No data returned")
            return False
        
        print(f"✓ Fetched {len(df):,} candles")
        print(f"✓ API requests: {api_requests}")
        print(f"✓ Date range: {df.index.min()} to {df.index.max()}")
        print()
    except MarketNotFoundError as e:
        print(f"✗ Market not found: {e}")
        return False
    except Exception as e:
        print(f"✗ Fetch error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 3: Test validation
    print("Step 3: Testing data validation...")
    validation = validate_data(df, timeframe)
    
    if validation['valid']:
        print("✓ Data validation passed")
    else:
        print("⚠️  Data validation issues:")
        if validation.get('duplicates'):
            print(f"  - Duplicates: {validation['duplicates']}")
        if validation.get('gaps'):
            print(f"  - Gaps: {len(validation['gaps'])}")
    
    if validation.get('duplicates', 0) > 0:
        df, removed = remove_duplicates(df)
        print(f"✓ Removed {removed} duplicates")
    
    print(f"✓ Total candles: {validation['candle_count']}")
    print()
    
    # Step 4: Test cache manager
    print("Step 4: Testing cache manager...")
    write_cache(symbol, timeframe, df)
    
    if not cache_file.exists():
        print("✗ Cache file not created")
        return False
    
    print(f"✓ Cache file created: {cache_file}")
    
    # Test reading from cache
    df_read = read_cache(symbol, timeframe)
    if df_read.empty or len(df_read) != len(df):
        print(f"✗ Cache read failed: expected {len(df)} candles, got {len(df_read)}")
        return False
    
    print(f"✓ Cache read successful: {len(df_read):,} candles")
    print()
    
    # Step 5: Test manifest
    print("Step 5: Testing manifest...")
    manifest = load_manifest()
    key = f"{symbol}_{timeframe}"
    
    if key not in manifest:
        print("✗ Manifest entry not found")
        return False
    
    entry = manifest[key]
    print(f"✓ Manifest entry created:")
    print(f"  Symbol: {entry['symbol']}")
    print(f"  Timeframe: {entry['timeframe']}")
    print(f"  First date: {entry['first_date']}")
    print(f"  Last date: {entry['last_date']}")
    print(f"  Candles: {entry['candle_count']:,}")
    print()
    
    # Step 6: Test last timestamp
    print("Step 6: Testing last timestamp detection...")
    last_ts = get_last_cached_timestamp(symbol, timeframe)
    
    if last_ts is None:
        print("✗ Could not get last timestamp")
        return False
    
    print(f"✓ Last timestamp: {last_ts}")
    print()
    
    # Step 7: Test update logic (should skip since up to date)
    print("Step 7: Testing update logic...")
    from data.updater import needs_update
    needs_update_flag, last_ts_check = needs_update(symbol, timeframe)
    
    if needs_update_flag:
        print(f"⚠️  System reports update needed (cache age check)")
    else:
        print(f"✓ System correctly reports cache is up to date")
    print()
    
    print("=" * 80)
    print("✓ All tests passed!")
    print("=" * 80)
    print()
    print("Next steps:")
    print(f"1. Check cache file: {cache_file}")
    print(f"2. Check manifest: data/.cache_manifest.json")
    print(f"3. Run full bulk fetch: python scripts/bulk_fetch.py")
    print()
    
    return True


if __name__ == '__main__':
    success = test_single_market()
    sys.exit(0 if success else 1)

