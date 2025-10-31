"""
Performance metrics and reporting module.

This module handles generating reports, saving results, and displaying
performance metrics from backtest runs.
"""

import pandas as pd
from datetime import datetime
import json
import os
from typing import List

from backtester.backtest.result import BacktestResult, SkippedRun


def save_results_csv(results: List[BacktestResult], config_manager, skipped: List[SkippedRun]):
    """
    Save results to CSV file.
    
    Args:
        results: List of BacktestResult objects
        config_manager: ConfigManager instance
        skipped: List of SkippedRun objects
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    strategy_name = config_manager.get_strategy_name()
    
    os.makedirs('artifacts/reports', exist_ok=True)
    
    filename = f'artifacts/reports/backtest_{strategy_name}_{timestamp}.csv'
    
    rows = []
    # Add successful results
    for result in results:
        final_value = result.initial_capital + result.metrics.net_profit
        
        row = {
            'timestamp': result.timestamp,
            'symbol': result.symbol,
            'timeframe': result.timeframe,
            'strategy_name': strategy_name,
            'initial_capital': result.initial_capital,
            'final_value': final_value,
            'total_return_pct': result.metrics.total_return_pct,
            'num_trades': result.metrics.num_trades,
            'execution_time': result.execution_time,
            'start_date': result.start_date or 'N/A',
            'end_date': result.end_date or 'N/A',
            'status': 'SUCCESS'
        }
        # Add key metrics to CSV
        row.update({
            'sharpe_ratio': result.metrics.sharpe_ratio,
            'max_drawdown': result.metrics.max_drawdown,
            'profit_factor': result.metrics.profit_factor,
            'win_rate_pct': result.metrics.win_rate_pct
        })
        rows.append(row)
    
    # Add skipped combinations
    for skip in skipped:
        rows.append({
            'timestamp': skip.timestamp,
            'symbol': skip.symbol,
            'timeframe': skip.timeframe,
            'strategy_name': strategy_name,
            'initial_capital': config_manager.get_walkforward_initial_capital(),
            'final_value': 'N/A',
            'total_return_pct': 'N/A',
            'num_trades': 'N/A',
            'execution_time': 'N/A',
            'start_date': 'N/A',
            'end_date': 'N/A',
            'status': f"SKIPPED: {skip.reason}"
        })
    
    df_results = pd.DataFrame(rows)
    df_results.to_csv(filename, index=False)
    
    print(f"\nResults saved to: {filename}")
    return filename


def save_performance_metrics(config_manager, metrics):
    """Save performance metrics to JSONL file with parallel execution info."""
    os.makedirs('artifacts/performance', exist_ok=True)
    
    # Load hardware profile for signature
    try:
        from backtester.backtest.execution.hardware import HardwareProfile
        hardware = HardwareProfile.get_or_create()
        hardware_signature = hardware.signature
    except Exception:
        hardware_signature = 'unknown'
    
    performance_entry = {
        'timestamp': datetime.now().isoformat(),
        'strategy_name': config_manager.get_strategy_name(),
        'hardware_signature': hardware_signature,
        'worker_count': metrics.get('worker_count', 1),
        'total_combinations': metrics['total_combinations'],
        'successful_runs': metrics['successful_runs'],
        'skipped_runs': metrics['skipped_runs'],
        'failed_runs': metrics['failed_runs'],
        'total_execution_time': metrics['total_execution_time'],
        'avg_time_per_run': metrics['avg_time_per_run'],
        'data_load_time': metrics['data_load_time'],
        'backtest_compute_time': metrics['backtest_compute_time'],
        'report_generation_time': metrics['report_generation_time']
    }
    
    with open('artifacts/performance/backtest_performance.jsonl', 'a') as f:
        f.write(json.dumps(performance_entry) + '\n')


def print_summary_table(results: List[BacktestResult], skipped: List[SkippedRun]):
    """
    Print a formatted summary table of results.
    
    NOTE: This function is deprecated. Use ConsoleOutput.print_summary_table instead.
    Kept for backwards compatibility.
    
    Args:
        results: List of BacktestResult objects
        skipped: List of SkippedRun objects
    """
    if not results:
        print("\nNo successful backtests to display.")
        return
    
    # Sort by return (descending)
    sorted_results = sorted(
        results,
        key=lambda x: x.metrics.total_return_pct if isinstance(x.metrics.total_return_pct, (int, float)) else -999,
        reverse=True
    )
    
    print("\n" + "="*140)
    print("BACKTEST SUMMARY")
    print("="*140)
    print(f"{'Symbol':<12} {'Timeframe':<10} {'Return %':<12} {'Final Value':<15} {'Trades':<8} {'Start Date':<12} {'End Date':<12} {'Duration':<10}")
    print("-"*140)
    
    for result in sorted_results:
        return_pct = result.metrics.total_return_pct
        final_value = result.initial_capital + result.metrics.net_profit
        num_trades = result.metrics.num_trades
        duration_days = result.metrics.total_calendar_days
        
        if isinstance(return_pct, (int, float)):
            return_str = f"{return_pct:.2f}%"
        else:
            return_str = str(return_pct)
        
        if isinstance(final_value, (int, float)):
            final_str = f"${final_value:,.2f}"
        else:
            final_str = str(final_value)
        
        num_trades_str = str(num_trades)
        duration_str = f"{duration_days} days" if isinstance(duration_days, int) else 'N/A'
        start_date = result.start_date or 'N/A'
        end_date = result.end_date or 'N/A'
        
        print(f"{result.symbol:<12} {result.timeframe:<10} {return_str:<12} {final_str:<15} {num_trades_str:<8} {start_date:<12} {end_date:<12} {duration_str:<10}")
    
    # Statistics
    print("-"*140)
    if results:
        returns = [r.metrics.total_return_pct for r in results if isinstance(r.metrics.total_return_pct, (int, float))]
        if returns:
            avg_return = sum(returns) / len(returns)
            max_return = max(returns)
            min_return = min(returns)
            print(f"\nAggregate Statistics:")
            print(f"  Successful runs: {len(results)}")
            print(f"  Average return: {avg_return:.2f}%")
            print(f"  Best return: {max_return:.2f}%")
            print(f"  Worst return: {min_return:.2f}%")
            print(f"  Skipped runs: {len(skipped)}")
    
    if skipped:
        print(f"\nSkipped Combinations ({len(skipped)}):")
        for skip in skipped:
            print(f"  ⚠️  {skip.symbol} {skip.timeframe}: {skip.reason}")
    
    print("="*140)

