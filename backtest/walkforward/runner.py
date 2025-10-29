"""
Walk-forward runner for orchestrating full walk-forward analysis.
"""

import pandas as pd
from typing import Type, List
from datetime import datetime
import time

from config import ConfigManager
from backtest.walkforward.window_generator import generate_windows_from_period
from backtest.walkforward.optimizer import WindowOptimizer
from backtest.walkforward.results import WalkForwardResults, WalkForwardWindowResult
from backtest.engine import run_backtest
from backtest.walkforward.metrics_calculator import calculate_metrics, BacktestMetrics
from backtest.walkforward.param_grid import generate_parameter_combinations
from backtest.execution.hardware import HardwareProfile


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
        start_date = pd.to_datetime(self.config.get_start_date())
        end_date = pd.to_datetime(self.config.get_end_date())
        
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
        
        all_results = []
        
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
            results_by_fitness = {
                fitness_func: WalkForwardResults(
                    symbol=symbol,
                    timeframe=timeframe,
                    period_str=period_str,
                    fitness_function=fitness_func
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
                    optimizer = WindowOptimizer(
                        config=self.config,
                        strategy_class=strategy_class,
                        data_df=data_df,
                        window_start=window_start_ts,
                        window_end=window_end_ts,
                        parameter_ranges=parameter_ranges,
                        fitness_functions=fitness_functions,
                        verbose=self.config.get_verbose()
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
                        original_params = self.config.config['strategy']['parameters'].copy()
                        self.config.config['strategy']['parameters'].update(best_params)
                        
                        try:
                            oos_start_time = time.time()
                            oos_result = run_backtest(
                                self.config,
                                out_sample_df,
                                strategy_class,
                                verbose=False
                            )
                            oos_time = time.time() - oos_start_time
                            
                            # Create OOS metrics
                            initial_capital = self.config.get_initial_capital()
                            final_value = oos_result['final_value']
                            
                            oos_metrics = BacktestMetrics(
                                net_profit=final_value - initial_capital,
                                total_return_pct=oos_result['total_return_pct'],
                                sharpe_ratio=0.0,  # Simplified for now
                                max_drawdown=0.0,
                                profit_factor=0.0,
                                np_avg_dd=(final_value - initial_capital) / 1000.0 if final_value > initial_capital else 0.0,
                                gross_profit=max(final_value - initial_capital, 0),
                                gross_loss=abs(min(final_value - initial_capital, 0)),
                                num_trades=oos_result['num_trades'],
                                num_winning_trades=max(oos_result['num_trades'] // 2, 0),
                                num_losing_trades=max(oos_result['num_trades'] // 2, 0),
                                avg_drawdown=1000.0
                            )
                        finally:
                            # Restore original parameters
                            self.config.config['strategy']['parameters'] = original_params
                        
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

