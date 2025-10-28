"""
Backtesting engine module.

This module handles the core backtesting logic using backtrader.
"""

import backtrader as bt
import time
import pandas as pd


def run_backtest(config_manager, df, strategy_class, verbose=False):
    """Run the backtest with backtrader.
    
    Args:
        config_manager: ConfigManager instance
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
    
    # Add a strategy with dynamic parameters
    strategy_params = config_manager.get_strategy_params()
    cerebro.addstrategy(
        strategy_class,
        printlog=verbose,
        **strategy_params  # Dynamic parameter passing
    )
    
    # Create a Data Feed from pandas DataFrame
    data = bt.feeds.PandasData(dataname=df)
    
    # Add the Data Feed to Cerebro
    cerebro.adddata(data)
    
    # Set our desired cash start
    cerebro.broker.setcash(config_manager.get_initial_capital())
    
    # Set commission
    commission = config_manager.get_commission()
    cerebro.broker.setcommission(commission=commission)
    
    # Get slippage from config
    slippage = config_manager.get_slippage()
    
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
    
    initial_value = config_manager.get_initial_capital()
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

