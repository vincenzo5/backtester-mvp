"""
Diagnostic script to investigate why strategies aren't generating trades.

This script checks:
1. Market conditions (price, RSI, SMA values)
2. Whether strategy conditions are being met
3. What the actual data looks like
"""

import sys
import os

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backtester.data.cache_manager import read_cache
from backtester.backtest.engine import prepare_backtest_data
from backtester.strategies.sma_cross import SMACrossStrategy
from backtester.strategies.rsi_sma_strategy import RSISMAStrategy
from backtester.config import ConfigManager
import pandas as pd
import numpy as np

def diagnose_no_trades():
    """Diagnose why strategies aren't trading."""
    print("\n" + "="*60)
    print("DIAGNOSING NO TRADES ISSUE")
    print("="*60)
    
    symbol = 'BTC/USD'
    timeframe = '1h'
    
    # Load data
    df = read_cache(symbol, timeframe)
    if df.empty:
        print("❌ No data found")
        return
    
    # Use last 1000 candles
    if len(df) > 1000:
        df = df.tail(1000)
    
    print(f"\nData loaded: {len(df):,} candles")
    print(f"Date range: {df.index[0]} to {df.index[-1]}")
    print(f"Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
    
    # Analyze SMACross conditions
    print("\n" + "-"*60)
    print("SMACross Strategy Analysis")
    print("-"*60)
    
    # Calculate SMAs manually to see if they would cross
    fast_period = 20
    slow_period = 50
    
    if len(df) >= slow_period:
        df_cross = df.copy()
        df_cross['sma_fast'] = df_cross['close'].rolling(window=fast_period).mean()
        df_cross['sma_slow'] = df_cross['close'].rolling(window=slow_period).mean()
        
        # Calculate crossovers
        df_cross['cross'] = df_cross['sma_fast'] - df_cross['sma_slow']
        df_cross['prev_cross'] = df_cross['cross'].shift(1)
        
        # Bullish cross: fast crosses above slow (cross > 0 and prev_cross <= 0)
        bullish_crosses = ((df_cross['cross'] > 0) & (df_cross['prev_cross'] <= 0)).sum()
        bearish_crosses = ((df_cross['cross'] < 0) & (df_cross['prev_cross'] >= 0)).sum()
        
        print(f"Fast SMA ({fast_period}): Period {fast_period} needed")
        print(f"Slow SMA ({slow_period}): Period {slow_period} needed")
        print(f"Available data: {len(df):,} candles (need {slow_period})")
        print(f"\nBullish crosses (buy signals): {bullish_crosses}")
        print(f"Bearish crosses (sell signals): {bearish_crosses}")
        
        if bullish_crosses == 0 and bearish_crosses == 0:
            print("\n⚠️  No crossover signals in this period!")
            print("   This means fast SMA never crossed above/below slow SMA.")
            print("   This is normal if the market is trending in one direction.")
    else:
        print(f"⚠️  Not enough data! Need {slow_period} candles, have {len(df)}")
    
    # Analyze RSISMA conditions
    print("\n" + "-"*60)
    print("RSISMA Strategy Analysis")
    print("-"*60)
    
    config = ConfigManager()
    config.config['strategy']['parameters'] = {
        'sma_period': 20,
        'rsi_period': 14,
        'rsi_oversold': 30,
        'rsi_overbought': 70
    }
    
    # Use strategy defaults (no config params)
    # Backtrader strategies use params defined in code
    # We don't need to extract them - just pass empty dict and backtrader uses defaults
    strategy_params = {}
    enriched_df = prepare_backtest_data(df, RSISMAStrategy, strategy_params)
    
    if 'RSI_14' in enriched_df.columns and 'SMA_20' in enriched_df.columns:
        # Analyze conditions
        enriched_df['rsi_oversold'] = enriched_df['RSI_14'] < 30
        enriched_df['rsi_overbought'] = enriched_df['RSI_14'] > 70
        enriched_df['price_above_sma'] = enriched_df['close'] > enriched_df['SMA_20']
        
        # Buy condition: RSI < 30 AND price > SMA
        enriched_df['buy_signal'] = enriched_df['rsi_oversold'] & enriched_df['price_above_sma']
        
        rsi_min = enriched_df['RSI_14'].min()
        rsi_max = enriched_df['RSI_14'].max()
        rsi_mean = enriched_df['RSI_14'].mean()
        
        oversold_count = enriched_df['rsi_oversold'].sum()
        overbought_count = enriched_df['rsi_overbought'].sum()
        buy_signal_count = enriched_df['buy_signal'].sum()
        
        print(f"RSI range: {rsi_min:.2f} - {rsi_max:.2f} (mean: {rsi_mean:.2f})")
        print(f"RSI < 30 (oversold): {oversold_count} periods")
        print(f"RSI > 70 (overbought): {overbought_count} periods")
        print(f"Buy signals (RSI < 30 AND price > SMA): {buy_signal_count}")
        
        if oversold_count == 0:
            print("\n⚠️  RSI never went below 30 (oversold) in this period!")
            print("   This means no buy signals can occur.")
        elif buy_signal_count == 0:
            print("\n⚠️  RSI was oversold, but price was never above SMA!")
            print("   This means the condition 'RSI < 30 AND price > SMA' never occurred.")
            print("   This can happen if oversold periods coincide with downtrends.")
        
        # Show some sample data
        print("\nSample of recent data:")
        sample = enriched_df[['close', 'RSI_14', 'SMA_20', 'rsi_oversold', 'buy_signal']].tail(10)
        print(sample.to_string())
    else:
        print("⚠️  Indicators not computed correctly")
    
    # Recommendation
    print("\n" + "="*60)
    print("RECOMMENDATIONS")
    print("="*60)
    print("""
1. **Use more historical data**: The last 1,000 candles might not have
   the right market conditions. Try using the full dataset or different date ranges.

2. **Adjust strategy parameters**: 
   - For RSI: Lower oversold threshold (e.g., 25) or raise overbought (e.g., 75)
   - For SMACross: Smaller periods (e.g., 10/20) for more frequent signals

3. **Check market conditions**: Some periods are trending without reversals,
   which means strategies that rely on mean reversion (like RSI < 30) won't trigger.

4. **Test with verbose mode**: Run with verbose=True to see strategy logs.
    """)
    
    # Test with verbose
    print("\n" + "-"*60)
    print("Testing with VERBOSE mode to see strategy behavior...")
    print("-"*60)
    
    from backtest.engine import run_backtest
    
    config.config['backtest']['initial_capital'] = 10000.0
    config.config['backtest']['verbose'] = True
    
    # Override dates
    start_date = df.index[0].strftime('%Y-%m-%d')
    end_date = df.index[-1].strftime('%Y-%m-%d')
    config.config['backtest']['start_date'] = start_date
    config.config['backtest']['end_date'] = end_date
    
    print("\nRunning RSISMA with verbose output:")
    print("="*60)
    try:
        result = run_backtest(config, df, RSISMAStrategy, verbose=True)
        print(f"\nResult: {result['num_trades']} trades")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == '__main__':
    diagnose_no_trades()
