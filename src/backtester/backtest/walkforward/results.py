"""
Results and reporting for walk-forward optimization.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

from backtester.backtest.walkforward.metrics_calculator import BacktestMetrics


@dataclass
class WalkForwardWindowResult:
    """Results from a single walk-forward window."""
    
    window_index: int
    in_sample_start: str
    in_sample_end: str
    out_sample_start: str
    out_sample_end: str
    
    # Best parameters from in-sample optimization
    best_parameters: Dict[str, int]
    
    # In-sample metrics (from optimization)
    in_sample_metrics: Optional[BacktestMetrics] = None
    
    # Out-of-sample metrics (from testing)
    out_sample_metrics: Optional[BacktestMetrics] = None
    
    # Optimization time
    optimization_time: float = 0.0
    
    # Out-of-sample backtest time
    oos_backtest_time: float = 0.0


@dataclass
class WalkForwardResults:
    """Aggregated results from walk-forward analysis."""
    
    symbol: str
    timeframe: str
    period_str: str  # e.g., "1Y/6M"
    fitness_function: str
    
    # Per-window results
    window_results: List[WalkForwardWindowResult] = field(default_factory=list)
    
    # Aggregate metrics
    total_oos_return_pct: float = 0.0
    total_oos_net_profit: float = 0.0
    avg_oos_return_pct: float = 0.0
    total_windows: int = 0
    successful_windows: int = 0
    
    # Timing
    total_execution_time: float = 0.0
    
    def calculate_aggregates(self):
        """Calculate aggregate metrics from window results."""
        self.total_windows = len(self.window_results)
        self.successful_windows = len([w for w in self.window_results if w.out_sample_metrics is not None])
        
        if not self.window_results:
            return
        
        # Calculate total OOS metrics
        total_oos_profit = 0.0
        oos_returns = []  # List to compound returns
        valid_windows = 0
        
        for window in self.window_results:
            if window.out_sample_metrics:
                total_oos_profit += window.out_sample_metrics.net_profit
                # Collect returns for compounding (convert percentage to decimal)
                oos_returns.append(window.out_sample_metrics.total_return_pct / 100.0)
                valid_windows += 1
        
        self.total_oos_net_profit = total_oos_profit
        self.avg_oos_return_pct = sum(oos_returns) * 100.0 / valid_windows if valid_windows > 0 else 0.0
        
        # Total OOS return: compound sequential returns
        # Formula: total = (prod(1 + r_i) - 1) * 100
        if oos_returns:
            # Calculate compound return: multiply (1 + return) for each window, then subtract 1
            compound_factor = 1.0
            for r in oos_returns:
                compound_factor *= (1 + r)
            self.total_oos_return_pct = (compound_factor - 1) * 100.0
        else:
            self.total_oos_return_pct = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert results to dictionary for serialization."""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'period_str': self.period_str,
            'fitness_function': self.fitness_function,
            'total_windows': self.total_windows,
            'successful_windows': self.successful_windows,
            'total_oos_return_pct': self.total_oos_return_pct,
            'total_oos_net_profit': self.total_oos_net_profit,
            'avg_oos_return_pct': self.avg_oos_return_pct,
            'total_execution_time': self.total_execution_time,
            'window_results': [
                {
                    'window_index': w.window_index,
                    'best_parameters': w.best_parameters,
                    'in_sample_return_pct': w.in_sample_metrics.total_return_pct if w.in_sample_metrics else None,
                    'out_sample_return_pct': w.out_sample_metrics.total_return_pct if w.out_sample_metrics else None,
                    'in_sample_net_profit': w.in_sample_metrics.net_profit if w.in_sample_metrics else None,
                    'out_sample_net_profit': w.out_sample_metrics.net_profit if w.out_sample_metrics else None,
                }
                for w in self.window_results
            ]
        }


