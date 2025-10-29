"""
Test end-to-end backtest with a single market.

This script tests that:
1. Data can be loaded from cache
2. Indicators are computed correctly
3. Backtest runs successfully
4. Results are returned

Usage:
    python scripts/test_single_market.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.cache_manager import read_cache
from backtest.engine import run_backtest, prepare_backtest_data
from strategies.sma_cross import SMACrossStrategy
from strategies.rsi_sma_strategy import RSISMAStrategy
from config import ConfigManager
import pandas as pd

def test_single_market():
    """Test backtest end-to-end with BTC/USD 1h."""
    print("\n" + "="*60)
    print("END-TO-END BACKTEST TEST: Single Market")
    print("="*60)
    
    # Configuration
    symbol = 'BTC/USD'
    timeframe = '1h'
    
    print(f"\nTesting: {symbol} {timeframe}")
    print("-" * 60)
    
    # Step 1: Load data
    print("\n1. Loading data from cache...")
    df = read_cache(symbol, timeframe)
    
    if df.empty:
        print(f"❌ ERROR: No cached data found for {symbol} {timeframe}")
        print("   Run: python scripts/bulk_fetch.py")
        return False
    
    print(f"   ✓ Loaded {len(df):,} candles")
    print(f"   Date range: {df.index[0]} to {df.index[-1]}")
    
    # Step 2: Filter to recent data for faster test
    print("\n2. Filtering to recent data...")
    if len(df) > 1000:
        df = df.tail(1000)
        print(f"   ✓ Using last 1,000 candles")
    
    print(f"   Filtered range: {df.index[0]} to {df.index[-1]}")
    
    # Step 3: Test old strategy (SMACross - backward compatibility)
    print("\n3. Testing SMACross strategy (backward compatibility)...")
    config = ConfigManager()
    config.config['strategy']['name'] = 'sma_cross'
    config.config['strategy']['parameters'] = {'fast_period': 20, 'slow_period': 50}
    
    # Use sufficient capital for high-priced assets like BTC
    # BTC is ~$110k, so we need at least ~$120k to buy 1 BTC
    current_price = df['close'].iloc[-1]
    min_capital = current_price * 1.2  # Enough for 1 BTC + buffer
    config.config['backtest']['initial_capital'] = min_capital
    config.config['backtest']['verbose'] = False
    print(f"   Using capital: ${min_capital:,.2f} (BTC price: ${current_price:,.2f})")
    
    # Override date range to match our data
    start_date = df.index[0].strftime('%Y-%m-%d')
    end_date = df.index[-1].strftime('%Y-%m-%d')
    config.config['backtest']['start_date'] = start_date
    config.config['backtest']['end_date'] = end_date
    
    try:
        result = run_backtest(config, df, SMACrossStrategy, verbose=False)
        print(f"   ✓ SMACross completed successfully")
        print(f"   - Initial capital: ${result['initial_capital']:,.2f}")
        print(f"   - Final value: ${result['final_value']:,.2f}")
        print(f"   - Return: {result['total_return_pct']:.2f}%")
        print(f"   - Trades: {result['num_trades']}")
        print(f"   - Execution time: {result['execution_time']:.2f}s")
    except Exception as e:
        print(f"   ❌ SMACross failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 4: Test new strategy (RSISMA - with indicators)
    print("\n4. Testing RSISMA strategy (with pre-computed indicators)...")
    config.config['strategy']['name'] = 'rsi_sma'
    config.config['strategy']['parameters'] = {
        'sma_period': 20,
        'rsi_period': 14,
        'rsi_oversold': 30,
        'rsi_overbought': 70
    }
    # Keep same capital amount
    print(f"   Using capital: ${config.config['backtest']['initial_capital']:,.2f}")
    
    try:
        # Test prepare_backtest_data
        strategy_params = config.get_strategy_params()
        enriched_df = prepare_backtest_data(df, RSISMAStrategy, strategy_params)
        
        original_cols = set(df.columns)
        new_cols = set(enriched_df.columns) - original_cols
        
        print(f"   ✓ Prepared data: Added {len(new_cols)} indicator columns")
        print(f"   - New columns: {', '.join(sorted(new_cols))}")
        
        # Verify indicators have valid values
        if 'SMA_20' in enriched_df.columns:
            valid_sma = enriched_df['SMA_20'].notna().sum()
            print(f"   - SMA_20: {valid_sma:,} valid values")
        
        if 'RSI_14' in enriched_df.columns:
            valid_rsi = enriched_df['RSI_14'].notna().sum()
            print(f"   - RSI_14: {valid_rsi:,} valid values")
        
        # Run backtest
        result = run_backtest(config, df, RSISMAStrategy, verbose=False)
        print(f"\n   ✓ RSISMA completed successfully")
        print(f"   - Initial capital: ${result['initial_capital']:,.2f}")
        print(f"   - Final value: ${result['final_value']:,.2f}")
        print(f"   - Return: {result['total_return_pct']:.2f}%")
        print(f"   - Trades: {result['num_trades']}")
        print(f"   - Execution time: {result['execution_time']:.2f}s")
        
    except Exception as e:
        print(f"   ❌ RSISMA failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # Success!
    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED!")
    print("="*60)
    print("\nThe backtest engine is working end-to-end:")
    print("  ✓ Data loading from cache")
    print("  ✓ Indicator pre-computation")
    print("  ✓ Strategy execution")
    print("  ✓ Results generation")
    print("\nBoth old (SMACross) and new (RSISMA) strategies work correctly.")
    
    return True


if __name__ == '__main__':
    success = test_single_market()
    sys.exit(0 if success else 1)
