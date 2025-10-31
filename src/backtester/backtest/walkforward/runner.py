"""
Walk-forward runner for orchestrating full walk-forward analysis.
"""

import pandas as pd
from typing import Type, List
from datetime import datetime
import time

from backtester.config import ConfigManager
from backtester.backtest.walkforward.window_generator import generate_windows_from_period
from backtester.backtest.walkforward.optimizer import WindowOptimizer
from backtester.backtest.walkforward.results import WalkForwardResults, WalkForwardWindowResult
from backtester.backtest.engine import run_backtest
from backtester.backtest.walkforward.metrics_calculator import calculate_metrics, BacktestMetrics
from backtester.backtest.walkforward.param_grid import generate_parameter_combinations
from backtester.backtest.execution.hardware import HardwareProfile


class WalkForwardRunner:
    """
    Orchestrates walk-forward optimization analysis across multiple windows.
    """
    
    def __init__(self, config: ConfigManager, output=None):
        """
        Initialize walk-forward runner.
        
        Args:
            config: ConfigManager instance
            output: Optional ConsoleOutput instance for progress
        """
        self.config = config
        self.output = output
    
    def run_walkforward_analysis(
        self,
        strategy_class: Type,
        symbol: str,
        timeframe: str,
        data_df: pd.DataFrame
    ) -> List[WalkForwardResults]:
        """
        Run full walk-forward analysis for a symbol/timeframe combination.
        Supports multiple periods and multiple fitness functions.
        
        Args:
            strategy_class: Strategy class to test
            symbol: Trading pair symbol
            timeframe: Timeframe string
            data_df: DataFrame with OHLCV data
        
        Returns:
            List of WalkForwardResults objects, one per period/fitness combination
        """
        if data_df.empty:
            raise ValueError(f"No data available for {symbol} {timeframe}")
        
        # Get walk-forward configuration
        periods = self.config.get_walkforward_periods()
        fitness_functions = self.config.get_walkforward_fitness_functions()
        parameter_ranges = self.config.get_parameter_ranges()
        
        if not periods:
            raise ValueError("No walk-forward periods configured")
        
        if not fitness_functions:
            raise ValueError("No fitness functions configured")
        
        # Get date range
        start_date = pd.to_datetime(self.config.get_walkforward_start_date())
        end_date = pd.to_datetime(self.config.get_walkforward_end_date())
        
        # Handle timezone mismatch - if data is timezone-aware, make start/end match
        if not data_df.empty and data_df.index.tz is not None:
            # Data has timezone, convert start/end to timezone-aware
            if start_date.tz is None:
                start_date = start_date.tz_localize('UTC')
            if end_date.tz is None:
                end_date = end_date.tz_localize('UTC')
        
        # Filter data to date range
        data_df = data_df.loc[start_date:end_date].copy()
        
        if data_df.empty:
            raise ValueError(f"No data in date range {start_date} to {end_date}")
        
        # CRITICAL: Pre-compute filters ONCE before any loops
        # Get filter names from config
        filter_names = self.config.get_walkforward_filters()
        
        # Compute filters if requested
        if filter_names:
            from backtester.filters.registry import get_filter
            from backtester.debug import get_crash_reporter
            crash_reporter = get_crash_reporter()
            
            for filter_name in filter_names:
                try:
                    filter_class = get_filter(filter_name)
                    if filter_class is None:
                        import warnings
                        warnings.warn(f"Filter '{filter_name}' not found in registry, skipping")
                        continue
                    
                    # Compute filter classification on full dataset
                    filter_instance = filter_class()
                    regime_series = filter_instance.compute_classification(data_df)
                    data_df[filter_name] = regime_series
                except Exception as e:
                    if crash_reporter and crash_reporter.should_capture('filter_error', e, severity='error'):
                        crash_reporter.capture('filter_error', e,
                                              context={'filter_name': filter_name, 
                                                      'symbol': symbol, 
                                                      'timeframe': timeframe},
                                              severity='error')
                    raise  # Re-raise to fail fast
        
        # Generate filter configurations (cartesian product + baseline)
        if filter_names:
            from backtester.filters.generator import generate_filter_configurations
            filter_configurations = generate_filter_configurations(filter_names)
        else:
            # No filters - just baseline
            filter_configurations = [{}]
        
        all_results = []
        
        # OUTER LOOP: Iterate through filter configurations
        for filter_config in filter_configurations:
            # Loop over all periods
            for period_str in periods:
                # Generate walk-forward windows for this period
                windows = generate_windows_from_period(
                    start_date,
                    end_date,
                    period_str,
                    data_df=data_df
                )
                
                if not windows:
                    if self.output:
                        self.output.skip_message(
                            symbol,
                            timeframe,
                            f"Period {period_str}: no valid windows",
                            use_tqdm=False
                        )
                    continue
                
                # Create separate results object for each fitness function
                # Each result includes the filter_config
                results_by_fitness = {
                    fitness_func: WalkForwardResults(
                        symbol=symbol,
                        timeframe=timeframe,
                        period_str=period_str,
                        fitness_function=fitness_func,
                        filter_config=filter_config
                    )
                    for fitness_func in fitness_functions
                }
                
                period_start_time = time.time()
                
                # Process each window
                for i, window in enumerate(windows):
                    if self.output:
                        self.output.print_walkforward_window_progress(i + 1, len(windows), window)
                    
                    try:
                        # Convert window dates to pandas Timestamp, handling timezone
                        window_start_ts = pd.to_datetime(window.in_sample_start)
                        window_end_ts = pd.to_datetime(window.in_sample_end)
                        
                        # If data is timezone-aware, ensure window dates match
                        if not data_df.empty and data_df.index.tz is not None:
                            if window_start_ts.tz is None:
                                window_start_ts = window_start_ts.tz_localize('UTC')
                            if window_end_ts.tz is None:
                                window_end_ts = window_end_ts.tz_localize('UTC')
                        
                        # Step 1: Optimize on in-sample data (once for all fitness functions)
                        # Pass filter_config to optimizer
                        optimizer = WindowOptimizer(
                            config=self.config,
                            strategy_class=strategy_class,
                            data_df=data_df,
                            window_start=window_start_ts,
                            window_end=window_end_ts,
                            parameter_ranges=parameter_ranges,
                            fitness_functions=fitness_functions,
                            filter_config=filter_config,
                            verbose=self.config.get_walkforward_verbose()
                        )
                        
                        # Get optimal worker count for optimization
                        num_param_combos = len(generate_parameter_combinations(parameter_ranges))
                        hardware = HardwareProfile.get_or_create()
                        opt_workers = min(
                            hardware.calculate_optimal_workers(num_param_combos),
                            4  # Limit optimization workers to avoid overhead
                        )
                        
                        # Optimize once, get best params for each fitness function
                        best_by_fitness = optimizer.optimize(max_workers=opt_workers)
                        
                        # Step 2: Test each fitness function's best params on OOS data
                        for fitness_func, (best_params, best_is_metrics, opt_time) in best_by_fitness.items():
                            # Prepare out-of-sample data with warm-up based on BEST parameters
                            oos_start = pd.to_datetime(window.out_sample_start)
                            oos_end = pd.to_datetime(window.out_sample_end)
                        
                        # If data is timezone-aware, ensure window dates match
                        if not data_df.empty and data_df.index.tz is not None:
                            if oos_start.tz is None:
                                oos_start = oos_start.tz_localize('UTC')
                            if oos_end.tz is None:
                                oos_end = oos_end.tz_localize('UTC')
                        
                        # Include warm-up data for indicators based on BEST parameters
                        max_period = max(best_params.values()) if best_params and all(isinstance(v, (int, float)) for v in best_params.values()) else 50
                        
                        # Calculate time difference to determine data frequency
                        if len(data_df) > 1:
                            time_diff = (data_df.index[1] - data_df.index[0]).total_seconds() / 3600  # hours
                            # Add extra buffer (20%) for indicator stability
                            warmup_hours = int(max_period * time_diff * 1.2)
                            warmup_start = oos_start - pd.Timedelta(hours=warmup_hours)
                            # Ensure warmup_start matches timezone of DataFrame index
                            if not data_df.empty and data_df.index.tz is not None:
                                if warmup_start.tz is None:
                                    warmup_start = warmup_start.tz_localize('UTC')
                                elif warmup_start.tz != data_df.index.tz:
                                    warmup_start = warmup_start.tz_convert(data_df.index.tz)
                        else:
                            warmup_start = oos_start
                        
                        # Get OOS data with warm-up period for indicator initialization
                        out_sample_df = data_df.loc[warmup_start:oos_end].copy()
                        
                        if out_sample_df.empty:
                            if self.output:
                                self.output.skip_message(
                                    symbol,
                                    timeframe,
                                    f"Window {i+1} ({fitness_func}): no OOS data with warm-up",
                                    use_tqdm=False
                                )
                            continue
                        
                        # Step 3: Test on out-of-sample data with best parameters
                        # Get original parameters from strategy config
                        original_strategy_config = self.config.get_strategy_config()
                        original_params = original_strategy_config.parameters.copy() if original_strategy_config.parameters else {}
                        
                        # Temporarily update strategy parameters in config
                        self.config._update_strategy_parameters(best_params)
                        
                        try:
                            # Set walk-forward context for tracer
                            from backtester.debug import get_tracer
                            tracer = get_tracer()
                            if tracer:
                                tracer.set_context(
                                    symbol=symbol,
                                    timeframe=timeframe,
                                    period=period_str,
                                    fitness_function=fitness_func,
                                    filter_config=filter_config,
                                    window_index=window.window_index,
                                    window_type='oos'
                                )
                                tracer.trace('window_oos_start', 
                                            f"OOS backtest for window {window.window_index}, {fitness_func}",
                                            window_start=str(oos_start),
                                            window_end=str(oos_end))
                            
                            oos_start_time = time.time()
                            oos_result, oos_cerebro, oos_strategy_instance, oos_metrics = run_backtest(
                                self.config,
                                out_sample_df,
                                strategy_class,
                                verbose=False,
                                strategy_params=best_params,  # Pass best params directly
                                return_metrics=True  # Return cerebro, strategy, and metrics
                            )
                            oos_time = time.time() - oos_start_time
                            
                            # Apply filters to OOS trades if filter_config is provided
                            if filter_config:
                                from backtester.filters.applicator import apply_filters_to_trades, recalculate_metrics_with_filtered_trades
                                
                                # Extract trades from strategy instance
                                oos_trades = getattr(oos_strategy_instance, 'trades_log', [])
                                
                                # Filter trades
                                filtered_oos_trades = apply_filters_to_trades(
                                    oos_trades,
                                    out_sample_df,
                                    filter_config
                                )
                                
                                # Recalculate metrics with filtered trades
                                start_date_py = oos_start.to_pydatetime()
                                end_date_py = oos_end.to_pydatetime()
                                initial_capital = self.config.get_walkforward_initial_capital()
                                
                                try:
                                    oos_metrics = recalculate_metrics_with_filtered_trades(
                                        oos_cerebro,
                                        oos_strategy_instance,
                                        initial_capital,
                                        filtered_oos_trades,
                                        equity_curve=None,
                                        start_date=start_date_py,
                                        end_date=end_date_py
                                    )
                                except Exception as e:
                                    from backtester.debug import get_crash_reporter
                                    crash_reporter = get_crash_reporter()
                                    
                                    if crash_reporter and crash_reporter.should_capture('exception', e, severity='error'):
                                        crash_reporter.capture('exception', e,
                                                              context={'step': 'metrics_recalculation',
                                                                      'filter_config': filter_config,
                                                                      'window_index': window.window_index,
                                                                      'filtered_trades_count': len(filtered_oos_trades)},
                                                              severity='error')
                                    raise
                            
                            # Calculate walk-forward efficiency (OOS / IS return ratio)
                            from backtester.backtest.walkforward.metrics_calculator import update_walkforward_efficiency
                            if best_is_metrics.total_return_pct != 0:
                                efficiency = oos_metrics.total_return_pct / best_is_metrics.total_return_pct
                            else:
                                # If IS return is 0 or negative, efficiency is 0
                                efficiency = 0.0
                            
                            # Update OOS metrics with calculated efficiency
                            oos_metrics = update_walkforward_efficiency(oos_metrics, efficiency)
                        finally:
                            # Restore original parameters
                            self.config._update_strategy_parameters(original_params)
                        
                        # Store window result for this fitness function
                        window_result = WalkForwardWindowResult(
                            window_index=window.window_index,
                            in_sample_start=window.in_sample_start.strftime('%Y-%m-%d'),
                            in_sample_end=window.in_sample_end.strftime('%Y-%m-%d'),
                            out_sample_start=window.out_sample_start.strftime('%Y-%m-%d'),
                            out_sample_end=window.out_sample_end.strftime('%Y-%m-%d'),
                            best_parameters=best_params,
                            in_sample_metrics=best_is_metrics,
                            out_sample_metrics=oos_metrics,
                            optimization_time=opt_time,
                            oos_backtest_time=oos_time
                        )
                        
                        results_by_fitness[fitness_func].window_results.append(window_result)
                    
                    except Exception as e:
                        # Get debug components
                        from backtester.debug import get_crash_reporter
                        crash_reporter = get_crash_reporter()
                        
                        if crash_reporter and crash_reporter.should_capture('exception', e, severity='error'):
                            context = {
                                'symbol': symbol,
                                'timeframe': timeframe,
                                'period': period_str,
                                'fitness_function': fitness_func,
                                'filter_config': filter_config,
                                'window_index': window.window_index,
                                'window_start': str(window.in_sample_start),
                                'window_end': str(window.in_sample_end)
                            }
                            crash_reporter.capture('exception', e, context, severity='error')
                        
                        if self.output:
                            self.output.error_message(
                                symbol,
                                timeframe,
                                f"Window {i+1} error: {e}",
                                use_tqdm=False
                            )
                        continue
                
                # Calculate aggregate metrics for each fitness function's results
                for fitness_func, result_obj in results_by_fitness.items():
                    result_obj.total_execution_time = time.time() - period_start_time
                    result_obj.calculate_aggregates()
                    all_results.append(result_obj)
        
        return all_results

