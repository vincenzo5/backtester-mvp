"""
Backtest runner module for orchestrating multi-combination backtests.

This module handles the execution of backtests across multiple symbols and timeframes,
tracking performance and aggregating results.
"""

from itertools import product
from typing import Type, List
import pandas as pd

from backtester.config import ConfigManager
from backtester.backtest.execution.hardware import HardwareProfile
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
    
    def run_walkforward_analysis(self, strategy_class: Type) -> List[WalkForwardResults]:
        """
        Run walk-forward optimization for all symbol/timeframe combinations.
        
        Args:
            strategy_class: Strategy class to use for backtesting
        
        Returns:
            List of WalkForwardResults objects, one per symbol/timeframe combination
        """
        from backtester.data.cache_manager import read_cache
        
        symbols = self.config.get_walkforward_symbols()
        timeframes = self.config.get_walkforward_timeframes()
        combinations = list(product(symbols, timeframes))
        
        # Print combinations info
        self.output.print_combinations_info(
            len(symbols),
            len(timeframes),
            len(combinations)
        )
        
        print("\nRunning walk-forward optimization...\n")
        
        walkforward_runner = WalkForwardRunner(self.config, self.output)
        all_results = []
        
        # Import debug components
        from backtester.debug import get_tracer, get_crash_reporter
        tracer = get_tracer()
        crash_reporter = get_crash_reporter()

        for symbol, timeframe in combinations:
            # Set context for symbol/timeframe combination
            if tracer:
                tracer.set_context(symbol=symbol, timeframe=timeframe)
                tracer.trace('combination_start', 
                            f"Starting walk-forward for {symbol} {timeframe}")
            
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
                # Capture exception with context
                if crash_reporter and crash_reporter.should_capture('exception', e, severity='error'):
                    crash_reporter.capture('exception', e, 
                                          context={'symbol': symbol, 'timeframe': timeframe},
                                          severity='error')
                
                self.output.error_message(
                    symbol,
                    timeframe,
                    e,
                    use_tqdm=False
                )
                continue
        
        return all_results
    

