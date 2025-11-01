# Performance Attribution

## Backtest Performance Log

Append JSON lines to `artifacts/performance/backtest_performance.jsonl` after runs.

Required fields:
- timestamp (ISO)
- strategy_name
- hardware_signature
- worker_count
- total_combinations, successful_runs, skipped_runs, failed_runs
- total_execution_time, avg_time_per_run
- data_load_time, backtest_compute_time, report_generation_time

Example writer (already implemented): see `backtester.backtest.metrics.save_performance_metrics`.

## Data Fetching Performance

Log bulk fetch performance to `artifacts/logs/bulk_fetch_performance.jsonl`.

Fields:
- timestamp (UTC ISO)
- market (symbol)
- timeframe
- candles, duration (s)
- status (success|skipped|failed)
- source (cache|exchange name)
- api_requests

## Hardware Signature

`HardwareProfile.get_or_create().signature` (cached at `artifacts/performance/hardware_profile.json`).

## Tips

- Use JSONL for easy ingestion.
- Keep file sizes in check via rotation where applicable.

