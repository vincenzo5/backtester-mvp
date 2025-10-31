"""
Backtest runner module for orchestrating multi-combination backtests.

This module handles the execution of backtests across multiple symbols and timeframes,
tracking performance and aggregating results.
"""

from itertools import product
from typing import Type, List
import pandas as pd
import time

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
            workflow_start_time = time.time()
            workflow_id = f"{symbol}_{timeframe}".replace('/', '_')
            
            # Set context for symbol/timeframe combination
            if tracer:
                tracer.set_context(symbol=symbol, timeframe=timeframe)
                tracer.trace('workflow_start',
                            f"Starting workflow for {symbol} {timeframe}",
                            symbol=symbol,
                            timeframe=timeframe,
                            workflow_id=workflow_id)
            
            try:
                # Load data
                data_load_start = time.time()
                df = read_cache(symbol, timeframe)
                data_load_time = time.time() - data_load_start
                
                if df.empty:
                    self.output.skip_message(
                        symbol,
                        timeframe,
                        "no cached data",
                        use_tqdm=False
                    )
                    if tracer:
                        tracer.trace('workflow_end',
                                    f"Workflow skipped: no cached data",
                                    symbol=symbol,
                                    timeframe=timeframe,
                                    workflow_id=workflow_id,
                                    performance={
                                        'total_time_seconds': time.time() - workflow_start_time,
                                        'data_load_time': data_load_time,
                                        'status': 'skipped'
                                    })
                    continue
                
                # Calculate data characteristics
                num_candles_total = len(df)
                date_range = {
                    'start': str(df.index[0]) if not df.empty else None,
                    'end': str(df.index[-1]) if not df.empty else None
                } if not df.empty else None
                data_size_mb = df.memory_usage(deep=True).sum() / (1024**2) if not df.empty else 0.0
                
                # Run walk-forward analysis (returns list of results per period/fitness combination)
                wf_results = walkforward_runner.run_walkforward_analysis(
                    strategy_class,
                    symbol,
                    timeframe,
                    df
                )
                
                workflow_time = time.time() - workflow_start_time
                
                # Calculate total windows across all results
                total_windows = sum(r.total_windows for r in wf_results) if wf_results else 0
                successful_windows = sum(r.successful_windows for r in wf_results) if wf_results else 0
                
                # Get filter computation time if available (from walkforward runner context)
                # Filters are computed in WalkForwardRunner, we'll track it there
                filter_computation_time = 0.0  # Will be tracked in walkforward runner
                
                all_results.extend(wf_results)
                
                # Print summary for each result
                for wf_result in wf_results:
                    self.output.print_walkforward_summary(wf_result)
                
                # Emit workflow_end event
                if tracer:
                    tracer.trace('workflow_end',
                                f"Workflow complete for {symbol} {timeframe}",
                                symbol=symbol,
                                timeframe=timeframe,
                                workflow_id=workflow_id,
                                performance={
                                    'total_time_seconds': workflow_time,
                                    'data_load_time': data_load_time,
                                    'filter_computation_time': filter_computation_time,
                                    'total_windows': total_windows,
                                    'successful_windows': successful_windows
                                },
                                data={
                                    'num_candles_total': num_candles_total,
                                    'date_range': date_range,
                                    'data_size_mb': data_size_mb
                                })
                
            except Exception as e:
                # Capture exception with context
                if crash_reporter and crash_reporter.should_capture('exception', e, severity='error'):
                    crash_reporter.capture('exception', e, 
                                          context={'symbol': symbol, 'timeframe': timeframe},
                                          severity='error')
                
                workflow_time = time.time() - workflow_start_time
                
                if tracer:
                    tracer.trace('workflow_end',
                                f"Workflow failed for {symbol} {timeframe}",
                                symbol=symbol,
                                timeframe=timeframe,
                                workflow_id=workflow_id,
                                performance={
                                    'total_time_seconds': workflow_time,
                                    'status': 'failed'
                                },
                                error=str(e))
                
                self.output.error_message(
                    symbol,
                    timeframe,
                    e,
                    use_tqdm=False
                )
                continue
        
        return all_results
    

