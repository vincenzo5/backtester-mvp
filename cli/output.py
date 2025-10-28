"""
Console output formatting module.

This module handles all user-facing console output including banners,
progress indicators, summaries, and error messages.
"""

from typing import Optional
from tqdm import tqdm
from config.manager import ConfigManager
from backtest.result import RunResults


class ConsoleOutput:
    """
    Handles all console output formatting for the backtesting engine.
    """
    
    def __init__(self, verbose: bool = False):
        """
        Initialize console output handler.
        
        Args:
            verbose: If True, enable verbose output mode
        """
        self.verbose = verbose
    
    def print_banner(self, config: ConfigManager, quick_mode: bool = False):
        """Print application banner."""
        print("Crypto Backtesting Engine - Multi-Market Multi-Timeframe")
        if quick_mode:
            print("QUICK TEST MODE: BTC/USD 1h")
        print("="*100)
    
    def print_config_loading(self, load_time: float):
        """Print configuration loading message."""
        print("Loading configuration...")
        print(f"Config loaded in {load_time:.3f} seconds\n")
    
    def print_combinations_info(self, num_symbols: int, num_timeframes: int, total_combinations: int):
        """Print information about symbol/timeframe combinations."""
        print(f"Symbols to test: {num_symbols}")
        print(f"Timeframes to test: {num_timeframes}")
        print(f"Total combinations: {total_combinations}")
        print()
    
    def print_running_backtests(self):
        """Print backtest execution start message."""
        print("Running backtests...\n")
    
    def skip_message(self, symbol: str, timeframe: str, reason: str, use_tqdm: bool = False):
        """
        Print skip message for a symbol/timeframe combination.
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe string
            reason: Reason for skipping
            use_tqdm: If True, use tqdm.write to avoid breaking progress bar
        """
        message = f"⚠️  Skipped {symbol} {timeframe} - {reason}"
        if use_tqdm:
            tqdm.write(message)
        else:
            print(message)
    
    def error_message(self, symbol: str, timeframe: str, error: Exception, use_tqdm: bool = False):
        """
        Print error message for a failed backtest.
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe string
            error: Exception that occurred
            use_tqdm: If True, use tqdm.write to avoid breaking progress bar
        """
        message = f"❌ Error running {symbol} {timeframe}: {error}"
        if use_tqdm:
            tqdm.write(message)
        else:
            print(message)
    
    def print_summary_table(self, results: RunResults):
        """
        Print formatted summary table of backtest results.
        
        Args:
            results: RunResults object containing all backtest outcomes
        """
        if not results.results:
            print("\nNo successful backtests to display.")
            return
        
        sorted_results = results.get_sorted_results(reverse=True)
        
        print("\n" + "="*140)
        print("BACKTEST SUMMARY")
        print("="*140)
        print(f"{'Symbol':<12} {'Timeframe':<10} {'Return %':<12} {'Final Value':<15} {'Trades':<8} {'Start Date':<12} {'End Date':<12} {'Duration':<10}")
        print("-"*140)
        
        for result in sorted_results:
            return_pct = result.total_return_pct
            final_value = result.final_value
            num_trades = result.num_trades
            duration_days = result.duration_days
            
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
        if results.results:
            returns = [r.total_return_pct for r in results.results if isinstance(r.total_return_pct, (int, float))]
            if returns:
                avg_return = sum(returns) / len(returns)
                max_return = max(returns)
                min_return = min(returns)
                print(f"\nAggregate Statistics:")
                print(f"  Successful runs: {len(results.results)}")
                print(f"  Average return: {avg_return:.2f}%")
                print(f"  Best return: {max_return:.2f}%")
                print(f"  Worst return: {min_return:.2f}%")
                print(f"  Skipped runs: {len(results.skipped)}")
        
        if results.skipped:
            print(f"\nSkipped Combinations ({len(results.skipped)}):")
            for skip in results.skipped:
                print(f"  ⚠️  {skip.symbol} {skip.timeframe}: {skip.reason}")
        
        print("="*140)
    
    def print_performance_summary(self, results: RunResults):
        """Print final performance summary."""
        print("\n" + "="*100)
        print("PERFORMANCE SUMMARY")
        print("="*100)
        print(f"Total combinations: {results.total_combinations}")
        print(f"Successful: {results.successful_runs}")
        print(f"Skipped: {results.skipped_runs}")
        print(f"Failed: {results.failed_runs}")
        print(f"Parallel workers: {results.worker_count}")
        print(f"Total execution time: {results.total_execution_time:.2f} seconds")
        print(f"Average time per run: {results.avg_time_per_run:.3f} seconds")
        print(f"Data load time: {results.data_load_time:.2f} seconds")
        print(f"Backtest compute time: {results.backtest_compute_time:.2f} seconds")
        print(f"Report generation time: {results.report_generation_time:.2f} seconds")
        print("="*100)

