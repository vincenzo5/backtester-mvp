"""
Backtesting engine module.

This module handles the core backtesting logic using backtrader.
"""

import backtrader as bt
import yaml
import time
import pandas as pd


def load_exchange_metadata():
    """Load exchange metadata from YAML file."""
    with open('config/exchange_metadata.yaml', 'r') as f:
        return yaml.safe_load(f)


def get_symbols_and_timeframes(config):
    """Get symbols and timeframes from config or exchange_metadata."""
    metadata = load_exchange_metadata()
    
    # Get symbols
    symbols = config['exchange'].get('symbols')
    if symbols is None:
        # Use all symbols from metadata
        symbols = metadata['top_markets']
    elif isinstance(symbols, str):
        # Single symbol
        symbols = [symbols]
    # else: already a list
    
    # Validate symbols against metadata
    valid_symbols = metadata['top_markets']
    symbols = [s for s in symbols if s in valid_symbols]
    
    # Get timeframes
    timeframes = config['exchange'].get('timeframes')
    if timeframes is None:
        # Use all timeframes from metadata
        timeframes = metadata['timeframes']
    elif isinstance(timeframes, str):
        # Single timeframe
        timeframes = [timeframes]
    # else: already a list
    
    # Validate timeframes against metadata
    valid_timeframes = metadata['timeframes']
    timeframes = [tf for tf in timeframes if tf in valid_timeframes]
    
    return symbols, timeframes


def run_backtest(config, df, strategy_class, verbose=False):
    """Run the backtest with backtrader.
    
    Args:
        config (dict): Configuration dictionary
        df (pandas.DataFrame): OHLCV data
        strategy_class: Strategy class to use
        verbose (bool): If True, print detailed trade logs
    
    Returns:
        dict: Results dictionary with performance metrics
    """
    backtest_start_time = time.time()
    
    if verbose:
        print("\n" + "="*60)
        print("RUNNING BACKTEST")
        print("="*60 + "\n")
    
    # Create a cerebro entity
    cerebro = bt.Cerebro()
    
    # Add a strategy
    cerebro.addstrategy(
        strategy_class,
        fast_period=config['strategy']['parameters']['fast_sma_period'],
        slow_period=config['strategy']['parameters']['slow_sma_period'],
        printlog=verbose
    )
    
    # Create a Data Feed from pandas DataFrame
    data = bt.feeds.PandasData(dataname=df)
    
    # Add the Data Feed to Cerebro
    cerebro.adddata(data)
    
    # Set our desired cash start
    cerebro.broker.setcash(config['backtest']['initial_capital'])
    
    # Set commission (load from exchange metadata or config)
    from data.fetch_data import load_exchange_fees
    commission = load_exchange_fees(config)
    cerebro.broker.setcommission(commission=commission)
    
    # Get slippage from config
    slippage = config['trading'].get('slippage', 0.0)
    
    if verbose:
        # Log trading parameters
        print("TRADING PARAMETERS:")
        print(f"  Commission: {commission*100:.2f}%")
        print(f"  Slippage: {slippage*100:.2f}%")
        print()
        
        # Print out the starting conditions
        print(f'Starting Portfolio Value: {cerebro.broker.getvalue():.2f}')
    
    # Run over everything and capture strategy instance
    run_result = cerebro.run()
    
    # Extract the strategy instance from the run result
    # run_result is a list of strategy objects directly
    strategy_instance = run_result[0]
    
    initial_value = config['backtest']['initial_capital']
    final_value = cerebro.broker.getvalue()
    total_return = ((final_value - initial_value) / initial_value) * 100
    
    backtest_time = time.time() - backtest_start_time
    
    # Get trade count from strategy - use buy_count which counts trade entries
    trade_count = getattr(strategy_instance, 'buy_count', 0)
    
    if verbose:
        print(f'Final Portfolio Value: {final_value:.2f}')
        print(f"Total Return: {total_return:.2f}%")
        print(f"Commission Rate: {commission*100:.2f}%")
        print(f"Slippage Rate: {slippage*100:.2f}%")
        print(f"Backtest Execution Time: {backtest_time:.2f} seconds")
        print("="*60)
    
    # Return results
    duration_days = None
    if not df.empty and len(df) > 0:
        duration_days = (df.index[-1] - df.index[0]).days
    
    return {
        'initial_capital': initial_value,
        'final_value': final_value,
        'total_return_pct': total_return,
        'num_trades': trade_count,
        'execution_time': backtest_time,
        'start_date': df.index[0].strftime('%Y-%m-%d') if not df.empty else None,
        'end_date': df.index[-1].strftime('%Y-%m-%d') if not df.empty else None,
        'duration_days': duration_days
    }

