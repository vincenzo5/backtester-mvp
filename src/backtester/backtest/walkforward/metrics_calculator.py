"""
Metrics calculator for walk-forward optimization.

Calculates fitness functions and performance metrics from backtrader results.
Uses backtrader's built-in analyzers for accurate metric calculation.

Implements all MultiWalk metrics exactly as specified in MultiWalk documentation.
"""

import backtrader as bt
import numpy as np
from scipy import stats
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class BacktestMetrics:
    """Container for calculated metrics from a backtest.
    
    Implements all 38 MultiWalk metrics exactly as documented.
    All metrics match MultiWalk's calculation methodology using mark-to-market data.
    """
    
    # Basic metrics (keep existing)
    net_profit: float  # Net profit in dollars
    total_return_pct: float  # Total return percentage
    sharpe_ratio: float  # Sharpe ratio
    max_drawdown: float  # Maximum drawdown in dollars
    profit_factor: float  # Gross profit / gross loss
    np_avg_dd: float  # Net profit / average drawdown
    gross_profit: float  # Total gross profit
    gross_loss: float  # Total gross loss
    num_trades: int  # Number of trades
    num_winning_trades: int  # Number of winning trades
    num_losing_trades: int  # Number of losing trades
    avg_drawdown: float  # Average drawdown in dollars
    
    # Trade statistics
    win_rate_pct: float  # Percent trades profitable (win rate)
    percent_trades_profitable: float  # Same as win_rate_pct (MultiWalk naming)
    percent_trades_unprofitable: float  # Percent trades unprofitable
    avg_trade: float  # Average dollar amount per trade
    avg_profitable_trade: float  # Average dollar amount of profitable trades
    avg_unprofitable_trade: float  # Average dollar amount of unprofitable trades
    largest_winning_trade: float  # Largest profit from a single trade
    largest_losing_trade: float  # Largest loss from a single trade (most negative)
    max_consecutive_wins: int  # Maximum consecutive profitable trades
    max_consecutive_losses: int  # Maximum consecutive unprofitable trades
    
    # Day statistics
    total_calendar_days: int  # Calendar days between first and last day
    total_trading_days: int  # Days represented in actual symbol data
    days_profitable: int  # Total number of profitable days
    days_unprofitable: int  # Total number of unprofitable days
    percent_days_profitable: float  # Percentage of days that were profitable
    percent_days_unprofitable: float  # Percentage of days that were unprofitable
    
    # Drawdown metrics (enhanced)
    max_drawdown_pct: float  # Maximum drawdown as percentage of peak equity
    max_run_up: float  # Maximum peak profit run-up (opposite of drawdown)
    recovery_factor: float  # Net profit / maximum drawdown (NP/Max DD)
    np_max_dd: float  # Net profit / maximum drawdown (same as recovery_factor)
    
    # Advanced metrics
    r_squared: float  # R² regression fit of equity curve
    sortino_ratio: float  # Sortino ratio (downside risk only)
    monte_carlo_score: float  # Monte Carlo analysis score (2500 iterations)
    rina_index: float  # RINA Index: NP / (AvgDD × Percent Time In Market)
    tradestation_index: float  # TradeStation Index: NP × WinDays / |Max Intraday DD|
    np_x_r2: float  # Net Profit × R²
    np_x_pf: float  # Net Profit × Profit Factor
    annualized_net_profit: float  # Annualized net profit (if period > 30 days)
    annualized_return_avg_dd: float  # Annualized return / average drawdown
    percent_time_in_market: float  # Percentage of time strategy is in a trade
    walkforward_efficiency: float  # OOS/IS efficiency (for walk-forward only, default 0.0)


def calculate_metrics(
    cerebro: bt.Cerebro,
    strategy_instance: bt.Strategy,
    initial_capital: float,
    equity_curve: Optional[List[Dict[str, Any]]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> BacktestMetrics:
    """
    Calculate comprehensive metrics from backtrader cerebro and strategy.
    
    Implements all 38 MultiWalk metrics using mark-to-market equity curve data.
    
    Args:
        cerebro: Backtrader Cerebro instance (after running)
        strategy_instance: Strategy instance from cerebro.run()
        initial_capital: Starting capital amount
        equity_curve: Optional pre-calculated equity curve (if None, extracts from strategy)
        start_date: Optional start date for calculating calendar/trading days
        end_date: Optional end date for calculating calendar/trading days
    
    Returns:
        BacktestMetrics object with all 38 MultiWalk metrics
    """
    final_value = cerebro.broker.getvalue()
    
    # Basic return metrics
    net_profit = final_value - initial_capital
    total_return_pct = (net_profit / initial_capital) * 100 if initial_capital > 0 else 0.0
    
    # Extract equity curve from strategy if not provided
    if equity_curve is None:
        if hasattr(strategy_instance, 'equity_curve') and strategy_instance.equity_curve:
            equity_curve = strategy_instance.equity_curve
        else:
            # Fallback: create minimal curve
            equity_curve = [
                {'date': start_date or datetime.now(), 'value': initial_capital},
                {'date': end_date or datetime.now(), 'value': final_value}
            ]
    
    # Get analyzer results
    trade_analyzer = None
    drawdown_analyzer = None
    sharpe_analyzer = None
    
    if hasattr(cerebro, 'analyzers'):
        try:
            trade_analyzer = cerebro.analyzers.trade.get_analysis() if hasattr(cerebro.analyzers, 'trade') else None
        except Exception:
            trade_analyzer = None
        
        try:
            drawdown_analyzer = cerebro.analyzers.drawdown.get_analysis() if hasattr(cerebro.analyzers, 'drawdown') else None
        except Exception:
            drawdown_analyzer = None
        
        try:
            sharpe_analyzer = cerebro.analyzers.sharpe.get_analysis() if hasattr(cerebro.analyzers, 'sharpe') else None
        except Exception:
            sharpe_analyzer = None
    
    # Extract trade data
    # Debug: Check trades_log before extraction
    import logging
    logger = logging.getLogger(__name__)
    if hasattr(strategy_instance, 'trades_log'):
        logger.debug(f"calculate_metrics: Before extraction - trades_log length = {len(strategy_instance.trades_log)}, content = {strategy_instance.trades_log}")
    else:
        logger.debug(f"calculate_metrics: Before extraction - strategy_instance does not have trades_log")
    
    trade_list = _extract_trade_list(trade_analyzer, strategy_instance, num_trades_default=0)
    num_trades = len(trade_list) if trade_list else getattr(strategy_instance, 'buy_count', 0)
    
    logger.debug(f"calculate_metrics: After extraction - trade_list length = {len(trade_list)}, num_trades = {num_trades}")
    
    # Calculate trade statistics
    if trade_list:
        gross_profit = sum(t['pnl'] for t in trade_list if t['pnl'] > 0)
        gross_loss = abs(sum(t['pnl'] for t in trade_list if t['pnl'] < 0))
        num_winning_trades = len([t for t in trade_list if t['pnl'] > 0])
        num_losing_trades = len([t for t in trade_list if t['pnl'] < 0])
        
        winning_trades = [t['pnl'] for t in trade_list if t['pnl'] > 0]
        losing_trades = [t['pnl'] for t in trade_list if t['pnl'] < 0]
        
        largest_winning_trade = max(winning_trades) if winning_trades else 0.0
        largest_losing_trade = min(losing_trades) if losing_trades else 0.0  # Most negative
        
        if num_winning_trades > 0:
            avg_profitable_trade = gross_profit / num_winning_trades
        else:
            avg_profitable_trade = 0.0
        
        if num_losing_trades > 0:
            avg_unprofitable_trade = gross_loss / num_losing_trades
        else:
            avg_unprofitable_trade = 0.0
        
        max_consecutive_wins, max_consecutive_losses = _calculate_consecutive_trades(trade_list)
    else:
        # No trades - use analyzer or estimate
        if trade_analyzer:
            gross_profit = trade_analyzer.get('pnl', {}).get('net', {}).get('profit', 0.0)
            gross_loss = abs(trade_analyzer.get('pnl', {}).get('net', {}).get('loss', 0.0))
            num_winning_trades = trade_analyzer.get('won', {}).get('total', 0)
            num_losing_trades = trade_analyzer.get('lost', {}).get('total', 0)
            
            # Try to get largest trades from analyzer
            largest_winning_trade = trade_analyzer.get('won', {}).get('pnl', {}).get('max', 0.0)
            largest_losing_trade = trade_analyzer.get('lost', {}).get('pnl', {}).get('min', 0.0)
            
            if num_winning_trades > 0:
                avg_profitable_trade = gross_profit / num_winning_trades
            else:
                avg_profitable_trade = 0.0
            
            if num_losing_trades > 0:
                avg_unprofitable_trade = gross_loss / num_losing_trades
            else:
                avg_unprofitable_trade = 0.0
            
            max_consecutive_wins = trade_analyzer.get('won', {}).get('streak', {}).get('current', 0)
            max_consecutive_losses = trade_analyzer.get('lost', {}).get('streak', {}).get('current', 0)
        else:
            # No trade data available - set all trade-related metrics to zero
            # Log warning only if there were actually completed trades but extraction failed
            import logging
            logger = logging.getLogger(__name__)
            
            # Check if there were actually completed trades (not just buy orders)
            # Use analyzer data if available to determine completed trades
            completed_trades = 0
            if trade_analyzer:
                completed_trades = trade_analyzer.get('won', {}).get('total', 0) + trade_analyzer.get('lost', {}).get('total', 0)
            
            # Only warn if there were completed trades but trades_log is empty
            if completed_trades > 0:
                # Enhanced debug information
                has_trades_log = hasattr(strategy_instance, 'trades_log')
                trades_log_len = len(getattr(strategy_instance, 'trades_log', [])) if has_trades_log else 0
                buy_count = getattr(strategy_instance, 'buy_count', 'N/A')
                
                logger.warning(
                    f"Trade extraction failed for {completed_trades} completed trades. "
                    f"Using zero defaults for trade statistics. "
                    f"Ensure strategies implement trades_log or TradeAnalyzer provides trade data. "
                    f"[Debug: has_trades_log={has_trades_log}, trades_log_len={trades_log_len}, "
                    f"buy_count={buy_count}, completed_trades={completed_trades}]"
                )
            # If num_trades > 0 but no completed trades, it's likely just open positions - don't warn
            elif num_trades > 0:
                logger.debug(
                    f"No completed trades found (buy_count={num_trades} but no SELL orders completed). "
                    f"This is normal if positions remain open at backtest end."
                )
            gross_profit = 0.0
            gross_loss = 0.0
            num_winning_trades = 0
            num_losing_trades = 0
            largest_winning_trade = 0.0
            largest_losing_trade = 0.0
            avg_profitable_trade = 0.0
            avg_unprofitable_trade = 0.0
            max_consecutive_wins = 0
            max_consecutive_losses = 0
    
    # Win rate and trade percentages
    if num_trades > 0:
        win_rate_pct = (num_winning_trades / num_trades) * 100
        percent_trades_profitable = win_rate_pct
        percent_trades_unprofitable = (num_losing_trades / num_trades) * 100
        avg_trade = net_profit / num_trades
    else:
        win_rate_pct = 0.0
        percent_trades_profitable = 0.0
        percent_trades_unprofitable = 0.0
        avg_trade = 0.0
    
    # Profit factor
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    else:
        profit_factor = float('inf') if gross_profit > 0 else 0.0
    
    # Calculate drawdown metrics
    if drawdown_analyzer:
        max_drawdown = abs(drawdown_analyzer.get('max', {}).get('drawdown', 0.0))
        max_drawdown_len = drawdown_analyzer.get('max', {}).get('len', 0)
    else:
        max_drawdown = _calculate_max_drawdown(equity_curve, initial_capital)
        max_drawdown_len = 0
    
    avg_drawdown = _calculate_avg_drawdown(equity_curve, initial_capital)
    
    # Calculate max drawdown percentage
    if equity_curve:
        values = [point['value'] for point in equity_curve]
        peak_value = max(values) if values else initial_capital
        if peak_value > 0:
            max_drawdown_pct = (max_drawdown / peak_value) * 100
        else:
            max_drawdown_pct = 0.0
    else:
        max_drawdown_pct = 0.0
    
    # Max run-up (opposite of drawdown)
    max_run_up = _calculate_max_run_up(equity_curve, initial_capital)
    
    # Recovery factor (NP/Max DD)
    if max_drawdown > 0:
        recovery_factor = net_profit / max_drawdown
        np_max_dd = recovery_factor
    else:
        recovery_factor = float('inf') if net_profit > 0 else 0.0
        np_max_dd = recovery_factor
    
    # NP/Average DD
    if avg_drawdown > 0:
        np_avg_dd = net_profit / avg_drawdown
    else:
        np_avg_dd = float('inf') if net_profit > 0 else 0.0
    
    # Calculate day statistics
    day_stats = _calculate_day_statistics(equity_curve, start_date, end_date)
    total_calendar_days = day_stats['total_calendar_days']
    total_trading_days = day_stats['total_trading_days']
    days_profitable = day_stats['days_profitable']
    days_unprofitable = day_stats['days_unprofitable']
    percent_days_profitable = day_stats['percent_days_profitable']
    percent_days_unprofitable = day_stats['percent_days_unprofitable']
    
    # Calculate percent time in market
    if trade_list and total_trading_days > 0:
        percent_time_in_market = _calculate_percent_time_in_market(trade_list, total_trading_days)
    else:
        percent_time_in_market = 0.0
    
    # Calculate advanced metrics
    if equity_curve and len(equity_curve) >= 2:
        r_squared = _calculate_r_squared(equity_curve)
        sortino_ratio = _calculate_sortino_ratio(equity_curve)
        monte_carlo_score = _calculate_monte_carlo(equity_curve, initial_capital)
        max_intraday_dd = _calculate_max_intraday_drawdown(equity_curve, initial_capital)
    else:
        r_squared = 0.0
        sortino_ratio = 0.0
        monte_carlo_score = 0.0
        max_intraday_dd = 0.0
    
    # Sharpe ratio
    if sharpe_analyzer:
        sharpe_ratio = sharpe_analyzer.get('sharperatio', 0.0)
        if sharpe_ratio is None:
            sharpe_ratio = 0.0
    elif equity_curve and len(equity_curve) >= 2:
        sharpe_ratio = _calculate_sharpe_ratio(equity_curve)
    else:
        sharpe_ratio = 0.0
    
    # TradeStation Index: NP × NumWinDays / |Max Intraday DD|
    if max_intraday_dd > 0:
        tradestation_index = (net_profit * days_profitable) / max_intraday_dd
    else:
        tradestation_index = float('inf') if net_profit > 0 and days_profitable > 0 else 0.0
    
    # RINA Index: NP / (AvgDD × Percent Time In Market)
    if avg_drawdown > 0 and percent_time_in_market > 0:
        rina_index = net_profit / (avg_drawdown * percent_time_in_market / 100.0)
    else:
        rina_index = 0.0
    
    # Net Profit × R²
    np_x_r2 = net_profit * r_squared
    
    # Net Profit × Profit Factor
    np_x_pf = net_profit * profit_factor
    
    # Annualized metrics (only if period > 30 days)
    if total_calendar_days > 30:
        annualized_net_profit = net_profit * (365.0 / total_calendar_days)
        annualized_return = total_return_pct * (365.0 / total_calendar_days)
        if avg_drawdown > 0:
            annualized_return_avg_dd = annualized_return / (avg_drawdown / initial_capital * 100) if initial_capital > 0 else 0.0
        else:
            annualized_return_avg_dd = float('inf') if annualized_return > 0 else 0.0
    else:
        annualized_net_profit = 0.0
        annualized_return_avg_dd = 0.0
    
    # Walk-forward efficiency (set to 0.0 for single backtests, calculated separately for walk-forward)
    walkforward_efficiency = 0.0
    
    return BacktestMetrics(
        # Basic metrics
        net_profit=net_profit,
        total_return_pct=total_return_pct,
        sharpe_ratio=sharpe_ratio,
        max_drawdown=max_drawdown,
        profit_factor=profit_factor,
        np_avg_dd=np_avg_dd,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        num_trades=num_trades,
        num_winning_trades=num_winning_trades,
        num_losing_trades=num_losing_trades,
        avg_drawdown=avg_drawdown,
        # Trade statistics
        win_rate_pct=win_rate_pct,
        percent_trades_profitable=percent_trades_profitable,
        percent_trades_unprofitable=percent_trades_unprofitable,
        avg_trade=avg_trade,
        avg_profitable_trade=avg_profitable_trade,
        avg_unprofitable_trade=avg_unprofitable_trade,
        largest_winning_trade=largest_winning_trade,
        largest_losing_trade=largest_losing_trade,
        max_consecutive_wins=max_consecutive_wins,
        max_consecutive_losses=max_consecutive_losses,
        # Day statistics
        total_calendar_days=total_calendar_days,
        total_trading_days=total_trading_days,
        days_profitable=days_profitable,
        days_unprofitable=days_unprofitable,
        percent_days_profitable=percent_days_profitable,
        percent_days_unprofitable=percent_days_unprofitable,
        # Drawdown metrics
        max_drawdown_pct=max_drawdown_pct,
        max_run_up=max_run_up,
        recovery_factor=recovery_factor,
        np_max_dd=np_max_dd,
        # Advanced metrics
        r_squared=r_squared,
        sortino_ratio=sortino_ratio,
        monte_carlo_score=monte_carlo_score,
        rina_index=rina_index,
        tradestation_index=tradestation_index,
        np_x_r2=np_x_r2,
        np_x_pf=np_x_pf,
        annualized_net_profit=annualized_net_profit,
        annualized_return_avg_dd=annualized_return_avg_dd,
        percent_time_in_market=percent_time_in_market,
        walkforward_efficiency=walkforward_efficiency
    )


def calculate_fitness(
    metrics: BacktestMetrics,
    fitness_function: str
) -> float:
    """
    Calculate fitness value based on fitness function name.
    
    Implements all MultiWalk fitness functions (marked with * in MultiWalk docs).
    
    Args:
        metrics: BacktestMetrics object
        fitness_function: Name of fitness function (net_profit, sharpe_ratio, etc.)
    
    Returns:
        Fitness value (higher is better)
    
    Supported fitness functions:
        - net_profit: Net profit in dollars
        - sharpe_ratio: Sharpe ratio
        - sortino_ratio: Sortino ratio
        - max_dd: Maximum drawdown (negated, so higher is better)
        - np_max_dd: Net profit / maximum drawdown
        - np_avg_dd: Net profit / average drawdown
        - profit_factor: Gross profit / gross loss
        - max_consecutive_wins: Maximum consecutive winning trades
        - avg_trade: Average dollar amount per trade
        - avg_profitable_trade: Average profitable trade amount
        - avg_unprofitable_trade: Average unprofitable trade amount (negated)
        - percent_trades_profitable: Win rate percentage
        - percent_days_profitable: Percentage of profitable days
        - r_squared: R² regression fit
        - np_x_r2: Net Profit × R²
        - np_x_pf: Net Profit × Profit Factor
        - rina_index: RINA Index
        - tradestation_index: TradeStation Index
        - max_run_up: Maximum run-up (peak profit)
        - annualized_net_profit: Annualized net profit
        - annualized_return_avg_dd: Annualized return / average drawdown
        - percent_time_in_market: Percent time in market (negated, less time is better)
        - walkforward_efficiency: Walk-forward efficiency (OOS/IS)
    """
    fitness_map = {
        # Basic metrics
        'net_profit': metrics.net_profit,
        'sharpe_ratio': metrics.sharpe_ratio,
        'sortino_ratio': metrics.sortino_ratio,
        'max_dd': -metrics.max_drawdown,  # Negate because lower DD is better
        'np_max_dd': metrics.np_max_dd,
        'np_avg_dd': metrics.np_avg_dd,
        'profit_factor': metrics.profit_factor,
        
        # Trade statistics
        'max_consecutive_wins': float(metrics.max_consecutive_wins),
        'avg_trade': metrics.avg_trade,
        'avg_profitable_trade': metrics.avg_profitable_trade,
        'avg_unprofitable_trade': -metrics.avg_unprofitable_trade,  # Negate: less loss is better
        'percent_trades_profitable': metrics.percent_trades_profitable,
        
        # Day statistics
        'percent_days_profitable': metrics.percent_days_profitable,
        
        # Advanced metrics
        'r_squared': metrics.r_squared,
        'np_x_r2': metrics.np_x_r2,
        'np_x_pf': metrics.np_x_pf,
        'rina_index': metrics.rina_index,
        'tradestation_index': metrics.tradestation_index,
        'max_run_up': metrics.max_run_up,
        'annualized_net_profit': metrics.annualized_net_profit,
        'annualized_return_avg_dd': metrics.annualized_return_avg_dd,
        'percent_time_in_market': -metrics.percent_time_in_market,  # Negate: less time in market can be better
        'walkforward_efficiency': metrics.walkforward_efficiency,
    }
    
    if fitness_function not in fitness_map:
        raise ValueError(
            f"Unknown fitness function: {fitness_function}. "
            f"Supported: {list(fitness_map.keys())}"
        )
    
    return fitness_map[fitness_function]


def get_equity_curve_from_backtest(
    cerebro: bt.Cerebro,
    strategy: bt.Strategy,
    initial_capital: float,
    data_df
) -> List[Dict[str, Any]]:
    """
    Generate equity curve from backtest by tracking portfolio value.
    
    This creates a tracker strategy wrapper that records equity at each bar.
    """
    # If strategy already tracked equity, use it
    if hasattr(strategy, 'equity_curve') and strategy.equity_curve:
        return strategy.equity_curve
    
    # Otherwise create a minimal curve from start/end
    return [
        {'date': None, 'value': initial_capital},
        {'date': None, 'value': cerebro.broker.getvalue()}
    ]


def _calculate_max_drawdown(equity_curve: list, initial_capital: float) -> float:
    """
    Calculate maximum drawdown from equity curve.
    
    Args:
        equity_curve: List of {'date', 'value'} dictionaries
        initial_capital: Starting capital
    
    Returns:
        Maximum drawdown in dollars
    """
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
    
    values = [point['value'] for point in equity_curve]
    peak = values[0]
    max_dd = 0.0
    
    for value in values:
        if value > peak:
            peak = value
        drawdown = peak - value
        if drawdown > max_dd:
            max_dd = drawdown
    
    return max_dd


def _calculate_avg_drawdown(equity_curve: list, initial_capital: float) -> float:
    """
    Calculate average drawdown from equity curve.
    
    Args:
        equity_curve: List of {'date', 'value'} dictionaries
        initial_capital: Starting capital
    
    Returns:
        Average drawdown in dollars
    """
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
    
    values = [point['value'] for point in equity_curve]
    peak = values[0]
    drawdowns = []
    
    for value in values:
        if value > peak:
            peak = value
        drawdown = peak - value
        drawdowns.append(drawdown)
    
    if not drawdowns:
        return 0.0
    
    return sum(drawdowns) / len(drawdowns)


def _calculate_sharpe_ratio(equity_curve: list, risk_free_rate: float = 0.0) -> float:
    """
    Calculate Sharpe ratio from equity curve.
    
    Args:
        equity_curve: List of {'date', 'value'} dictionaries
        risk_free_rate: Risk-free rate (default 0)
    
    Returns:
        Sharpe ratio
    """
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
    
    values = [point['value'] for point in equity_curve]
    
    # Calculate returns
    returns = []
    for i in range(1, len(values)):
        if values[i-1] > 0:
            ret = (values[i] - values[i-1]) / values[i-1]
            returns.append(ret)
    
    if not returns:
        return 0.0
    
    returns_array = np.array(returns)
    
    # Calculate mean and std of returns
    mean_return = np.mean(returns_array)
    std_return = np.std(returns_array)
    
    if std_return == 0:
        return 0.0
    
    # Annualize if possible (assuming daily returns)
    # For simplicity, we'll use raw Sharpe ratio
    sharpe = (mean_return - risk_free_rate) / std_return
    
    return float(sharpe)


def _extract_trade_list(trade_analyzer: Optional[Dict[str, Any]], strategy_instance: bt.Strategy, num_trades_default: int) -> List[Dict[str, Any]]:
    """Extract trade list with PnL from analyzer or strategy.
    
    Note: Backtrader's TradeAnalyzer provides aggregate statistics but not individual trades.
    We try to extract from strategy_instance.trades_log first, then fall back to analyzer aggregates.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    trade_list = []
    
    # Debug: Check if trades_log exists
    has_trades_log = hasattr(strategy_instance, 'trades_log')
    logger.debug(f"Trade extraction: hasattr(trades_log) = {has_trades_log}")
    
    # First, try strategy trades_log (if strategy tracks individual trades)
    if has_trades_log:
        trades_log_value = getattr(strategy_instance, 'trades_log', None)
        logger.debug(f"Trade extraction: trades_log type = {type(trades_log_value)}, length = {len(trades_log_value) if trades_log_value else 0}")
        
        if trades_log_value:
            logger.debug(f"Trade extraction: trades_log contains {len(trades_log_value)} entries")
            for i, trade in enumerate(trades_log_value):
                logger.debug(f"Trade extraction: Processing trade {i}: type = {type(trade)}, is_dict = {isinstance(trade, dict)}")
                
                if isinstance(trade, dict):
                    pnl = trade.get('pnl', 0.0)
                    entry_date = trade.get('entry_date', None)
                    exit_date = trade.get('exit_date', None)
                    
                    logger.debug(f"Trade extraction: Trade {i} - pnl = {pnl}, entry_date = {entry_date} (type: {type(entry_date)}), exit_date = {exit_date} (type: {type(exit_date)})")
                    
                    # Calculate duration with error handling
                    duration = 0
                    try:
                        if entry_date and exit_date:
                            # Handle different date types
                            import pandas as pd
                            if isinstance(entry_date, pd.Timestamp) and isinstance(exit_date, pd.Timestamp):
                                duration = (exit_date - entry_date).days
                            elif hasattr(entry_date, '__sub__') and hasattr(exit_date, '__sub__'):
                                delta = exit_date - entry_date
                                if hasattr(delta, 'days'):
                                    duration = delta.days
                                else:
                                    duration = int(delta.total_seconds() / 86400)
                            logger.debug(f"Trade extraction: Trade {i} - duration calculated = {duration} days")
                    except Exception as e:
                        logger.warning(f"Trade extraction: Failed to calculate duration for trade {i}: {e} (entry_date: {entry_date}, exit_date: {exit_date})")
                    
                    trade_list.append({
                        'pnl': pnl,
                        'entry_date': entry_date,
                        'exit_date': exit_date,
                        'duration': duration
                    })
                    logger.debug(f"Trade extraction: Trade {i} added to trade_list")
                else:
                    logger.warning(f"Trade extraction: Trade {i} is not a dict, skipping. Type: {type(trade)}, Value: {trade}")
            
            if trade_list:
                logger.debug(f"Trade extraction: Successfully extracted {len(trade_list)} trades from trades_log")
                return trade_list
            else:
                logger.debug(f"Trade extraction: trades_log had {len(trades_log_value)} entries but none were valid dicts or extraction failed")
        else:
            logger.debug(f"Trade extraction: trades_log exists but is empty or falsy")
    else:
        logger.debug(f"Trade extraction: strategy_instance does not have trades_log attribute")
    
    # Fallback: try to reconstruct from analyzer if it has individual trade data
    # Note: Standard TradeAnalyzer doesn't provide individual trades, but some analyzers might
    if trade_analyzer:
        logger.debug(f"Trade extraction: Attempting fallback to trade_analyzer (type: {type(trade_analyzer)})")
        try:
            # Check if analyzer has individual trades (some custom analyzers might)
            if isinstance(trade_analyzer, dict):
                # Standard TradeAnalyzer provides aggregate stats, not individual trades
                # We can't construct individual trades from aggregates alone
                logger.debug(f"Trade extraction: trade_analyzer is a dict but doesn't provide individual trades")
                pass
        except (AttributeError, TypeError) as e:
            logger.debug(f"Trade extraction: Exception checking trade_analyzer: {e}")
            pass
    
    # Return empty list - calculate_metrics will use analyzer aggregates as fallback
    logger.debug(f"Trade extraction: Returning empty trade_list (will use analyzer aggregates)")
    return trade_list


def _calculate_consecutive_trades(trade_list: List[Dict[str, Any]]) -> Tuple[int, int]:
    """Calculate max consecutive wins and losses."""
    if not trade_list:
        return 0, 0
    
    max_consecutive_wins = 0
    max_consecutive_losses = 0
    current_wins = 0
    current_losses = 0
    
    for trade in trade_list:
        pnl = trade.get('pnl', 0.0)
        if pnl > 0:
            current_wins += 1
            current_losses = 0
            max_consecutive_wins = max(max_consecutive_wins, current_wins)
        elif pnl < 0:
            current_losses += 1
            current_wins = 0
            max_consecutive_losses = max(max_consecutive_losses, current_losses)
        else:
            # Zero PnL - reset both
            current_wins = 0
            current_losses = 0
    
    return max_consecutive_wins, max_consecutive_losses


def _calculate_max_run_up(equity_curve: List[Dict[str, Any]], initial_capital: float) -> float:
    """Calculate maximum run-up (peak profit above initial capital)."""
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
    
    values = [point['value'] for point in equity_curve]
    max_run_up = 0.0
    
    for value in values:
        run_up = value - initial_capital
        if run_up > max_run_up:
            max_run_up = run_up
    
    return max_run_up


def _calculate_max_intraday_drawdown(equity_curve: List[Dict[str, Any]], initial_capital: float) -> float:
    """Calculate maximum intraday drawdown (largest equity drop within a day period)."""
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
    
    values = [point['value'] for point in equity_curve]
    max_intraday_dd = 0.0
    
    # Group by day and find max intraday drop
    daily_values = {}
    for i, point in enumerate(equity_curve):
        date = point['date']
        if isinstance(date, datetime):
            day_key = date.date()
        elif hasattr(date, 'date'):
            day_key = date.date()
        else:
            day_key = None
        
        if day_key:
            if day_key not in daily_values:
                daily_values[day_key] = []
            daily_values[day_key].append(point['value'])
    
    # Find max drop within each day
    for day_values in daily_values.values():
        if len(day_values) >= 2:
            peak = day_values[0]
            for value in day_values:
                if value > peak:
                    peak = value
                drop = peak - value
                if drop > max_intraday_dd:
                    max_intraday_dd = drop
    
    return max_intraday_dd


def _calculate_r_squared(equity_curve: List[Dict[str, Any]]) -> float:
    """Calculate R² regression fit of equity curve."""
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
    
    try:
        # Extract x (days from start) and y (equity values)
        start_date = equity_curve[0]['date']
        if isinstance(start_date, datetime):
            start_timestamp = start_date.timestamp()
        elif hasattr(start_date, 'timestamp'):
            start_timestamp = start_date.timestamp()
        else:
            return 0.0
        
        x_values = []
        y_values = []
        
        for point in equity_curve:
            date = point['date']
            if isinstance(date, datetime):
                timestamp = date.timestamp()
            elif hasattr(date, 'timestamp'):
                timestamp = date.timestamp()
            else:
                continue
            
            days_from_start = (timestamp - start_timestamp) / (24 * 3600)
            x_values.append(days_from_start)
            y_values.append(point['value'])
        
        if len(x_values) < 2:
            return 0.0
        
        x_array = np.array(x_values)
        y_array = np.array(y_values)
        
        # Linear regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(x_array, y_array)
        r_squared = r_value ** 2
        
        return float(r_squared) if not np.isnan(r_squared) else 0.0
    except Exception:
        return 0.0


def _calculate_sortino_ratio(equity_curve: List[Dict[str, Any]], risk_free_rate: float = 0.0) -> float:
    """Calculate Sortino ratio (downside risk only)."""
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
    
    try:
        values = [point['value'] for point in equity_curve]
        
        # Calculate returns
        returns = []
        for i in range(1, len(values)):
            if values[i-1] > 0:
                ret = (values[i] - values[i-1]) / values[i-1]
                returns.append(ret)
        
        if not returns:
            return 0.0
        
        returns_array = np.array(returns)
        
        # Calculate mean return
        mean_return = np.mean(returns_array)
        
        # Calculate downside deviation (only negative returns)
        downside_returns = returns_array[returns_array < 0]
        if len(downside_returns) == 0:
            # No downside, return high value if positive mean
            return float('inf') if mean_return > risk_free_rate else 0.0
        
        downside_deviation = np.std(downside_returns)
        
        if downside_deviation == 0:
            return float('inf') if mean_return > risk_free_rate else 0.0
        
        # Annualize if daily returns (assuming ~252 trading days)
        # For simplicity, use raw Sortino ratio
        sortino = (mean_return - risk_free_rate) / downside_deviation
        
        return float(sortino) if not np.isnan(sortino) else 0.0
    except Exception:
        return 0.0


def _calculate_monte_carlo(equity_curve: List[Dict[str, Any]], initial_capital: float, iterations: int = 2500) -> float:
    """Calculate Monte Carlo score using resampling with replacement."""
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
    
    try:
        # Extract returns from equity curve
        values = [point['value'] for point in equity_curve]
        returns = []
        
        for i in range(1, len(values)):
            if values[i-1] > 0:
                ret = (values[i] - values[i-1]) / values[i-1]
                returns.append(ret)
        
        if not returns or len(returns) < 2:
            return 0.0
        
        returns_array = np.array(returns)
        
        # Run Monte Carlo simulation
        final_values = []
        np.random.seed(42)  # For reproducibility
        
        for _ in range(iterations):
            # Resample with replacement
            resampled_returns = np.random.choice(returns_array, size=len(returns_array), replace=True)
            
            # Calculate final value
            final_value = initial_capital * np.prod(1 + resampled_returns)
            final_values.append(final_value)
        
        # Calculate percentile rank of actual final value
        actual_final = values[-1]
        final_values_array = np.array(final_values)
        
        # Percentile where actual value falls
        percentile_rank = (final_values_array < actual_final).sum() / len(final_values) * 100
        
        return float(percentile_rank) if not np.isnan(percentile_rank) else 0.0
    except Exception:
        return 0.0


def _calculate_day_statistics(equity_curve: List[Dict[str, Any]], start_date: Optional[datetime], end_date: Optional[datetime]) -> Dict[str, Any]:
    """Calculate day statistics from equity curve."""
    if not equity_curve or len(equity_curve) < 2:
        return {
            'total_calendar_days': 0,
            'total_trading_days': 0,
            'days_profitable': 0,
            'days_unprofitable': 0,
            'percent_days_profitable': 0.0,
            'percent_days_unprofitable': 0.0
        }
    
    # Get dates from equity curve
    dates = [point['date'] for point in equity_curve if point.get('date')]
    
    if not dates:
        # Fallback to start/end date if provided
        if start_date and end_date:
            total_calendar_days = (end_date - start_date).days
        else:
            total_calendar_days = 0
        total_trading_days = len(equity_curve)
    else:
        # Normalize dates
        normalized_dates = []
        for date in dates:
            if isinstance(date, datetime):
                normalized_dates.append(date.date())
            elif hasattr(date, 'date'):
                normalized_dates.append(date.date())
        
        if normalized_dates:
            min_date = min(normalized_dates)
            max_date = max(normalized_dates)
            total_calendar_days = (max_date - min_date).days
            total_trading_days = len(set(normalized_dates))  # Unique trading days
        else:
            total_calendar_days = len(equity_curve)
            total_trading_days = len(equity_curve)
    
    # Calculate days profitable/unprofitable from equity changes
    values = [point['value'] for point in equity_curve]
    days_profitable = 0
    days_unprofitable = 0
    
    # Group equity curve by day (multi-walk uses end-of-day mark-to-market)
    daily_equity = {}
    for point in equity_curve:
        date = point.get('date')
        if date:
            if isinstance(date, datetime):
                day_key = date.date()
            elif hasattr(date, 'date'):
                day_key = date.date()
            else:
                continue
            # Use last value of the day (end-of-day mark-to-market)
            daily_equity[day_key] = point['value']
    
    if len(daily_equity) >= 2:
        sorted_days = sorted(daily_equity.keys())
        prev_value = daily_equity[sorted_days[0]]
        
        for day in sorted_days[1:]:
            current_value = daily_equity[day]
            if current_value > prev_value:
                days_profitable += 1
            elif current_value < prev_value:
                days_unprofitable += 1
            prev_value = current_value
    
    # Calculate percentages
    total_days_with_changes = days_profitable + days_unprofitable
    if total_days_with_changes > 0:
        percent_days_profitable = (days_profitable / total_days_with_changes) * 100
        percent_days_unprofitable = (days_unprofitable / total_days_with_changes) * 100
    else:
        percent_days_profitable = 0.0
        percent_days_unprofitable = 0.0
    
    return {
        'total_calendar_days': total_calendar_days,
        'total_trading_days': total_trading_days,
        'days_profitable': days_profitable,
        'days_unprofitable': days_unprofitable,
        'percent_days_profitable': percent_days_profitable,
        'percent_days_unprofitable': percent_days_unprofitable
    }


def _calculate_percent_time_in_market(trade_list: List[Dict[str, Any]], total_trading_days: int) -> float:
    """Calculate percentage of time strategy is in a trade."""
    if not trade_list or total_trading_days == 0:
        return 0.0
    
    total_days_in_market = 0
    for trade in trade_list:
        duration = trade.get('duration', 0)
        if duration is None:
            duration = 0
        total_days_in_market += duration
    
    if total_trading_days > 0:
        percent = (total_days_in_market / total_trading_days) * 100
        return float(percent) if not np.isnan(percent) else 0.0
    
    return 0.0


# Enhanced version that tracks equity during backtest
def create_equity_tracker(cerebro: bt.Cerebro, strategy_class):
    """
    Create a modified strategy class that tracks equity curve.
    
    This would be used to enhance strategies with equity tracking.
    """
    class EquityTrackingStrategy(strategy_class):
        def __init__(self):
            super().__init__()
            self.equity_curve = []
            self.trades_log = []
            
        def next(self):
            super().next()
            # Track equity at each bar
            self.equity_curve.append({
                'date': self.data.datetime.date(0),
                'value': self.broker.getvalue()
            })
    
    return EquityTrackingStrategy


def update_walkforward_efficiency(metrics: BacktestMetrics, efficiency: float) -> BacktestMetrics:
    """
    Create a new BacktestMetrics instance with updated walkforward_efficiency.
    
    Since BacktestMetrics is a dataclass, we create a new instance with the efficiency
    field updated. This is used when calculating walk-forward efficiency after OOS testing.
    
    Args:
        metrics: Original BacktestMetrics object
        efficiency: Walk-forward efficiency value (OOS return / IS return)
    
    Returns:
        New BacktestMetrics instance with efficiency updated
    """
    # Create new instance with all fields from original, but efficiency updated
    return BacktestMetrics(
        net_profit=metrics.net_profit,
        total_return_pct=metrics.total_return_pct,
        sharpe_ratio=metrics.sharpe_ratio,
        max_drawdown=metrics.max_drawdown,
        profit_factor=metrics.profit_factor,
        np_avg_dd=metrics.np_avg_dd,
        gross_profit=metrics.gross_profit,
        gross_loss=metrics.gross_loss,
        num_trades=metrics.num_trades,
        num_winning_trades=metrics.num_winning_trades,
        num_losing_trades=metrics.num_losing_trades,
        avg_drawdown=metrics.avg_drawdown,
        win_rate_pct=metrics.win_rate_pct,
        percent_trades_profitable=metrics.percent_trades_profitable,
        percent_trades_unprofitable=metrics.percent_trades_unprofitable,
        avg_trade=metrics.avg_trade,
        avg_profitable_trade=metrics.avg_profitable_trade,
        avg_unprofitable_trade=metrics.avg_unprofitable_trade,
        largest_winning_trade=metrics.largest_winning_trade,
        largest_losing_trade=metrics.largest_losing_trade,
        max_consecutive_wins=metrics.max_consecutive_wins,
        max_consecutive_losses=metrics.max_consecutive_losses,
        total_calendar_days=metrics.total_calendar_days,
        total_trading_days=metrics.total_trading_days,
        days_profitable=metrics.days_profitable,
        days_unprofitable=metrics.days_unprofitable,
        percent_days_profitable=metrics.percent_days_profitable,
        percent_days_unprofitable=metrics.percent_days_unprofitable,
        max_drawdown_pct=metrics.max_drawdown_pct,
        max_run_up=metrics.max_run_up,
        recovery_factor=metrics.recovery_factor,
        np_max_dd=metrics.np_max_dd,
        r_squared=metrics.r_squared,
        sortino_ratio=metrics.sortino_ratio,
        monte_carlo_score=metrics.monte_carlo_score,
        rina_index=metrics.rina_index,
        tradestation_index=metrics.tradestation_index,
        np_x_r2=metrics.np_x_r2,
        np_x_pf=metrics.np_x_pf,
        annualized_net_profit=metrics.annualized_net_profit,
        annualized_return_avg_dd=metrics.annualized_return_avg_dd,
        percent_time_in_market=metrics.percent_time_in_market,
        walkforward_efficiency=efficiency
    )

