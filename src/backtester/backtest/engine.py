"""
Backtesting engine module.

This module handles the core backtesting logic using backtrader. It pre-computes
indicators and aligns third-party data sources before running backtests, optimizing
for walk-forward optimization scenarios.

Quick Start:
    from backtester.backtest.engine import run_backtest, prepare_backtest_data
    from backtester.strategies import get_strategy_class
    from backtester.config import ConfigManager
    
    config = ConfigManager()
    strategy_class = get_strategy_class('sma_cross')
    df = load_ohlcv_data()
    
    # Prepare data (compute indicators, align data sources)
    enriched_df = prepare_backtest_data(df, strategy_class, config.get_strategy_params())
    
    # Run backtest
    result = run_backtest(config, enriched_df, strategy_class, verbose=True)

Common Patterns:
    # Pattern 1: Using with indicators
    # Strategy declares indicators via get_required_indicators()
    # Engine automatically computes them before backtest
    
    # Pattern 2: Using with third-party data
    # Strategy declares data sources via get_required_data_sources()
    # Engine fetches and aligns data before backtest
    
    # Pattern 3: Walk-forward optimization
    # Prepare data once, then run multiple backtests with different parameters
    base_df = load_ohlcv_data()
    strategy_class = MyStrategy
    
    # Prepare indicators once (expensive operation)
    enriched_df = prepare_backtest_data(base_df, strategy_class, base_params)
    
    # Run many backtests quickly (reusing pre-computed indicators)
    for params in parameter_combinations:
        result = run_backtest(config, enriched_df, strategy_class, verbose=False)

Extending:
    The prepare_backtest_data() function:
    - Calls strategy.get_required_indicators() to get indicator specs
    - Computes all indicators using IndicatorLibrary
    - Calls strategy.get_required_data_sources() to get data providers
    - Fetches and aligns all external data
    - Returns enriched DataFrame ready for backtesting
"""

import backtrader as bt
import time
import pandas as pd
from typing import Optional


class EnrichedPandasData(bt.feeds.PandasData):
    """
    Custom PandasData feed that exposes additional columns (indicators, data sources).
    
    This class dynamically exposes all DataFrame columns beyond OHLCV as accessible
    attributes in strategies (e.g., self.data.SMA_20[0]).
    """
    
    def __getattr__(self, name):
        """
        Override to allow access to indicator columns by name.
        
        First tries standard backtrader attributes, then checks if it's
        an indicator column in the DataFrame.
        """
        # Try standard backtrader attribute access first
        try:
            return super().__getattribute__(name)
        except AttributeError:
            pass
        
        # Check if it's a line (standard backtrader mechanism)
        try:
            return getattr(self.lines, name)
        except AttributeError:
            pass
        
        # Check if it's an indicator/data column in the DataFrame
        if hasattr(self, 'p') and hasattr(self.p, 'dataname') and name in self.p.dataname.columns:
            # Get the column index
            col_idx = list(self.p.dataname.columns).index(name)
            
            # Create a line that directly accesses this column from the DataFrame
            # We'll use backtrader's line mechanism by creating a custom line
            class ColumnLine:
                """Line that accesses a DataFrame column by index."""
                def __init__(self, data_feed, col_idx):
                    self.data_feed = data_feed
                    self.col_idx = col_idx
                
                def __getitem__(self, idx):
                    """Access the value at index.
                    
                    In backtrader, [0] = current bar, [-1] = previous bar, etc.
                    We need to map this to the DataFrame index.
                    """
                    if not hasattr(self.data_feed, 'p') or not hasattr(self.data_feed.p, 'dataname'):
                        return float('nan')
                    
                    df = self.data_feed.p.dataname
                    
                    # In backtrader, len(self.data) gives total bars seen so far
                    # [0] should access the current bar (latest processed)
                    # Current bar index in DataFrame = len(self.data_feed) - 1
                    # Then [0] = current, [-1] = previous, etc.
                    
                    # Get current position in DataFrame
                    current_pos = len(self.data_feed) - 1
                    
                    # Map backtrader index to DataFrame position
                    # [0] = current bar, [-1] = previous, etc.
                    df_idx = current_pos + idx
                    
                    if 0 <= df_idx < len(df):
                        value = df.iloc[df_idx, self.col_idx]
                        # Handle NaN
                        import numpy as np
                        if pd.isna(value) or (isinstance(value, float) and np.isnan(value)):
                            return float('nan')
                        return value
                    
                    return float('nan')
            
            # Create and cache the line
            line = ColumnLine(self, col_idx)
            if not hasattr(self.lines, name):
                setattr(self.lines, name, line)
            return line
        
        # Not found
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


def prepare_backtest_data(df: pd.DataFrame, strategy_class, strategy_params: dict, symbol: Optional[str] = None) -> pd.DataFrame:
    """
    Prepare DataFrame for backtest by computing indicators and aligning data sources.
    
    This function:
    1. Gets required indicators from strategy class
    2. Computes all indicators and adds to DataFrame
    3. Gets required data sources from strategy class
    4. Fetches and aligns all external data
    5. Returns enriched DataFrame ready for backtesting
    
    Args:
        df: OHLCV DataFrame with datetime index
        strategy_class: Strategy class (must have get_required_indicators/get_required_data_sources methods)
        strategy_params: Dictionary of strategy parameters
        symbol: Optional trading pair symbol (e.g., 'BTC/USD') for data source providers
    
    Returns:
        Enriched DataFrame with:
        - Original OHLCV columns (open, high, low, close, volume)
        - Indicator columns (e.g., SMA_20, RSI_14)
        - External data columns (e.g., onchain_active_addresses)
    
    Example:
        from backtester.backtest.engine import prepare_backtest_data
        from backtester.strategies import get_strategy_class
        
        strategy_class = get_strategy_class('rsi_sma')
        params = {'fast_period': 20, 'slow_period': 50}
        
        enriched_df = prepare_backtest_data(df, strategy_class, params)
        # enriched_df now has all indicators and data sources ready
    """
    if df.empty:
        return df
    
    result_df = df.copy()
    
    # Step 1: Compute indicators
    try:
        # Get required indicators from strategy
        indicator_specs = strategy_class.get_required_indicators(strategy_params)
        
        if indicator_specs:
            from indicators import IndicatorLibrary
            lib = IndicatorLibrary()
            result_df = lib.compute_all(result_df, indicator_specs)
    except AttributeError:
        # Strategy doesn't implement get_required_indicators - that's okay, skip
        pass
    except Exception as e:
        # Log but don't fail - some strategies might not need indicators
        import warnings
        warnings.warn(f"Error computing indicators: {str(e)}")
    
    # Step 2: Fetch and align third-party data sources
    try:
        # Get required data sources from strategy
        data_sources = strategy_class.get_required_data_sources()
        
        if data_sources:
            # Extract date range from DataFrame
            if not result_df.empty:
                start_date = result_df.index[0].strftime('%Y-%m-%d')
                end_date = result_df.index[-1].strftime('%Y-%m-%d')
                
                # Use provided symbol or default
                data_symbol = symbol or 'BTC/USD'  # Default for mock providers
                
                for provider in data_sources:
                    try:
                        # Fetch raw data
                        raw_data = provider.fetch(data_symbol, start_date, end_date)
                        
                        # Align to OHLCV timeframe
                        prefix = provider.get_provider_name() + '_'
                        aligned_data = provider.align_to_ohlcv(raw_data, result_df, prefix=prefix)
                        
                        # Merge with result DataFrame
                        result_df = result_df.join(aligned_data)
                    except Exception as e:
                        # Log but continue with other providers
                        import warnings
                        warnings.warn(f"Error fetching data from {provider.__class__.__name__}: {str(e)}")
                        continue
    except AttributeError:
        # Strategy doesn't implement get_required_data_sources - that's okay, skip
        pass
    except Exception as e:
        # Log but don't fail
        import warnings
        warnings.warn(f"Error fetching data sources: {str(e)}")
    
    return result_df


def run_backtest(config_manager, df, strategy_class, verbose=False, strategy_params=None, return_metrics=False):
    """Run the backtest with backtrader.
    
    This function automatically prepares data (indicators + data sources) before
    running the backtest. The DataFrame passed in should be raw OHLCV data;
    indicators and external data will be computed/loaded automatically.
    
    Args:
        config_manager: ConfigManager instance
        df (pandas.DataFrame): OHLCV data (indicators/data sources will be added automatically)
        strategy_class: Strategy class to use
        verbose (bool): If True, print detailed trade logs
        strategy_params: Optional dict of strategy parameters
        return_metrics: If True, also return (cerebro, strategy_instance) tuple for metrics calculation
    
    Returns:
        dict: Results dictionary with performance metrics
        OR tuple: (result_dict, cerebro, strategy_instance) if return_metrics=True
    
    Note:
        Indicators and data sources are pre-computed before the backtest runs.
        This is optimized for walk-forward optimization where the same data
        is used for multiple parameter combinations.
    """
    backtest_start_time = time.time()
    
    if verbose:
        print("\n" + "="*60)
        print("RUNNING BACKTEST")
        print("="*60 + "\n")
    
    # Try to get symbol from config (first symbol if multiple)
    symbol = None
    try:
        symbols = config_manager.get_symbols()
        if symbols:
            symbol = symbols[0]  # Use first symbol if available
    except Exception:
        pass  # If we can't get symbol, use default in prepare_backtest_data
    
    # Get strategy parameters
    # If strategy_params is None, use empty dict - backtrader will use strategy code defaults
    # Strategy parameters are defined in the strategy class itself via params tuple
    if strategy_params is None:
        strategy_params = {}  # Empty dict lets backtrader use defaults from strategy.params
    
    enriched_df = prepare_backtest_data(df, strategy_class, strategy_params, symbol=symbol)
    
    if verbose:
        # Show what was added
        original_cols = set(df.columns)
        new_cols = set(enriched_df.columns) - original_cols
        if new_cols:
            print(f"Prepared data: Added {len(new_cols)} columns")
            print(f"  Indicators/Data: {', '.join(sorted(new_cols))}")
            print()
    
    # Create a cerebro entity
    cerebro = bt.Cerebro()
    
    # Add analyzers for detailed metrics calculation
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    
    # Wrap strategy class to track equity curve (mark-to-market at each bar)
    class EquityTrackingStrategy(strategy_class):
        def __init__(self):
            super().__init__()
            # Initialize equity curve tracking if not already present
            if not hasattr(self, 'equity_curve'):
                self.equity_curve = []
        
        def next(self):
            super().next()
            # Track portfolio value at end of each bar (mark-to-market)
            # MultiWalk uses end-of-day (close of last bar before midnight)
            current_datetime = self.data.datetime.datetime(0)
            portfolio_value = self.broker.getvalue()
            self.equity_curve.append({
                'date': current_datetime,
                'value': portfolio_value
            })
    
    # Add wrapped strategy with parameters
    # If strategy_params provided, override defaults; otherwise use strategy code defaults
    cerebro.addstrategy(
        EquityTrackingStrategy,
        printlog=verbose,
        **strategy_params  # Pass params (may be empty dict to use strategy defaults)
    )
    
    # Create a Data Feed from enriched pandas DataFrame
    # Use custom class to expose indicator columns
    original_cols = set(enriched_df.columns)
    ohlcv_cols = {'open', 'high', 'low', 'close', 'volume'}
    indicator_cols = original_cols - ohlcv_cols
    
    if indicator_cols:
        # Use custom PandasData that can access indicator columns
        data = EnrichedPandasData(dataname=enriched_df)
    else:
        # No indicators, use standard PandasData
        data = bt.feeds.PandasData(dataname=enriched_df)
    
    # Add the Data Feed to Cerebro
    cerebro.adddata(data)
    
    # Set our desired cash start
    cerebro.broker.setcash(config_manager.get_initial_capital())
    
    # Set commission
    commission = config_manager.get_commission()
    cerebro.broker.setcommission(commission=commission)
    
    # Set slippage from config
    slippage = config_manager.get_slippage()
    if slippage > 0:
        # Apply percentage-based slippage
        # slip_open: apply to market orders executed at open
        # slip_limit: apply to limit orders (we use market orders but include for completeness)
        # slip_match: cap slippage at high/low prices (safety)
        # slip_out: don't allow slippage to exceed high/low range
        cerebro.broker.set_slippage_perc(
            perc=slippage,
            slip_open=True,
            slip_limit=False,
            slip_match=True,
            slip_out=False
        )
    
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
    
    backtest_time = time.time() - backtest_start_time
    
    # Calculate comprehensive metrics using unified calculator
    from backtester.backtest.walkforward.metrics_calculator import calculate_metrics
    from dataclasses import asdict
    
    start_date = pd.to_datetime(df.index[0]).to_pydatetime() if not df.empty else None
    end_date = pd.to_datetime(df.index[-1]).to_pydatetime() if not df.empty else None
    
    metrics = calculate_metrics(
        cerebro,
        strategy_instance,
        initial_value,
        equity_curve=None,  # Will extract from strategy_instance
        start_date=start_date,
        end_date=end_date
    )
    
    if verbose:
        print(f'Final Portfolio Value: {final_value:.2f}')
        print(f"Total Return: {metrics.total_return_pct:.2f}%")
        print(f"Number of Trades: {metrics.num_trades}")
        print(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
        print(f"Max Drawdown: {metrics.max_drawdown:.2f}")
        print(f"Commission Rate: {commission*100:.2f}%")
        print(f"Slippage Rate: {slippage*100:.2f}%")
        print(f"Backtest Execution Time: {backtest_time:.2f} seconds")
        print("="*60)
    
    # Return results with serialized metrics for parallel execution
    result_dict = {
        'initial_capital': initial_value,  # Store for display/export
        'execution_time': backtest_time,
        'start_date': df.index[0].strftime('%Y-%m-%d') if not df.empty else None,
        'end_date': df.index[-1].strftime('%Y-%m-%d') if not df.empty else None,
        'metrics': asdict(metrics),  # Serialized for parallel execution
        # Backward compatibility fields for test scripts and legacy code
        'final_value': final_value,
        'total_return_pct': metrics.total_return_pct,
        'num_trades': metrics.num_trades,
    }
    
    # Return metrics objects if requested (for walk-forward optimization)
    if return_metrics:
        return result_dict, cerebro, strategy_instance, metrics
    
    return result_dict

