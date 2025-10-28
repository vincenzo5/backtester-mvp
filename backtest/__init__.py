"""
Backtesting engine module.

This module provides the core backtesting functionality including:
- Running backtests on historical data
- Generating performance metrics
- Exporting results to CSV
"""

# Lazy imports to avoid circular dependencies
__all__ = [
    'run_backtest',
    'save_results_csv',
    'print_summary_table',
    'save_performance_metrics',
]

# Lazy imports on module level for cleaner API
def __getattr__(name):
    if name == 'run_backtest':
        from backtest import engine
        return getattr(engine, name)
    elif name in ['save_results_csv', 'print_summary_table', 'save_performance_metrics']:
        from backtest import metrics
        return getattr(metrics, name)
    raise AttributeError(f"module {__name__} has no attribute {name}")

