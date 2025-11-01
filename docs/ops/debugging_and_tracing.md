# Debugging, Tracing, and Crash Reporting

## Execution Tracing

Use `ExecutionTracer` to record JSONL traces for long-running operations.

```python
from backtester.debug.tracer import ExecutionTracer
from backtester.config import ConfigManager

config = ConfigManager()
tracer = ExecutionTracer(config.get_debug_config())
tracer.set_context(symbol='BTC/USD', timeframe='1h', strategy='sma_cross')
tracer.trace_function_entry('run_backtest')
# ... work ...
tracer.trace_function_exit('run_backtest', duration=1.23)
tracer.stop()
```

- Output: `artifacts/logs/backtest_execution.jsonl`
- Configure rotation in `config/debug.yaml`.

## Crash Reporter

Capture exceptions and notable events to `artifacts/logs/crash_reports/`.

```python
from backtester.debug.crash_reporter import CrashReporter
crash = CrashReporter(config.get_debug_config(), tracer=None)
crash.start()
try:
    # risky operation
    pass
except Exception as e:
    if crash.should_capture('exception', exception=e, severity='error'):
        crash.capture('exception', exception=e, context={'operation': 'backtest'}, severity='error')
finally:
    crash.stop()
```

## Logging Locations

- Traces: `artifacts/logs/backtest_execution.jsonl`
- Crash reports: `artifacts/logs/crash_reports/`
- Daily updates: `artifacts/logs/daily_update.log`

## Tips

- Set `debug.tracing.level` to `detailed` for deep dives; consider lowering `sample_rate`.
- Always stop tracer/crash reporter to flush buffers.

