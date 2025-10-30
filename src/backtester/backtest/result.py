"""
Result data classes for backtest runs.

This module provides type-safe containers for backtest results and aggregated outcomes.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from backtester.backtest.walkforward.metrics_calculator import BacktestMetrics


@dataclass
class BacktestResult:
    """Result from a single backtest run."""
    
    symbol: str
    timeframe: str
    timestamp: str
    metrics: Any  # BacktestMetrics - using Any to avoid circular import
    initial_capital: float  # Starting capital (input parameter, not a metric)
    execution_time: float
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary format."""
        result = {
            'timestamp': self.timestamp,
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'initial_capital': self.initial_capital,
            'execution_time': self.execution_time,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'metrics': asdict(self.metrics)
        }
        return result


@dataclass
class SkippedRun:
    """Information about a skipped backtest combination."""
    
    symbol: str
    timeframe: str
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert skipped run to dictionary format."""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'reason': self.reason,
            'timestamp': self.timestamp
        }


@dataclass
class RunResults:
    """Aggregated results from multiple backtest runs."""
    
    results: List[BacktestResult] = field(default_factory=list)
    skipped: List[SkippedRun] = field(default_factory=list)
    total_combinations: int = 0
    successful_runs: int = 0
    skipped_runs: int = 0
    failed_runs: int = 0
    total_execution_time: float = 0.0
    avg_time_per_run: float = 0.0
    data_load_time: float = 0.0
    backtest_compute_time: float = 0.0
    report_generation_time: float = 0.0
    worker_count: int = 1  # Number of parallel workers used
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics dictionary."""
        return {
            'total_combinations': self.total_combinations,
            'successful_runs': self.successful_runs,
            'skipped_runs': self.skipped_runs,
            'failed_runs': self.failed_runs,
            'total_execution_time': self.total_execution_time,
            'avg_time_per_run': self.avg_time_per_run,
            'data_load_time': self.data_load_time,
            'backtest_compute_time': self.backtest_compute_time,
            'report_generation_time': self.report_generation_time,
            'worker_count': self.worker_count
        }
    
    def get_sorted_results(self, reverse: bool = True) -> List[BacktestResult]:
        """Get results sorted by return percentage."""
        return sorted(
            self.results,
            key=lambda x: x.metrics.total_return_pct if isinstance(x.metrics.total_return_pct, (int, float)) else -999,
            reverse=reverse
        )
    
    def get_results_as_dicts(self) -> List[Dict[str, Any]]:
        """Get all results as dictionaries for CSV export."""
        return [result.to_dict() for result in self.results]
    
    def get_skipped_as_dicts(self) -> List[Dict[str, Any]]:
        """Get all skipped runs as dictionaries for CSV export."""
        return [skip.to_dict() for skip in self.skipped]

