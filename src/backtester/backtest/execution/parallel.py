"""
Parallel execution module for backtesting.

Provides ProcessPoolExecutor-based parallel execution for multiple
symbol/timeframe combinations.
"""

import time
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Tuple, Dict, Any
from tqdm import tqdm

from backtester.backtest.result import BacktestResult, RunResults, SkippedRun


# NOTE: _run_backtest_worker was removed since it was only used by run_multi_backtest()
# which has been removed. Walk-forward optimization uses ThreadPoolExecutor directly
# in WindowOptimizer for parallel parameter optimization within windows.
# ParallelExecutor class remains but execute() method is now unused.

class ParallelExecutor:
    """Unified parallel executor for all combination counts."""
    
    def __init__(self, num_workers: int, config, output):
        """
        Initialize parallel executor.
        
        Args:
            num_workers: Number of parallel worker processes
            config: ConfigManager instance
            output: ConsoleOutput instance for user feedback
        """
        self.num_workers = num_workers
        self.config = config
        self.output = output
    
    def execute(self, combinations: List[Tuple[str, str]], strategy_class) -> RunResults:
        """
        Execute backtests for all combinations using parallel workers.
        
        Args:
            combinations: List of (symbol, timeframe) tuples
            strategy_class: Strategy class to use (for reference, not passed to workers)
        
        Returns:
            RunResults with aggregated results from all backtests
        """
        # NOTE: This method is unused since run_multi_backtest() was removed.
        # Single backtest mode has been removed - system now only supports walk-forward optimization.
        # Walk-forward uses ThreadPoolExecutor directly in WindowOptimizer for parameter optimization.
        raise NotImplementedError("ParallelExecutor.execute() is no longer used. Single backtest mode has been removed.")
    
    def _process_result(self, result: Dict[str, Any], run_results: RunResults):
        """
        Process worker result and update run_results.
        
        Args:
            result: Result dict from worker
            run_results: RunResults to update
        """
        if result['status'] == 'success':
            # Extract metrics dict and reconstruct BacktestMetrics object
            from backtester.backtest.walkforward.metrics_calculator import BacktestMetrics
            
            metrics_dict = result.get('metrics', {})
            metrics = BacktestMetrics(**metrics_dict)
            
            # Extract metadata fields
            backtest_result = BacktestResult(
                symbol=result['symbol'],
                timeframe=result['timeframe'],
                timestamp=result.get('timestamp', datetime.now().isoformat()),
                metrics=metrics,
                initial_capital=result.get('initial_capital', 0.0),
                execution_time=result.get('execution_time', 0.0),
                start_date=result.get('start_date'),
                end_date=result.get('end_date')
            )
            run_results.results.append(backtest_result)
            run_results.successful_runs += 1
            # Note: execution_time from individual results is kept in BacktestResult
            # but we don't accumulate it here since we use wall-clock time for parallel execution
        
        elif result['status'] == 'skipped':
            skip = SkippedRun(
                symbol=result['symbol'],
                timeframe=result['timeframe'],
                reason=result['reason'],
                timestamp=result.get('timestamp', datetime.now().isoformat())
            )
            run_results.skipped.append(skip)
            run_results.skipped_runs += 1
            self.output.skip_message(
                result['symbol'], 
                result['timeframe'], 
                result['reason'], 
                use_tqdm=True
            )
        
        elif result['status'] == 'error':
            skip = SkippedRun(
                symbol=result['symbol'],
                timeframe=result['timeframe'],
                reason=f"error: {result['error']}",
                timestamp=result.get('timestamp', datetime.now().isoformat())
            )
            run_results.skipped.append(skip)
            run_results.failed_runs += 1
            self.output.error_message(
                result['symbol'], 
                result['timeframe'], 
                Exception(result['error']), 
                use_tqdm=True
            )
