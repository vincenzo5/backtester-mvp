"""
Apply filters to trade lists based on filter configurations.

Uses each filter's matching logic to filter trades post-execution.

Quick Start:
    from backtester.filters.applicator import apply_filters_to_trades, recalculate_metrics_with_filtered_trades
    
    # Filter trades
    filtered_trades = apply_filters_to_trades(trades, df, filter_config)
    
    # Recalculate metrics with filtered trades
    filtered_metrics = recalculate_metrics_with_filtered_trades(
        cerebro, strategy_instance, initial_capital, filtered_trades, equity_curve, start_date, end_date
    )
"""

from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import datetime
from backtester.filters.registry import get_filter
from backtester.backtest.walkforward.metrics_calculator import (
    calculate_metrics,
    BacktestMetrics
)
import backtrader as bt


def apply_filters_to_trades(
    trades: List[Dict[str, Any]],
    df: pd.DataFrame,
    filter_config: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Filter trades based on active filter configuration.
    
    Uses each filter's own matching logic (entry, both, either) to determine
    if a trade should be included.
    
    Args:
        trades: List of trade dictionaries with 'entry_date' and 'exit_date'
                Expected format: [
                    {
                        'entry_date': datetime,
                        'exit_date': datetime,
                        'pnl': float,
                        ...
                    },
                    ...
                ]
        df: DataFrame with filter classification columns (e.g., 'volatility_regime_atr')
            Must have datetime index matching trade dates
        filter_config: Dictionary mapping filter_name -> target_regime
                      Empty dict means no filtering (baseline - return all trades)
                      Example: {'volatility_regime_atr': 'high'}
    
    Returns:
        Filtered list of trades
    
    Example:
        filter_config = {'volatility_regime_atr': 'high'}
        # Returns only trades entered during high volatility (if matching='entry')
        
        filter_config = {}  # baseline
        # Returns all trades
    """
    if not filter_config:
        # Baseline: no filters applied, return all trades
        return trades.copy()
    
    if not trades:
        return []
    
    if df.empty:
        # No data available for filtering, return empty
        return []
    
    filtered_trades = []
    
    for trade in trades:
        entry_date = trade.get('entry_date')
        exit_date = trade.get('exit_date')
        
        if not entry_date or not exit_date:
            # Skip trades without dates (shouldn't happen, but safe)
            continue
        
        # Check if trade matches all filters in config
        include_trade = True
        
        for filter_name, target_regime in filter_config.items():
            if target_regime == 'none':
                # This filter is disabled for this config (skip)
                continue
            
            # Get filter class to check matching logic
            filter_class = get_filter(filter_name)
            if filter_class is None:
                # Filter not found - skip this filter (log warning?)
                continue
            
            # Get regime classifications for this trade's dates
            # Use nearest index matching for robustness
            try:
                # Normalize timezones to match DataFrame index before comparison
                normalized_entry_date = entry_date
                normalized_exit_date = exit_date
                
                if df.index.tz is not None:
                    # DataFrame is timezone-aware, ensure trade dates match
                    import pandas as pd
                    if isinstance(entry_date, pd.Timestamp):
                        if entry_date.tz is None:
                            normalized_entry_date = entry_date.tz_localize('UTC')
                        elif entry_date.tz != df.index.tz:
                            normalized_entry_date = entry_date.tz_convert(df.index.tz)
                    else:
                        normalized_entry_date = pd.to_datetime(entry_date)
                        if normalized_entry_date.tz is None:
                            normalized_entry_date = normalized_entry_date.tz_localize('UTC')
                        elif normalized_entry_date.tz != df.index.tz:
                            normalized_entry_date = normalized_entry_date.tz_convert(df.index.tz)
                    
                    if isinstance(exit_date, pd.Timestamp):
                        if exit_date.tz is None:
                            normalized_exit_date = exit_date.tz_localize('UTC')
                        elif exit_date.tz != df.index.tz:
                            normalized_exit_date = exit_date.tz_convert(df.index.tz)
                    else:
                        normalized_exit_date = pd.to_datetime(exit_date)
                        if normalized_exit_date.tz is None:
                            normalized_exit_date = normalized_exit_date.tz_localize('UTC')
                        elif normalized_exit_date.tz != df.index.tz:
                            normalized_exit_date = normalized_exit_date.tz_convert(df.index.tz)
                else:
                    # DataFrame is timezone-naive, ensure trade dates are naive too
                    import pandas as pd
                    if isinstance(entry_date, pd.Timestamp) and entry_date.tz is not None:
                        normalized_entry_date = entry_date.tz_localize(None)
                    elif not isinstance(entry_date, pd.Timestamp):
                        normalized_entry_date = pd.to_datetime(entry_date)
                    
                    if isinstance(exit_date, pd.Timestamp) and exit_date.tz is not None:
                        normalized_exit_date = exit_date.tz_localize(None)
                    elif not isinstance(exit_date, pd.Timestamp):
                        normalized_exit_date = pd.to_datetime(exit_date)
                
                entry_idx = df.index.get_indexer([normalized_entry_date], method='nearest')[0]
                exit_idx = df.index.get_indexer([normalized_exit_date], method='nearest')[0]
                
                if entry_idx < 0 or exit_idx < 0:
                    # Date not found in DataFrame - exclude trade
                    include_trade = False
                    break
                
                entry_regime = df.iloc[entry_idx][filter_name]
                exit_regime = df.iloc[exit_idx][filter_name]
            except (KeyError, IndexError, AttributeError, TypeError) as e:
                # Date not found or column missing or timezone mismatch - exclude trade
                # Capture filter error for debugging
                from backtester.debug import get_crash_reporter
                crash_reporter = get_crash_reporter()
                
                if crash_reporter and crash_reporter.should_capture('filter_error', e, severity='error'):
                    crash_reporter.capture('filter_error', e,
                                          context={'filter_name': filter_name, 'trades_count': len(trades)},
                                          severity='error')
                
                include_trade = False
                break
            except Exception as e:
                # Other unexpected errors in filter application
                from backtester.debug import get_crash_reporter
                crash_reporter = get_crash_reporter()
                
                if crash_reporter and crash_reporter.should_capture('filter_error', e, severity='error'):
                    crash_reporter.capture('filter_error', e,
                                          context={'filter_name': filter_name, 'trades_count': len(trades)},
                                          severity='error')
                
                # Re-raise unexpected errors
                raise
            
            # Apply filter's matching logic
            matches = _check_matching_logic(
                filter_class.matching,
                entry_regime,
                exit_regime,
                target_regime
            )
            
            if not matches:
                include_trade = False
                break  # All filters must match
        
        if include_trade:
            filtered_trades.append(trade)
    
    return filtered_trades


def _check_matching_logic(
    matching: str,
    entry_regime: str,
    exit_regime: str,
    target_regime: str
) -> bool:
    """
    Check if trade matches based on matching logic.
    
    Args:
        matching: Matching logic ('entry', 'both', 'either')
        entry_regime: Regime at trade entry
        exit_regime: Regime at trade exit
        target_regime: Target regime to match
    
    Returns:
        True if trade matches, False otherwise
    """
    if matching == 'entry':
        return entry_regime == target_regime
    elif matching == 'both':
        return entry_regime == target_regime and exit_regime == target_regime
    elif matching == 'either':
        return entry_regime == target_regime or exit_regime == target_regime
    else:
        # Default to entry matching for unknown matching types
        return entry_regime == target_regime


def recalculate_metrics_with_filtered_trades(
    cerebro: bt.Cerebro,
    strategy_instance: bt.Strategy,
    initial_capital: float,
    filtered_trades: List[Dict[str, Any]],
    equity_curve: Optional[List[Dict[str, Any]]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> BacktestMetrics:
    """
    Recalculate metrics using filtered trades.
    
    Rebuilds equity curve from filtered trades and recalculates all metrics.
    This provides accurate metrics for the filtered trade subset.
    
    Args:
        cerebro: Backtrader Cerebro instance (after running)
        strategy_instance: Strategy instance from cerebro.run()
        initial_capital: Starting capital amount
        filtered_trades: List of filtered trades with entry/exit dates and PnL
        equity_curve: Optional original equity curve (will rebuild from filtered trades)
        start_date: Optional start date for calculating calendar/trading days
        end_date: Optional end date for calculating calendar/trading days
    
    Returns:
        BacktestMetrics object with metrics calculated from filtered trades
    
    Notes:
        - Rebuilds equity curve by simulating filtered trades sequentially
        - All metrics are recalculated based on filtered trade list
        - If filtered_trades is empty, returns metrics with zeros/defaults
    """
    if not filtered_trades:
        # No trades after filtering - return zero metrics
        # Use original equity curve if available, otherwise minimal curve
        if equity_curve:
            min_curve = [equity_curve[0], equity_curve[-1]] if len(equity_curve) >= 2 else equity_curve
        else:
            min_curve = [
                {'date': start_date or datetime.now(), 'value': initial_capital},
                {'date': end_date or datetime.now(), 'value': initial_capital}
            ]
        
        # Calculate metrics with zero trades
        metrics = calculate_metrics(
            cerebro,
            strategy_instance,
            initial_capital,
            equity_curve=min_curve,
            start_date=start_date,
            end_date=end_date
        )
        return metrics
    
    # Rebuild equity curve from filtered trades
    # Start with initial capital, apply each trade's PnL sequentially
    rebuilt_equity_curve = []
    current_value = initial_capital
    
    # Sort trades by entry date
    sorted_trades = sorted(filtered_trades, key=lambda t: t.get('entry_date', datetime.min))
    
    # Start with initial value at start_date or first trade entry
    first_entry = sorted_trades[0].get('entry_date', start_date) if sorted_trades else start_date
    if first_entry:
        rebuilt_equity_curve.append({'date': first_entry, 'value': initial_capital})
    
    # Build equity curve from filtered trades
    for trade in sorted_trades:
        entry_date = trade.get('entry_date')
        exit_date = trade.get('exit_date')
        pnl = trade.get('pnl', 0.0)
        
        if entry_date and exit_date:
            # Apply trade PnL at exit
            current_value += pnl
            rebuilt_equity_curve.append({'date': exit_date, 'value': current_value})
    
    # Add final point if end_date provided and different from last trade exit
    if end_date and rebuilt_equity_curve:
        last_date = rebuilt_equity_curve[-1]['date']
        if end_date != last_date:
            rebuilt_equity_curve.append({'date': end_date, 'value': current_value})
    
    # Replace strategy's trades_log with filtered trades for metrics calculation
    # Save original if exists
    original_trades_log = getattr(strategy_instance, 'trades_log', None)
    strategy_instance.trades_log = filtered_trades
    
    try:
        # Calculate metrics with filtered trades and rebuilt equity curve
        metrics = calculate_metrics(
            cerebro,
            strategy_instance,
            initial_capital,
            equity_curve=rebuilt_equity_curve,
            start_date=start_date,
            end_date=end_date
        )
    finally:
        # Restore original trades_log if it existed
        if original_trades_log is not None:
            strategy_instance.trades_log = original_trades_log
        elif hasattr(strategy_instance, 'trades_log'):
            delattr(strategy_instance, 'trades_log')
    
    return metrics

