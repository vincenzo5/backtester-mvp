"""
Metrics calculator for walk-forward optimization.

Calculates fitness functions and performance metrics from backtrader results.
Uses backtrader's built-in analyzers for accurate metric calculation.
"""

import backtrader as bt
import numpy as np
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class BacktestMetrics:
    """Container for calculated metrics from a backtest."""
    
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


def calculate_metrics(
    cerebro: bt.Cerebro,
    strategy_instance: bt.Strategy,
    initial_capital: float,
    equity_curve: Optional[List[Dict[str, Any]]] = None
) -> BacktestMetrics:
    """
    Calculate comprehensive metrics from backtrader cerebro and strategy.
    
    Args:
        cerebro: Backtrader Cerebro instance (after running)
        strategy_instance: Strategy instance from cerebro.run()
        initial_capital: Starting capital amount
        equity_curve: Optional pre-calculated equity curve
    
    Returns:
        BacktestMetrics object with all calculated metrics
    """
    final_value = cerebro.broker.getvalue()
    
    # Basic return metrics
    net_profit = final_value - initial_capital
    total_return_pct = (net_profit / initial_capital) * 100
    
    # Get analyzer results if available
    analyzers = cerebro.runresult if hasattr(cerebro, 'runresult') else []
    
    # Try to get trade analyzer
    trade_analyzer = None
    drawdown_analyzer = None
    sharpe_analyzer = None
    
    # Check if analyzers were added
    if hasattr(cerebro, 'analyzers'):
        trade_analyzer = cerebro.analyzers.trade.get_analysis() if hasattr(cerebro.analyzers, 'trade') else None
        drawdown_analyzer = cerebro.analyzers.drawdown.get_analysis() if hasattr(cerebro.analyzers, 'drawdown') else None
        sharpe_analyzer = cerebro.analyzers.sharpe.get_analysis() if hasattr(cerebro.analyzers, 'sharpe') else None
    
    # If no analyzers, get basic info from strategy
    num_trades = getattr(strategy_instance, 'buy_count', 0)
    
    # Try to get more detailed trade info
    if hasattr(strategy_instance, 'trades_log') and strategy_instance.trades_log:
        trades = strategy_instance.trades_log
        gross_profit = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0)
        gross_loss = abs(sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0))
        num_winning_trades = len([t for t in trades if t.get('pnl', 0) > 0])
        num_losing_trades = len([t for t in trades if t.get('pnl', 0) < 0])
    else:
        # Fallback to analyzer data
        if trade_analyzer:
            gross_profit = trade_analyzer.get('pnl', {}).get('net', {}).get('profit', 0.0)
            gross_loss = abs(trade_analyzer.get('pnl', {}).get('net', {}).get('loss', 0.0))
            num_winning_trades = trade_analyzer.get('won', {}).get('total', 0)
            num_losing_trades = trade_analyzer.get('lost', {}).get('total', 0)
        else:
            # Last resort: estimate from net profit
            gross_profit = max(net_profit, 0) * 0.6 if num_trades > 0 else 0.0
            gross_loss = abs(min(net_profit, 0)) * 0.6 if num_trades > 0 else 0.0
            num_winning_trades = int(num_trades * 0.5) if num_trades > 0 else 0
            num_losing_trades = num_trades - num_winning_trades
    
    # Profit factor
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    else:
        profit_factor = float('inf') if gross_profit > 0 else 0.0
    
    # Get drawdown info
    if drawdown_analyzer:
        max_drawdown = abs(drawdown_analyzer.get('max', {}).get('drawdown', 0.0))
    else:
        # Calculate from equity curve if available
        if equity_curve:
            max_drawdown = _calculate_max_drawdown(equity_curve, initial_capital)
            avg_drawdown = _calculate_avg_drawdown(equity_curve, initial_capital)
        else:
            max_drawdown = 0.0
            avg_drawdown = 0.0
    
    if equity_curve and avg_drawdown == 0.0:
        avg_drawdown = _calculate_avg_drawdown(equity_curve, initial_capital)
    
    # NP/Average DD
    if avg_drawdown > 0:
        np_avg_dd = net_profit / avg_drawdown
    else:
        np_avg_dd = float('inf') if net_profit > 0 else 0.0
    
    # Sharpe ratio
    if sharpe_analyzer:
        sharpe_ratio = sharpe_analyzer.get('sharperatio', 0.0)
    elif equity_curve:
        sharpe_ratio = _calculate_sharpe_ratio(equity_curve)
    else:
        sharpe_ratio = 0.0
    
    return BacktestMetrics(
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
        avg_drawdown=avg_drawdown
    )


def calculate_fitness(
    metrics: BacktestMetrics,
    fitness_function: str
) -> float:
    """
    Calculate fitness value based on fitness function name.
    
    Args:
        metrics: BacktestMetrics object
        fitness_function: Name of fitness function (net_profit, sharpe_ratio, etc.)
    
    Returns:
        Fitness value (higher is better)
    """
    fitness_map = {
        'net_profit': metrics.net_profit,
        'sharpe_ratio': metrics.sharpe_ratio,
        'max_dd': -metrics.max_drawdown,  # Negate because lower DD is better
        'profit_factor': metrics.profit_factor,
        'np_avg_dd': metrics.np_avg_dd,
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

