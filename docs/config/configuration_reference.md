# Configuration Reference

## Overview

Configuration is split by domain. Access configs via `ConfigManager` (typed accessors). Do not rely on a monolithic `config.yaml`.

## Files

- `config/data.yaml` – data sources, cache, start dates
- `config/strategy.yaml` – strategy selection/params
- `config/trading.yaml` – capital, slippage/fees
- `config/walkforward.yaml` – periods, parameter ranges, filters
- `config/parallel.yaml` – worker counts and batch sizing
- `config/debug.yaml` – logging/tracing/crash reporting
- `config/markets.yaml` – symbols/timeframes selection
- `config/profiles/*.yaml` – profile overrides

## Access Patterns

```python
from backtester.config import ConfigManager
config = ConfigManager()
bt_cfg = config.get_backtest_config()
wf_cfg = config.get_walkforward_config()
```

## Validation

- Range checks for numerics
- ISO date formats, logical constraints (end > start)
- Enums (e.g., mode: auto|manual)

## Examples

`config/data.yaml`:
```yaml
data:
  exchange: coinbase
  cache_enabled: true
  cache_directory: data
  historical_start_date: "2017-01-01"
```

`config/strategy.yaml`:
```yaml
strategy:
  name: sma_cross
```

`config/walkforward.yaml`:
```yaml
walkforward:
  periods: ['1Y/6M']
  parameter_ranges:
    fast_period: {start: 10, end: 20, step: 5}
    slow_period: {start: 20, end: 40, step: 10}
  filters:
    - volatility_regime_atr
```

## Notes

- Prefer YAML updates over CLI flags.
- Use absolute imports and typed accessors in code.

