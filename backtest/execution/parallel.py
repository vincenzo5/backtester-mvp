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

from backtest.result import BacktestResult, RunResults, SkippedRun


# Top-level worker function (required for multiprocessing pickle)
def _run_backtest_worker(work_item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute single backtest in worker process.
    
    This function runs in a separate process and must be picklable.
    All objects are reconstructed from serialized data.
    
    Args:
        work_item: Dict containing:
            - symbol: Trading pair symbol
            - timeframe: Timeframe string
            - config_dict: Serialized ConfigManager data
            - strategy_name: Strategy class name
    
    Returns:
        Dict with result data (status, symbol, timeframe, and result fields)
    """
    try:
        # Reconstruct config from dict
        from config.manager import ConfigManager
        config = ConfigManager._from_dict(work_item['config_dict'])
        
        # Import strategy dynamically
        from strategies import get_strategy_class
        strategy_class = get_strategy_class(work_item['strategy_name'])
        
        # Load data from cache
        from data.fetch_data import fetch_historical_data
        df = fetch_historical_data(config, work_item['symbol'], work_item['timeframe'])
        
        if df.empty:
            return {
                'status': 'skipped',
                'symbol': work_item['symbol'],
                'timeframe': work_item['timeframe'],
                'reason': 'no cached data'
            }
        
        # Run backtest
        from backtest.engine import run_backtest
        result_dict = run_backtest(config, df, strategy_class, verbose=False)
        
        # Return serializable result
        return {
            'status': 'success',
            'symbol': work_item['symbol'],
            'timeframe': work_item['timeframe'],
            'timestamp': datetime.now().isoformat(),
            **result_dict
        }
        
    except Exception as e:
        # Isolate error - don't crash other workers
        return {
            'status': 'error',
            'symbol': work_item['symbol'],
            'timeframe': work_item['timeframe'],
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


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
        run_results = RunResults()
        run_results.total_combinations = len(combinations)
        run_results.worker_count = self.num_workers
        total_start = time.time()
        
        # Prepare work items (must be serializable)
        config_dict = self.config._to_dict()
        strategy_name = self.config.get_strategy_name()
        
        work_items = [
            {
                'symbol': symbol,
                'timeframe': timeframe,
                'config_dict': config_dict,
                'strategy_name': strategy_name
            }
            for symbol, timeframe in combinations
        ]
        
        # Execute with progress bar
        if self.num_workers > 1:
            print(f"Running backtests with {self.num_workers} workers...")
        else:
            print("Running backtests...")
        
        # Track backtest computation time (wall-clock time, not sum of worker times)
        backtest_start = time.time()
        
        with ProcessPoolExecutor(max_workers=self.num_workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(_run_backtest_worker, item): item 
                for item in work_items
            }
            
            # Process results as they complete (with progress bar)
            for future in tqdm(as_completed(futures), total=len(futures), desc="Progress"):
                result = future.result()
                self._process_result(result, run_results)
        
        backtest_end = time.time()
        
        # Track timing
        run_results.total_execution_time = time.time() - total_start
        # Use actual wall-clock time for parallel execution (not sum of worker times)
        run_results.backtest_compute_time = backtest_end - backtest_start
        # Note: data_load_time is not tracked separately in parallel execution
        # as each worker loads its own data concurrently
        run_results.avg_time_per_run = (
            run_results.backtest_compute_time / run_results.successful_runs
            if run_results.successful_runs > 0 else 0
        )
        
        return run_results
    
    def _process_result(self, result: Dict[str, Any], run_results: RunResults):
        """
        Process worker result and update run_results.
        
        Args:
            result: Result dict from worker
            run_results: RunResults to update
        """
        if result['status'] == 'success':
            # Extract backtest-specific fields
            backtest_fields = {
                k: v for k, v in result.items() 
                if k not in ['status', 'symbol', 'timeframe', 'timestamp']
            }
            
            backtest_result = BacktestResult(
                symbol=result['symbol'],
                timeframe=result['timeframe'],
                timestamp=result.get('timestamp', datetime.now().isoformat()),
                **backtest_fields
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
