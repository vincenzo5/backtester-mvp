# Walk-Forward Optimization & Filters Guide

## Overview

Walk-forward splits history into rolling IS/OOS windows, optimizes in-sample, then evaluates out-of-sample. Filters restrict trades by market regimes (e.g., volatility).

## Periods

- Format: `length/step` (e.g., `1Y/6M`)
- Configure in `config/walkforward.yaml` under `walkforward.periods`.

## Parameter Grid

- Define in `config/walkforward.yaml` → `parameter_ranges`.
- Cartesian product via `walkforward/param_grid.py`.

## Running

Programmatic entry points:
- `backtester.backtest.walkforward.runner.WalkForwardRunner`
- CLI examples exist in tests/e2e and system suites.

## Filters

- Implement `BaseFilter` subclasses (see `src/backtester/filters/implementations/...`).
- Register via category `__init__.py` using `register_filter`.
- Configure active filters in `config/walkforward.yaml` → `walkforward.filters`.
- Matching modes: `entry`, `both`, `either`.

### Verifying Filters

```bash
pytest tests/e2e/test_walkforward_filters_e2e.py -v
pytest tests/integration/test_walkforward_integration.py -v
```

## Metrics

- OOS returns are compounded across windows.
- Efficiency = OOS return / IS return (see `BacktestMetrics.walkforward_efficiency`).
- See `docs/metrics_calculation_methodology.md` for formulas.

## Data Preparation

Speed up walk-forward by pre-computing indicators/data sources once with `engine.prepare_backtest_data()` and reusing enriched DataFrames.

## Troubleshooting

- Zero trades → check capital sizing and filter regimes.
- Skipped windows → inspect logs in `artifacts/logs/backtest_execution.jsonl`.

## References

- Runner: `src/backtester/backtest/walkforward/runner.py`
- Optimizer: `src/backtester/backtest/walkforward/optimizer.py`
- Filters: `src/backtester/filters/*`
- Metrics: `src/backtester/backtest/metrics.py`, `docs/metrics_calculation_methodology.md`

