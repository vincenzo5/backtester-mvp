#!/usr/bin/env python3
"""
Simple crypto backtesting engine.
Run: python main.py
Quick test: python main.py --quick
"""

import sys
import time

from cli.parser import parse_arguments
from cli.output import ConsoleOutput
from config.manager import ConfigManager
from backtest.runner import BacktestRunner
from backtest.metrics import save_results_csv, save_performance_metrics
from strategies import get_strategy_class


def validate_dependencies():
    """Ensure required dependencies are available."""
    try:
        import psutil
    except ImportError:
        print("\n" + "="*80)
        print("ERROR: Missing required dependency")
        print("="*80)
        print("\npsutil is required for parallel execution.")
        print("\nInstall dependencies:")
        print("  pip install -r requirements.txt")
        print("\n" + "="*80)
        sys.exit(1)


def main():
    """Main entry point for the backtesting engine."""
    # Validate dependencies first
    validate_dependencies()
    
    # Parse CLI arguments
    args = parse_arguments()
    
    # Load configuration
    config_start = time.time()
    config = ConfigManager(profile_name=args.profile)
    config_time = time.time() - config_start
    
    # Setup output handler
    output = ConsoleOutput(verbose=config.get_verbose())
    
    # Print banner
    output.print_banner(config, quick_mode=args.quick)
    
    # Print config loading info
    output.print_config_loading(config_time)
    
    # Get strategy class
    strategy_class = get_strategy_class(config.get_strategy_name())
    
    # Create runner and execute backtests
    runner = BacktestRunner(config, output)
    run_results = runner.run_multi_backtest(strategy_class)
    
    # Generate reports and save metrics
    report_gen_start = time.time()
    save_results_csv(run_results.results, config, run_results.skipped)
    report_gen_time = time.time() - report_gen_start
    
    # Update report generation time in results
    run_results.report_generation_time = report_gen_time
    
    # Save performance metrics
    save_performance_metrics(config, run_results.get_metrics())
    
    # Print summaries
    output.print_summary_table(run_results)
    output.print_performance_summary(run_results)


if __name__ == '__main__':
    main()
