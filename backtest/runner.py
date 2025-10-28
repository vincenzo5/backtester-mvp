"""
Backtest runner module for orchestrating multi-combination backtests.

This module handles the execution of backtests across multiple symbols and timeframes,
tracking performance and aggregating results.
"""

import time
from itertools import product
from datetime import datetime
from typing import Type
from tqdm import tqdm

from config.manager import ConfigManager
from data.fetch_data import fetch_historical_data
from backtest.engine import run_backtest
from backtest.result import BacktestResult, RunResults, SkippedRun
from cli.output import ConsoleOutput


class BacktestRunner:
    """
    Orchestrates execution of multiple backtests across symbol/timeframe combinations.
    """
    
    def __init__(self, config: ConfigManager, output: ConsoleOutput):
        """
        Initialize the backtest runner.
        
        Args:
            config: ConfigManager instance
            output: ConsoleOutput instance for user feedback
        """
        self.config = config
        self.output = output
        self.total_start_time = None
        self.run_results = RunResults()
    
    def _get_combinations(self):
        """
        Get all symbol/timeframe combinations to test.
        
        Returns:
            list: List of (symbol, timeframe) tuples
        """
        symbols = self.config.get_symbols()
        timeframes = self.config.get_timeframes()
        return list(product(symbols, timeframes))
    
    def run_multi_backtest(self, strategy_class: Type) -> RunResults:
        """
        Run backtests for all symbol/timeframe combinations.
        
        Args:
            strategy_class: Strategy class to use for backtesting
        
        Returns:
            RunResults: Aggregated results from all backtest runs
        """
        self.total_start_time = time.time()
        
        # Get combinations
        symbols = self.config.get_symbols()
        timeframes = self.config.get_timeframes()
        combinations = self._get_combinations()
        
        self.run_results.total_combinations = len(combinations)
        
        # Print combinations info
        self.output.print_combinations_info(
            len(symbols),
            len(timeframes),
            self.run_results.total_combinations
        )
        
        # Print running message
        self.output.print_running_backtests()
        
        # Determine if we should use progress bar
        use_progress_bar = len(combinations) > 1
        iterator = tqdm(combinations, desc="Progress") if use_progress_bar else combinations
        
        # Get verbose setting
        verbose_setting = self.config.get_verbose()
        
        # Run each combination
        for symbol, timeframe in iterator:
            self._run_single_backtest(
                symbol,
                timeframe,
                strategy_class,
                verbose_setting,
                len(combinations),
                use_progress_bar
            )
        
        # Calculate final metrics
        self._finalize_metrics()
        
        return self.run_results
    
    def _run_single_backtest(
        self,
        symbol: str,
        timeframe: str,
        strategy_class: Type,
        verbose_setting: bool,
        total_combinations: int,
        use_progress_bar: bool
    ):
        """
        Run a single backtest for a symbol/timeframe combination.
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe string
            strategy_class: Strategy class to use
            verbose_setting: Verbose mode setting from config
            total_combinations: Total number of combinations (for verbose logic)
            use_progress_bar: Whether progress bar is being used
        """
        timestamp = datetime.now().isoformat()
        
        # Load data
        load_start = time.time()
        df = fetch_historical_data(self.config, symbol=symbol, timeframe=timeframe)
        load_time = time.time() - load_start
        self.run_results.data_load_time += load_time
        
        # Check if data exists
        if df.empty:
            skipped = SkippedRun(
                symbol=symbol,
                timeframe=timeframe,
                reason='no cached data',
                timestamp=timestamp
            )
            self.run_results.skipped.append(skipped)
            self.run_results.skipped_runs += 1
            self.output.skip_message(symbol, timeframe, 'no cached data', use_progress_bar)
            return
        
        # Run backtest
        try:
            backtest_start = time.time()
            # Use verbose mode from config or single combination
            verbose_mode = verbose_setting or (total_combinations == 1)
            result_dict = run_backtest(
                self.config,
                df,
                strategy_class,
                verbose=verbose_mode
            )
            backtest_time = time.time() - backtest_start
            self.run_results.backtest_compute_time += backtest_time
            
            # Convert to BacktestResult
            result = BacktestResult(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=timestamp,
                initial_capital=result_dict['initial_capital'],
                final_value=result_dict['final_value'],
                total_return_pct=result_dict['total_return_pct'],
                num_trades=result_dict['num_trades'],
                execution_time=result_dict['execution_time'],
                start_date=result_dict.get('start_date'),
                end_date=result_dict.get('end_date'),
                duration_days=result_dict.get('duration_days')
            )
            
            self.run_results.results.append(result)
            self.run_results.successful_runs += 1
            
        except Exception as e:
            skipped = SkippedRun(
                symbol=symbol,
                timeframe=timeframe,
                reason=f'error: {str(e)}',
                timestamp=timestamp
            )
            self.run_results.skipped.append(skipped)
            self.run_results.failed_runs += 1
            self.output.error_message(symbol, timeframe, e, use_progress_bar)
    
    def _finalize_metrics(self):
        """Calculate final performance metrics."""
        total_execution_time = time.time() - self.total_start_time
        avg_time_per_run = (
            self.run_results.backtest_compute_time / self.run_results.successful_runs
            if self.run_results.successful_runs > 0
            else 0
        )
        
        self.run_results.total_execution_time = total_execution_time
        self.run_results.avg_time_per_run = avg_time_per_run

