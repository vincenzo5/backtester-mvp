"""
Walk-forward optimizer for single window optimization.

Optimizes parameters on in-sample data and selects best set based on fitness function.
"""

import backtrader as bt
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from backtester.config import ConfigManager
from backtester.backtest.engine import run_backtest, prepare_backtest_data
from backtester.backtest.walkforward.param_grid import generate_parameter_combinations
from backtester.backtest.walkforward.metrics_calculator import calculate_metrics, calculate_fitness, BacktestMetrics


class WindowOptimizer:
    """
    Optimizes strategy parameters for a single walk-forward window.
    """
    
    def __init__(
        self,
        config: ConfigManager,
        strategy_class,
        data_df: pd.DataFrame,
        window_start: pd.Timestamp,
        window_end: pd.Timestamp,
        parameter_ranges: Dict[str, Dict[str, int]],
        fitness_functions: List[str],
        filter_config: Dict[str, str] = None,
        verbose: bool = False
    ):
        """
        Initialize optimizer for a single window.
        
        Args:
            config: ConfigManager instance
            strategy_class: Strategy class to optimize
            data_df: Full DataFrame with all data (should include filter columns if filters are used)
            window_start: Start datetime of in-sample window
            window_end: End datetime of in-sample window
            parameter_ranges: Parameter ranges for grid search
            fitness_functions: List of fitness function names to evaluate
            filter_config: Optional filter configuration dict (e.g., {'volatility_regime_atr': 'high'})
                         If None or empty, no filtering is applied
            verbose: Enable verbose output
        """
        self.config = config
        self.strategy_class = strategy_class
        self.data_df = data_df
        self.parameter_ranges = parameter_ranges
        self.fitness_functions = fitness_functions
        self.filter_config = filter_config or {}
        self.verbose = verbose
        
        # Normalize timezones before slicing to avoid comparison errors
        # Ensure window dates match DataFrame index timezone
        if not data_df.empty and data_df.index.tz is not None:
            # DataFrame is timezone-aware, ensure window dates match
            if isinstance(window_start, pd.Timestamp):
                if window_start.tz is None:
                    window_start = window_start.tz_localize('UTC')
                elif window_start.tz != data_df.index.tz:
                    window_start = window_start.tz_convert(data_df.index.tz)
            else:
                window_start = pd.to_datetime(window_start).tz_localize('UTC')
            if isinstance(window_end, pd.Timestamp):
                if window_end.tz is None:
                    window_end = window_end.tz_localize('UTC')
                elif window_end.tz != data_df.index.tz:
                    window_end = window_end.tz_convert(data_df.index.tz)
            else:
                window_end = pd.to_datetime(window_end).tz_localize('UTC')
        else:
            # DataFrame is timezone-naive, ensure window dates are naive too
            if isinstance(window_start, pd.Timestamp) and window_start.tz is not None:
                window_start = window_start.tz_localize(None)
            elif not isinstance(window_start, pd.Timestamp):
                window_start = pd.to_datetime(window_start)
            if isinstance(window_end, pd.Timestamp) and window_end.tz is not None:
                window_end = window_end.tz_localize(None)
            elif not isinstance(window_end, pd.Timestamp):
                window_end = pd.to_datetime(window_end)
        
        # Store normalized dates
        self.window_start = window_start
        self.window_end = window_end
        
        # Extract in-sample data segment (preserves filter columns)
        self.in_sample_df = data_df.loc[window_start:window_end].copy()
        
        if self.in_sample_df.empty:
            raise ValueError(f"In-sample window {window_start} to {window_end} has no data")
    
    def optimize(self, max_workers: int = 1) -> Dict[str, Tuple[Dict[str, int], BacktestMetrics, float]]:
        """
        Run optimization on in-sample window for all fitness functions.
        
        Optimizes parameter combinations once, then evaluates each fitness function
        on the same results to find best params for each fitness function.
        
        Args:
            max_workers: Number of parallel workers for optimization
        
        Returns:
            Dictionary mapping fitness function name to (best_parameters, best_metrics, optimization_time)
            Example: {"np_avg_dd": (params_dict, metrics, time), "net_profit": (params_dict, metrics, time)}
        """
        from backtester.debug import get_tracer
        tracer = get_tracer()
        
        start_time = time.time()
        
        # Generate all parameter combinations
        param_combinations = generate_parameter_combinations(self.parameter_ranges)
        
        if tracer:
            tracer.trace('optimization_start',
                        f"Optimizing {len(param_combinations)} parameter combinations",
                        param_combinations_count=len(param_combinations),
                        max_workers=max_workers,
                        window_start=str(self.window_start),
                        window_end=str(self.window_end))
        
        if self.verbose:
            print(f"  Optimizing {len(param_combinations)} parameter combinations...")
        
        if not param_combinations:
            raise ValueError("No parameter combinations to optimize")
        
        # Run optimization once for all parameter combinations (parallel if max_workers > 1)
        if max_workers > 1 and len(param_combinations) > 1:
            results = self._optimize_parallel(param_combinations, max_workers)
        else:
            results = self._optimize_sequential(param_combinations)
        
        optimization_time = time.time() - start_time
        
        # For each fitness function, find best parameters from the same optimization results
        best_by_fitness = {}
        
        for fitness_function in self.fitness_functions:
            best_params = None
            best_metrics = None
            best_fitness = float('-inf')
            
            for params, metrics in results:
                if metrics is None:
                    continue
                
                fitness = calculate_fitness(metrics, fitness_function)
                
                if fitness > best_fitness:
                    best_fitness = fitness
                    best_params = params
                    best_metrics = metrics
            
            if best_params is None:
                raise ValueError(f"No valid optimization results found for fitness function: {fitness_function}")
            
            if tracer:
                tracer.trace('optimization_best_params',
                            f"Best params for {fitness_function}",
                            fitness_function=fitness_function,
                            best_params=best_params,
                            best_fitness=best_fitness)
            
            if self.verbose:
                print(f"  Best params for {fitness_function}: {best_params}, Fitness: {best_fitness:.2f}")
            
            best_by_fitness[fitness_function] = (best_params, best_metrics, optimization_time)
        
        if tracer:
            tracer.trace('optimization_end',
                        f"Optimization completed in {optimization_time:.2f}s",
                        duration=optimization_time,
                        best_params_by_fitness={k: v[0] for k, v in best_by_fitness.items()})
        
        return best_by_fitness
    
    def _optimize_sequential(self, param_combinations: List[Dict[str, int]]) -> List[Tuple[Dict[str, int], Optional[BacktestMetrics]]]:
        """Run optimization sequentially."""
        results = []
        
        for i, params in enumerate(param_combinations):
            try:
                metrics = self._evaluate_parameters(params)
                results.append((params, metrics))
            except Exception as e:
                if self.verbose:
                    print(f"  Error evaluating params {params}: {e}")
                results.append((params, None))
        
        return results
    
    def _optimize_parallel(self, param_combinations: List[Dict[str, int]], max_workers: int) -> List[Tuple[Dict[str, int], Optional[BacktestMetrics]]]:
        """Run optimization in parallel."""
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_params = {
                executor.submit(self._evaluate_parameters, params): params
                for params in param_combinations
            }
            
            # Collect results
            for future in as_completed(future_to_params):
                params = future_to_params[future]
                try:
                    metrics = future.result()
                    results.append((params, metrics))
                except Exception as e:
                    # Get debug components
                    from backtester.debug import get_crash_reporter
                    crash_reporter = get_crash_reporter()
                    
                    if crash_reporter and crash_reporter.should_capture('exception', e, severity='error'):
                        context = {
                            'params': params,
                            'parallel': True,
                            'window': {
                                'start': str(self.window_start),
                                'end': str(self.window_end)
                            }
                        }
                        crash_reporter.capture('exception', e, context, severity='error')
                    
                    if self.verbose:
                        print(f"  Error evaluating params {params}: {e}")
                    results.append((params, None))
        
        return results
    
    def _evaluate_parameters(self, params: Dict[str, int]) -> Optional[BacktestMetrics]:
        """
        Evaluate a single parameter combination on in-sample data.
        
        Args:
            params: Parameter dictionary
        
        Returns:
            BacktestMetrics or None if evaluation fails
        """
        # Create a temporary config manager with these parameters
        # We'll modify strategy params directly
        try:
            # Run backtest with these parameters
            # Parameters come from optimization ranges, not config
            # We'll pass params directly to the backtest
            
            try:
                # Run backtest on in-sample data with optimized parameters
                from backtester.backtest.engine import run_backtest
                from backtester.backtest.walkforward.metrics_calculator import calculate_metrics
                from backtester.filters.applicator import apply_filters_to_trades, recalculate_metrics_with_filtered_trades
                
                result_dict, cerebro, strategy_instance, metrics = run_backtest(
                    self.config,
                    self.in_sample_df,
                    self.strategy_class,
                    verbose=False,
                    strategy_params=params,  # Pass optimized parameters
                    return_metrics=True  # Return cerebro, strategy, and metrics
                )
                
                # Apply filters if filter_config is provided and not empty
                if self.filter_config:
                    # Extract trades from strategy instance
                    trades = getattr(strategy_instance, 'trades_log', [])
                    if not trades:
                        # Fallback: try to extract from trade analyzer
                        try:
                            trade_analyzer = cerebro.analyzers.trade.get_analysis() if hasattr(cerebro.analyzers, 'trade') else None
                            # Trade analyzer doesn't provide individual trades, so we'll work with empty list
                            trades = []
                        except Exception:
                            trades = []
                    
                    # Filter trades
                    filtered_trades = apply_filters_to_trades(
                        trades,
                        self.in_sample_df,
                        self.filter_config
                    )
                    
                    # Recalculate metrics with filtered trades
                    start_date = pd.to_datetime(self.in_sample_df.index[0]).to_pydatetime() if not self.in_sample_df.empty else None
                    end_date = pd.to_datetime(self.in_sample_df.index[-1]).to_pydatetime() if not self.in_sample_df.empty else None
                    
                    initial_capital = self.config.get_walkforward_initial_capital()
                    filtered_metrics = recalculate_metrics_with_filtered_trades(
                        cerebro,
                        strategy_instance,
                        initial_capital,
                        filtered_trades,
                        equity_curve=None,  # Will extract from strategy_instance
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    return filtered_metrics
                else:
                    # No filtering, return original metrics
                    return metrics
            except Exception as e:
                # Get debug components
                from backtester.debug import get_tracer, get_crash_reporter
                crash_reporter = get_crash_reporter()
                
                if crash_reporter and crash_reporter.should_capture('exception', e, severity='error'):
                    context = {
                        'params': params,
                        'window': {
                            'start': str(self.window_start),
                            'end': str(self.window_end)
                        }
                    }
                    crash_reporter.capture('exception', e, context, severity='error')
                
                if self.verbose:
                    print(f"    Error in backtest for params {params}: {e}")
                return None
                
        except Exception as e:
            # Get debug components
            from backtester.debug import get_tracer, get_crash_reporter
            crash_reporter = get_crash_reporter()
            
            if crash_reporter and crash_reporter.should_capture('exception', e, severity='error'):
                context = {
                    'params': params,
                    'window': {
                        'start': str(self.window_start),
                        'end': str(self.window_end)
                    }
                }
                crash_reporter.capture('exception', e, context, severity='error')
            
            if self.verbose:
                print(f"    Error evaluating parameters {params}: {e}")
            return None


