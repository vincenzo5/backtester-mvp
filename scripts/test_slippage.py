#!/usr/bin/env python3
"""
Test script to verify slippage is being applied correctly.
This runs a single backtest with verbose output to see execution prices.
"""

import sys
import pandas as pd
from config import ConfigManager
from backtest.engine import run_backtest
from strategies import get_strategy_class


def test_slippage():
    """Run a backtest and verify slippage is applied to execution prices."""
    print("="*80)
    print("SLIPPAGE VERIFICATION TEST")
    print("="*80)
    print()
    
    # Load config
    config = ConfigManager(profile_name='quick')
    
    # Get slippage and commission rates from config
    slippage = config.get_slippage()
    commission = config.get_commission()
    
    print(f"Configuration:")
    print(f"  Slippage: {slippage*100:.4f}% ({slippage})")
    print(f"  Commission: {commission*100:.2f}% ({commission})")
    print()
    
    # Get strategy
    strategy_class = get_strategy_class(config.get_strategy_name())
    
    # Load data
    from data.cache_manager import read_cache
    symbols = config.get_symbols()
    timeframes = config.get_timeframes()
    
    if not symbols or not timeframes:
        print("ERROR: No symbols or timeframes configured")
        return False
    
    symbol = symbols[0]
    timeframe = timeframes[0]
    
    print(f"Loading data: {symbol} {timeframe}")
    df = read_cache(symbol, timeframe)
    
    if df.empty:
        print(f"ERROR: No cached data for {symbol} {timeframe}")
        return False
    
    # Filter by date range
    start_date = config.get_start_date()
    end_date = config.get_end_date()
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    
    if df.index.tz is not None:
        from datetime import timezone
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
    
    df = df[(df.index >= start_dt) & (df.index <= end_dt)]
    
    if df.empty:
        print(f"ERROR: No data in date range {start_date} to {end_date}")
        return False
    
    print(f"Data loaded: {len(df)} bars from {df.index[0]} to {df.index[-1]}")
    print()
    
    # Show a sample of data so we can compare expected vs executed prices
    print("Sample data (first few bars):")
    print(df[['open', 'high', 'low', 'close']].head(5))
    print()
    
    # Run backtest with verbose output
    print("="*80)
    print("RUNNING BACKTEST (check execution prices below)")
    print("="*80)
    print()
    
    try:
        result = run_backtest(config, df, strategy_class, verbose=True)
        
        print()
        print("="*80)
        print("SLIPPAGE VERIFICATION")
        print("="*80)
        
        # Extract and verify slippage from first few trades by parsing the logs
        # We'll check manually by looking at the output
        print()
        print("To verify slippage:")
        print(f"  Expected slippage rate: {slippage*100:.4f}%")
        print()
        print("  For BUY orders:")
        print(f"    Expected execution price = close_price × (1 + {slippage:.6f})")
        print(f"    Example: $100 × (1 + {slippage:.6f}) = ${100 * (1 + slippage):.2f}")
        print()
        print("  For SELL orders:")
        print(f"    Expected execution price = close_price × (1 - {slippage:.6f})")
        print(f"    Example: $100 × (1 - {slippage:.6f}) = ${100 * (1 - slippage):.2f}")
        print()
        print("Check the execution logs above:")
        print("  1. Find an ORDER log (e.g., 'ORDER: BUY(...) @ $XXX')")
        print("  2. Find the corresponding EXECUTION log (e.g., 'EXECUTION: BUY(...) @ $YYY')")
        print("  3. Compare YYY vs XXX to verify slippage is applied")
        print()
        print(f"Expected difference: ~{slippage*100:.4f}% (or ${slippage*100:.2f} per $100)")
        print()
        print("="*80)
        print("BACKTEST RESULTS")
        print("="*80)
        print(f"Number of trades: {result.get('num_trades', 0)}")
        print(f"Final value: ${result.get('final_value', 0):.2f}")
        print(f"Return: {result.get('return_pct', 0):.2f}%")
        print()
        
        return True
        
    except Exception as e:
        print(f"ERROR running backtest: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_slippage()
    sys.exit(0 if success else 1)

