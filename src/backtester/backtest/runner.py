"""
Backtest runner module for orchestrating multi-combination backtests.

This module handles the execution of backtests across multiple symbols and timeframes,
tracking performance and aggregating results.
"""

from itertools import product
from typing import Type, List
import pandas as pd

from backtester.config import ConfigManager
from backtester.backtest.result import RunResults
from backtester.backtest.execution.hardware import HardwareProfile
from backtester.backtest.execution.parallel import ParallelExecutor
from backtester.cli.output import ConsoleOutput
from backtester.backtest.walkforward.runner import WalkForwardRunner
from backtester.backtest.walkforward.results import WalkForwardResults


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
        Run backtests for all symbol/timeframe combinations using parallel execution.
        
        Args:
            strategy_class: Strategy class to use for backtesting
        
        Returns:
            RunResults: Aggregated results from all backtest runs
        """
        # Get dynamic combinations from config
        symbols = self.config.get_symbols()
        timeframes = self.config.get_timeframes()
        combinations = self._get_combinations()
        num_combinations = len(combinations)
        
        # Print combinations info
        self.output.print_combinations_info(
            len(symbols),
            len(timeframes),
            num_combinations
        )
        
        # Get or create hardware profile (cached after first run)
        hardware = HardwareProfile.get_or_create()
        
        # Calculate optimal workers
        parallel_mode = self.config.get_parallel_mode()
        manual_workers = self.config.get_manual_workers()
        memory_safety_factor = self.config.get_memory_safety_factor()
        cpu_reserve_cores = self.config.get_cpu_reserve_cores()
        
        num_workers = hardware.calculate_optimal_workers(
            num_combinations,
            mode=parallel_mode,
            manual_workers=manual_workers,
            memory_safety_factor=memory_safety_factor,
            cpu_reserve_cores=cpu_reserve_cores
        )
        
        # Execute using parallel executor
        executor = ParallelExecutor(num_workers, self.config, self.output)
        run_results = executor.execute(combinations, strategy_class)
        
        return run_results
    
    def run_walkforward_analysis(self, strategy_class: Type) -> List[WalkForwardResults]:
        """
        Run walk-forward optimization for all symbol/timeframe combinations.
        
        Args:
            strategy_class: Strategy class to use for backtesting
        
        Returns:
            List of WalkForwardResults objects, one per symbol/timeframe combination
        """
        from backtester.data.cache_manager import read_cache
        
        symbols = self.config.get_symbols()
        timeframes = self.config.get_timeframes()
        combinations = self._get_combinations()
        
        # Print combinations info
        self.output.print_combinations_info(
            len(symbols),
            len(timeframes),
            len(combinations)
        )
        
        print("\nRunning walk-forward optimization...\n")
        
        walkforward_runner = WalkForwardRunner(self.config, self.output)
        all_results = []
        
        for symbol, timeframe in combinations:
            try:
                # Load data
                df = read_cache(symbol, timeframe)
                
                if df.empty:
                    self.output.skip_message(
                        symbol,
                        timeframe,
                        "no cached data",
                        use_tqdm=False
                    )
                    continue
                
                # Run walk-forward analysis (returns list of results per period/fitness combination)
                wf_results = walkforward_runner.run_walkforward_analysis(
                    strategy_class,
                    symbol,
                    timeframe,
                    df
                )
                
                all_results.extend(wf_results)
                
                # Print summary for each result
                for wf_result in wf_results:
                    self.output.print_walkforward_summary(wf_result)
                
            except Exception as e:
                self.output.error_message(
                    symbol,
                    timeframe,
                    e,
                    use_tqdm=False
                )
                continue
        
        return all_results
    

