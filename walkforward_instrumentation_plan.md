# Walk-Forward Instrumentation Plan ✅ IMPLEMENTED

## Overview
This plan addresses missing debug instrumentation points specific to walk-forward testing. These additions will ensure comprehensive coverage of the walk-forward execution flow.

**Status:** All instrumentation points have been successfully implemented. See `walkforward_instrumentation_implementation.md` for details.

## Missing Instrumentation Points

### 1. OOS Backtest with Walk-Forward Context (High Priority)
**Location:** `WalkForwardRunner.run_walkforward_analysis()` before line 250

**Issue:** OOS backtests call `run_backtest()` but lack walk-forward context (window, period, fitness function, filter_config) in traces.

**Solution:**
```python
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

oos_result, oos_cerebro, oos_strategy_instance, oos_metrics = run_backtest(...)
```

**Why:** Ensures execution traces include full walk-forward context for OOS runs.

---

### 2. Window-Level Exception Capture (High Priority)
**Location:** `WalkForwardRunner.run_walkforward_analysis()` at line 319

**Issue:** Window-level exceptions are caught but not captured in crash reports.

**Solution:**
```python
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
```

**Why:** Captures window-level failures with full walk-forward context.

---

### 3. Symbol/Timeframe Loop Tracking (Medium Priority)
**Location:** `BacktestRunner.run_walkforward_analysis()` around line 63

**Issue:** No tracing for symbol/timeframe combination iteration.

**Solution:**
```python
from backtester.debug import get_tracer, get_crash_reporter
tracer = get_tracer()
crash_reporter = get_crash_reporter()

for symbol, timeframe in combinations:
    if tracer:
        tracer.set_context(symbol=symbol, timeframe=timeframe)
        tracer.trace('combination_start', 
                    f"Starting walk-forward for {symbol} {timeframe}")
    
    try:
        # Load data
        df = read_cache(symbol, timeframe)
        
        # ... existing code ...
        
    except Exception as e:
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
```

**Why:** Provides visibility into combination-level progress and captures failures.

---

### 4. Filter Computation Errors (Medium Priority)
**Location:** `WalkForwardRunner.run_walkforward_analysis()` around lines 93-105

**Issue:** Filter computation errors are not captured.

**Solution:**
```python
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
```

**Why:** Captures filter computation failures with context.

---

### 5. Window Optimization Tracking (Low Priority)
**Location:** `WindowOptimizer.optimize()` method

**Issue:** No tracing for optimization start/end and best params selection.

**Solution:**
```python
def optimize(self, max_workers: int = 1):
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
    
    # ... existing optimization code ...
    
    optimization_time = time.time() - start_time
    
    # For each fitness function, find best parameters
    best_by_fitness = {}
    for fitness_function in self.fitness_functions:
        # ... existing selection logic ...
        
        if tracer:
            tracer.trace('optimization_best_params',
                        f"Best params for {fitness_function}",
                        fitness_function=fitness_function,
                        best_params=best_params,
                        best_fitness=best_fitness)
    
    if tracer:
        tracer.trace('optimization_end',
                    f"Optimization completed in {optimization_time:.2f}s",
                    duration=optimization_time,
                    best_params_by_fitness={k: v[0] for k, v in best_by_fitness.items()})
    
    return best_by_fitness
```

**Why:** Tracks optimization progress and outcomes for debugging performance issues.

---

### 6. Metrics Recalculation Errors (Medium Priority)
**Location:** `WalkForwardRunner.run_walkforward_analysis()` around line 279

**Issue:** Errors in `recalculate_metrics_with_filtered_trades()` are not captured.

**Solution:**
```python
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
```

**Why:** Captures errors during filtered metrics recalculation.

---

## Implementation Pattern

All additions follow this consistent pattern:

1. **Import debug components** at function start
   ```python
   from backtester.debug import get_tracer, get_crash_reporter
   tracer = get_tracer()
   crash_reporter = get_crash_reporter()
   ```

2. **Set context** before key operations
   ```python
   if tracer:
       tracer.set_context(key=value, ...)
   ```

3. **Trace entry/exit** for major phases
   ```python
   tracer.trace('phase_start', "Starting phase", ...)
   # ... phase code ...
   tracer.trace('phase_end', "Completed phase", duration=..., ...)
   ```

4. **Capture exceptions** with full context
   ```python
   if crash_reporter and crash_reporter.should_capture(...):
       crash_reporter.capture(..., context={...}, ...)
   ```

5. **Re-raise if needed** after capture
   ```python
   raise  # For critical errors that should propagate
   ```

## Files to Modify

1. `src/backtester/backtest/runner.py` - Symbol/timeframe loop
2. `src/backtester/backtest/walkforward/runner.py` - Walk-forward orchestration
3. `src/backtester/backtest/walkforward/optimizer.py` - Optimization tracking

## Estimated Impact

- **Lines of code:** ~60-80 lines added
- **Performance impact:** Negligible (<0.1% overhead)
- **Test coverage:** Integration tests should validate walk-forward context appears in traces

## Implementation Order

1. High Priority (OOS context, window exceptions)
2. Medium Priority (Symbol/timeframe tracking, filter errors, metrics recalculation)
3. Low Priority (Optimization tracking)

