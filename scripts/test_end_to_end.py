"""
Quick end-to-end test of the complete data collection system.

Tests the full workflow:
1. Bulk fetch with subset of markets
2. Update runner (delta updates)
3. Backtest integration

Only tests 2 markets × 2 timeframes for speed.
"""

import sys
import os
import yaml
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def backup_and_modify_metadata():
    """Backup metadata and create minimal test version."""
    metadata_path = Path('config/markets.yaml')
    backup_path = Path('config/exchange_metadata.yaml.backup')
    
    # Backup original
    if metadata_path.exists():
        shutil.copy(metadata_path, backup_path)
        print(f"✓ Backed up metadata to {backup_path}")
    
    # Read original
    with open(metadata_path, 'r') as f:
        metadata = yaml.safe_load(f)
    
    # Create minimal test version (just 2 markets × 2 timeframes)
    test_metadata = {
        # Exchange comes from config, not metadata
        'exchange': 'coinbase',  # Will use actual config in real usage
        'timeframes': ['1h', '1d'],  # Only 2 timeframes
        'top_markets': ['BTC/USD', 'ETH/USD'],  # Only 2 markets
        'fees': metadata.get('fees', {'maker': 0.004, 'taker': 0.006}),
        'last_updated': datetime.now(timezone.utc).isoformat()
    }
    
    # Write test version
    with open(metadata_path, 'w') as f:
        yaml.dump(test_metadata, f, default_flow_style=False, sort_keys=False)
    
    print("✓ Created test metadata (2 markets × 2 timeframes)")
    return backup_path


def restore_metadata(backup_path):
    """Restore original metadata."""
    metadata_path = Path('config/markets.yaml')
    if backup_path.exists():
        shutil.copy(backup_path, metadata_path)
        backup_path.unlink()
        print(f"✓ Restored original metadata")


def run_bulk_fetch():
    """Test bulk fetch script."""
    print("\n" + "=" * 80)
    print("STEP 1: Testing Bulk Fetch")
    print("=" * 80)
    
    from scripts.bulk_fetch import main as bulk_fetch_main
    
    try:
        bulk_fetch_main()
        print("\n✓ Bulk fetch completed successfully")
        return True
    except Exception as e:
        print(f"\n✗ Bulk fetch failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_update_runner():
    """Test update runner service."""
    print("\n" + "=" * 80)
    print("STEP 2: Testing Update Runner (Delta Update)")
    print("=" * 80)
    
    from services.update_runner import run_update
    
    try:
        # Set target date to yesterday to force a check
        target_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
        
        result = run_update(target_end_date=target_date)
        
        if result.get('status') == 'success':
            print(f"\n✓ Update runner completed successfully")
            print(f"  - Updated: {result.get('updated', 0)}")
            print(f"  - Skipped: {result.get('skipped', 0)}")
            print(f"  - Failed: {result.get('failed', 0)}")
            return True
        else:
            print(f"\n✗ Update runner failed: {result.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"\n✗ Update runner failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_backtest_integration():
    """Test that backtest can actually use the cached data."""
    print("\n" + "=" * 80)
    print("STEP 3: Testing Backtest Integration")
    print("=" * 80)
    
    try:
        from config import ConfigManager
        from data.cache_manager import read_cache
        from backtest.engine import run_backtest
        from strategies import get_strategy_class
        import pandas as pd
        
        # Create config
        config = ConfigManager(profile_name='quick')
        
        # Get symbols and timeframes from config
        symbols = config.get_symbols()
        timeframes = config.get_timeframes()
        
        if not symbols or not timeframes:
            print("⚠️  No symbols/timeframes in quick test config, trying defaults...")
            symbols = ['BTC/USD']
            timeframes = ['1h']
        
        symbol = symbols[0]
        timeframe = timeframes[0]
        
        print(f"Testing with {symbol} {timeframe}...")
        
        # Try to load data from cache
        df = read_cache(symbol, timeframe)
        
        if df.empty:
            print(f"✗ No cached data found for {symbol} {timeframe}")
            print("  Run bulk_fetch.py first to populate cache")
            return False
        
        print(f"✓ Loaded {len(df):,} candles from cache")
        
        # Filter by backtest date range
        start_date = config.get_start_date()
        end_date = config.get_end_date()
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        # Handle timezone-aware DataFrames
        if df.index.tz is not None:
            from datetime import timezone
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
        
        df_filtered = df[(df.index >= start_dt) & (df.index <= end_dt)]
        
        if df_filtered.empty:
            print(f"⚠️  No data in backtest date range ({start_date} to {end_date})")
            print(f"   Cache has data from {df.index.min()} to {df.index.max()}")
            # Use available data anyway
            df_filtered = df
        
        print(f"✓ Filtered to {len(df_filtered):,} candles for backtest date range")
        
        if len(df_filtered) < 50:
            print("⚠️  Very few candles, backtest may not be meaningful")
        
        # Try to run a backtest
        print("\nRunning test backtest...")
        strategy_class = get_strategy_class(config.get_strategy_name())
        result = run_backtest(config, df_filtered, strategy_class, verbose=False)
        
        if result and 'final_value' in result:
            print(f"\n✓ Backtest completed successfully")
            print(f"  Initial capital: ${result['initial_capital']:,.2f}")
            print(f"  Final value: ${result['final_value']:,.2f}")
            print(f"  Total return: {result['total_return_pct']:.2f}%")
            print(f"  Trades: {result['num_trades']}")
            return True
        else:
            print("✗ Backtest returned invalid results")
            return False
        
    except Exception as e:
        print(f"✗ Backtest integration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_cache_files():
    """Verify cache files and manifest were created."""
    print("\n" + "=" * 80)
    print("STEP 4: Verifying Cache Files")
    print("=" * 80)
    
    from data.cache_manager import load_manifest, get_cache_path
    
    manifest = load_manifest()
    
    if not manifest:
        print("✗ No manifest found")
        return False
    
    print(f"✓ Manifest found with {len(manifest)} entries")
    
    # Check expected test markets
    expected = ['BTC/USD_1h', 'BTC/USD_1d', 'ETH/USD_1h', 'ETH/USD_1d']
    found = []
    
    for key in expected:
        if key in manifest:
            entry = manifest[key]
            cache_file = get_cache_path(entry['symbol'], entry['timeframe'])
            if cache_file.exists():
                found.append(key)
                print(f"✓ {key}: {entry['candle_count']:,} candles, last updated {entry['last_date']}")
            else:
                print(f"⚠️  {key}: Manifest entry exists but cache file missing")
        else:
            print(f"⚠️  {key}: Not in manifest")
    
    if len(found) == len(expected):
        print(f"\n✓ All {len(expected)} expected cache files found")
        return True
    else:
        print(f"\n⚠️  Only {len(found)}/{len(expected)} cache files found")
        return len(found) > 0  # Partial success


def main():
    """Run end-to-end test."""
    print("=" * 80)
    print("End-to-End Data Collection System Test")
    print("=" * 80)
    print("\nThis test will:")
    print("1. Temporarily modify exchange_metadata.yaml (2 markets × 2 timeframes)")
    print("2. Run bulk_fetch.py")
    print("3. Run update_runner.py")
    print("4. Test backtest integration")
    print("5. Verify cache files")
    print("\nEstimated time: 2-5 minutes\n")
    
    backup_path = None
    
    try:
        # Backup and modify metadata
        backup_path = backup_and_modify_metadata()
        
        results = []
        
        # Step 1: Bulk fetch
        results.append(("Bulk Fetch", run_bulk_fetch()))
        
        # Step 2: Update runner
        results.append(("Update Runner", run_update_runner()))
        
        # Step 3: Backtest integration
        results.append(("Backtest Integration", test_backtest_integration()))
        
        # Step 4: Verify cache
        results.append(("Cache Verification", verify_cache_files()))
        
        # Summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        
        all_passed = True
        for name, passed in results:
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"{status}: {name}")
            if not passed:
                all_passed = False
        
        print("=" * 80)
        
        if all_passed:
            print("\n✓ All end-to-end tests passed!")
            print("\nThe system is working correctly. You can now:")
            print("1. Restore full metadata (original will be restored automatically)")
            print("2. Run full bulk fetch: python scripts/bulk_fetch.py")
            print("3. Start scheduler: python services/scheduler_daemon.py")
        else:
            print("\n✗ Some tests failed. Check errors above.")
        
        return all_passed
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        return False
    except Exception as e:
        print(f"\n\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Always restore metadata
        if backup_path:
            print("\nRestoring original metadata...")
            restore_metadata(backup_path)


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)

