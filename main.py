#!/usr/bin/env python3
"""
Simple crypto backtesting engine.
Run: python main.py
Quick test: python main.py --quick
"""

import time
import argparse
from itertools import product
from tqdm import tqdm
from datetime import datetime

# Import from refactored modules
from config.manager import ConfigManager
from data.fetch_data import fetch_historical_data
from backtest.engine import run_backtest, get_symbols_and_timeframes
from backtest.metrics import save_results_csv, print_summary_table, save_performance_metrics
from strategies import get_strategy_class

def main():
    """Main function to run multi-market, multi-timeframe backtest."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Crypto backtesting engine')
    parser.add_argument('--quick', action='store_true',
                       help='Run quick test: BTC/USD 1h with verbose output')
    args = parser.parse_args()
    
    total_start_time = time.time()
    quick_test_mode = args.quick
    
    print("Crypto Backtesting Engine - Multi-Market Multi-Timeframe")
    if quick_test_mode:
        print("QUICK TEST MODE: BTC/USD 1h")
    print("="*100)
    
    # Load configuration with ConfigManager
    print("Loading configuration...")
    config_start = time.time()
    
    # Use quick profile if --quick flag is set
    profile_name = 'quick' if quick_test_mode else None
    config = ConfigManager(profile_name=profile_name)
    
    config_time = time.time() - config_start
    print(f"Config loaded in {config_time:.3f} seconds\n")
    
    # Get strategy class dynamically
    strategy_class = get_strategy_class(config.get_strategy_name())
    
    # Get symbols and timeframes
    symbols, timeframes = get_symbols_and_timeframes(config)
    print(f"Symbols to test: {len(symbols)}")
    print(f"Timeframes to test: {len(timeframes)}")
    print(f"Total combinations: {len(symbols) * len(timeframes)}")
    
    print()
    
    # Initialize performance tracking
    results = []
    skipped = []
    total_combinations = len(symbols) * len(timeframes)
    successful_runs = 0
    skipped_runs = 0
    failed_runs = 0
    
    data_load_time = 0.0
    backtest_compute_time = 0.0
    
    # Generate all combinations
    combinations = list(product(symbols, timeframes))
    
    # Run backtests with progress bar
    print("Running backtests...\n")
    
    # Get verbose setting from config
    verbose_setting = config.get_verbose()
    
    # Use progress bar only if more than one combination
    use_progress_bar = len(combinations) > 1
    iterator = tqdm(combinations, desc="Progress") if use_progress_bar else combinations
    
    for symbol, timeframe in iterator:
        timestamp = datetime.now().isoformat()
        
        # Track data loading time
        load_start = time.time()
        df = fetch_historical_data(config, symbol=symbol, timeframe=timeframe)
        data_load_time += time.time() - load_start
        
        # Check if data exists
        if df.empty:
            tqdm.write(f"⚠️  Skipped {symbol} {timeframe} - no cached data")
            skipped.append({
                'symbol': symbol,
                'timeframe': timeframe,
                'reason': 'no cached data'
            })
            skipped_runs += 1
            continue
        
        # Run backtest
        try:
            backtest_start = time.time()
            # Use verbose mode from config or single combination
            verbose_mode = verbose_setting or (len(combinations) == 1)
            result = run_backtest(config, df, strategy_class, verbose=verbose_mode)
            backtest_time = time.time() - backtest_start
            backtest_compute_time += backtest_time
            
            # Store results
            result['timestamp'] = timestamp
            result['symbol'] = symbol
            result['timeframe'] = timeframe
            results.append(result)
            successful_runs += 1
            
        except Exception as e:
            tqdm.write(f"❌ Error running {symbol} {timeframe}: {e}")
            skipped.append({
                'symbol': symbol,
                'timeframe': timeframe,
                'reason': f'error: {str(e)}'
            })
            failed_runs += 1
    
    # Calculate total execution time
    total_execution_time = time.time() - total_start_time
    avg_time_per_run = backtest_compute_time / successful_runs if successful_runs > 0 else 0
    
    # Generate reports (only time this operation)
    print()
    report_gen_start = time.time()
    save_results_csv(results, config, skipped)
    print_summary_table(results, skipped)
    report_gen_time = time.time() - report_gen_start
    
    # Save performance metrics
    metrics = {
        'total_combinations': total_combinations,
        'successful_runs': successful_runs,
        'skipped_runs': skipped_runs,
        'failed_runs': failed_runs,
        'total_execution_time': total_execution_time,
        'avg_time_per_run': avg_time_per_run,
        'data_load_time': data_load_time,
        'backtest_compute_time': backtest_compute_time,
        'report_generation_time': report_gen_time
    }
    save_performance_metrics(config, metrics)
    
    # Final summary
    print("\n" + "="*100)
    print("PERFORMANCE SUMMARY")
    print("="*100)
    print(f"Total combinations: {total_combinations}")
    print(f"Successful: {successful_runs}")
    print(f"Skipped: {skipped_runs}")
    print(f"Failed: {failed_runs}")
    print(f"Total execution time: {total_execution_time:.2f} seconds")
    print(f"Average time per run: {avg_time_per_run:.3f} seconds")
    print(f"Data load time: {data_load_time:.2f} seconds")
    print(f"Backtest compute time: {backtest_compute_time:.2f} seconds")
    print(f"Report generation time: {report_gen_time:.2f} seconds")
    print("="*100)


if __name__ == '__main__':
    main()
