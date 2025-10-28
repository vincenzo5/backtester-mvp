#!/usr/bin/env python3
"""
Simple crypto backtesting engine.
Run: python main.py
Quick test: python main.py --quick
"""

import ccxt
import backtrader as bt
import yaml
from datetime import datetime
import pandas as pd
import time
import json
import os
import argparse
from itertools import product
from tqdm import tqdm
from data.fetch_data import fetch_historical_data, load_exchange_fees


class SMACrossStrategy(bt.Strategy):
    """Simple SMA Crossover Strategy."""
    
    params = (
        ('fast_period', 20),
        ('slow_period', 50),
        ('printlog', True),
    )
    
    def __init__(self):
        self.fast_sma = bt.indicators.SMA(self.data.close, period=self.params.fast_period)
        self.slow_sma = bt.indicators.SMA(self.data.close, period=self.params.slow_period)
        self.crossover = bt.indicators.CrossOver(self.fast_sma, self.slow_sma)
        self.order = None
        self.trade_count = 0
        self.last_position = 0  # Track position changes
        self.buy_count = 0  # Debug: count buy signals
        self.sell_count = 0  # Debug: count sell signals
    
    def log(self, txt, dt=None):
        """Logging function for this strategy."""
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()}: {txt}')
    
    def next(self):
        """Called on every bar."""
        # Skip if we don't have enough data
        if len(self.data) < self.params.slow_period:
            return
        
        # Check if we have a pending order
        if self.order:
            return
        
        # Buy signal: fast SMA crosses above slow SMA
        if not self.position:
            if self.crossover > 0:
                # Use 90% of available cash (leave room for commissions)
                cash = self.broker.getcash()
                size = int((cash * 0.9) / self.data.close[0])
                if size > 0:
                    self.buy_count += 1
                    self.log(f'ORDER: BUY({size}) @ ${self.data.close[0]:.2f}')
                    self.order = self.buy(size=size)
                else:
                    self.log(f'ORDER: BUY(0) @ ${self.data.close[0]:.2f} - INSUFFICIENT CASH')
        
        # Sell signal: fast SMA crosses below slow SMA
        else:
            if self.crossover < 0:
                self.sell_count += 1
                position_size = self.position.size
                self.log(f'ORDER: SELL({position_size}) @ ${self.data.close[0]:.2f}')
                self.order = self.sell()
    
    def notify_order(self, order):
        """Called when order status changes."""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            slippage_pct = 0.0005  # From config
            
            # Order details
            price = order.executed.price
            size = order.executed.size
            commission_dollar = order.executed.comm
            executed_value = order.executed.value
            
            # Count completed trades (round trips)
            # Count when we enter a position (buy order) or exit a position (sell order)
            if order.isbuy():
                # Buying - entering a position
                self.trade_count += 1
                self.last_position = abs(size)
            elif order.issell():
                # Selling - exiting a position
                self.last_position = 0
                # Don't increment count - a round trip is counted on entry
            
            # Cash and portfolio status
            cash_after = self.broker.getcash()
            portfolio_value = self.broker.getvalue()
            
            # Calculate slippage cost
            slippage_dollar = executed_value * slippage_pct
            
            # Total cost (for buy) or proceeds (for sell)
            total_cost = executed_value + commission_dollar + slippage_dollar if order.isbuy() else executed_value - commission_dollar - slippage_dollar
            
            if order.isbuy() and self.params.printlog:
                # BUY format: qty, price, total cost, fee %, cash, portfolio
                fee_pct = commission_dollar/executed_value*100 if executed_value > 0 else 0
                self.log(f'EXECUTION: BUY({size}) @ ${price:.2f} | Cost: ${total_cost:.2f} | Fee: {fee_pct:.2f}% | '
                        f'Cash: ${cash_after:.2f} | Value: ${portfolio_value:.2f}')
            elif order.issell() and self.params.printlog:
                # SELL format: qty (abs value), price, net after fees, fee %, cash, portfolio
                abs_size = abs(size)
                fee_pct = commission_dollar/executed_value*100 if executed_value > 0 else 0
                self.log(f'EXECUTION: SELL({abs_size}) @ ${price:.2f} | Net: ${total_cost:.2f} | Fee: {fee_pct:.2f}% | '
                        f'Cash: ${cash_after:.2f} | Value: ${portfolio_value:.2f}')
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected] and self.params.printlog:
            self.log('Order Canceled/Margin/Rejected')
        
        self.order = None
    
    def stop(self):
        """Called at the end of backtesting."""
        if self.params.printlog:
            self.log(f'Strategy Final Value: {self.broker.getvalue():.2f}')


def run_backtest(config, df, verbose=False):
    """Run the backtest with backtrader.
    
    Args:
        config (dict): Configuration dictionary
        df (pandas.DataFrame): OHLCV data
        verbose (bool): If True, print detailed trade logs
    
    Returns:
        dict: Results dictionary with performance metrics
    """
    backtest_start_time = time.time()
    
    if verbose:
        print("\n" + "="*60)
        print("RUNNING BACKTEST")
        print("="*60 + "\n")
    
    # Create a cerebro entity
    cerebro = bt.Cerebro()
    
    # Add a strategy
    cerebro.addstrategy(
        SMACrossStrategy,
        fast_period=config['strategy']['parameters']['fast_sma_period'],
        slow_period=config['strategy']['parameters']['slow_sma_period'],
        printlog=verbose
    )
    
    # Create a Data Feed from pandas DataFrame
    data = bt.feeds.PandasData(dataname=df)
    
    # Add the Data Feed to Cerebro
    cerebro.adddata(data)
    
    # Set our desired cash start
    cerebro.broker.setcash(config['backtest']['initial_capital'])
    
    # Set commission (load from exchange metadata or config)
    commission = load_exchange_fees(config)
    cerebro.broker.setcommission(commission=commission)
    
    # Get slippage from config
    slippage = config['trading'].get('slippage', 0.0)
    
    if verbose:
        # Log trading parameters
        print("TRADING PARAMETERS:")
        print(f"  Commission: {commission*100:.2f}%")
        print(f"  Slippage: {slippage*100:.2f}%")
        print()
        
        # Print out the starting conditions
        print(f'Starting Portfolio Value: {cerebro.broker.getvalue():.2f}')
    
    # Run over everything and capture strategy instance
    run_result = cerebro.run()
    
    # Extract the strategy instance from the run result
    # run_result is a list of strategy objects directly
    strategy_instance = run_result[0]
    
    initial_value = config['backtest']['initial_capital']
    final_value = cerebro.broker.getvalue()
    total_return = ((final_value - initial_value) / initial_value) * 100
    
    backtest_time = time.time() - backtest_start_time
    
    # Get trade count from strategy - use buy_count which counts trade entries
    trade_count = getattr(strategy_instance, 'buy_count', 0)
    
    if verbose:
        print(f'Final Portfolio Value: {final_value:.2f}')
        print(f"Total Return: {total_return:.2f}%")
        print(f"Commission Rate: {commission*100:.2f}%")
        print(f"Slippage Rate: {slippage*100:.2f}%")
        print(f"Backtest Execution Time: {backtest_time:.2f} seconds")
        print("="*60)
    
    # Return results
    duration_days = None
    if not df.empty and len(df) > 0:
        duration_days = (df.index[-1] - df.index[0]).days
    
    return {
        'initial_capital': initial_value,
        'final_value': final_value,
        'total_return_pct': total_return,
        'num_trades': trade_count,
        'execution_time': backtest_time,
        'start_date': df.index[0].strftime('%Y-%m-%d') if not df.empty else None,
        'end_date': df.index[-1].strftime('%Y-%m-%d') if not df.empty else None,
        'duration_days': duration_days
    }


def load_exchange_metadata():
    """Load exchange metadata from YAML file."""
    with open('config/exchange_metadata.yaml', 'r') as f:
        return yaml.safe_load(f)


def get_symbols_and_timeframes(config):
    """Get symbols and timeframes from config or exchange_metadata."""
    metadata = load_exchange_metadata()
    
    # Get symbols
    symbols = config['exchange'].get('symbols')
    if symbols is None:
        # Use all symbols from metadata
        symbols = metadata['top_markets']
    elif isinstance(symbols, str):
        # Single symbol
        symbols = [symbols]
    # else: already a list
    
    # Validate symbols against metadata
    valid_symbols = metadata['top_markets']
    symbols = [s for s in symbols if s in valid_symbols]
    
    # Get timeframes
    timeframes = config['exchange'].get('timeframes')
    if timeframes is None:
        # Use all timeframes from metadata
        timeframes = metadata['timeframes']
    elif isinstance(timeframes, str):
        # Single timeframe
        timeframes = [timeframes]
    # else: already a list
    
    # Validate timeframes against metadata
    valid_timeframes = metadata['timeframes']
    timeframes = [tf for tf in timeframes if tf in valid_timeframes]
    
    return symbols, timeframes


def save_results_csv(results, config, skipped):
    """Save results to CSV file."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    strategy_name = config['strategy']['name']
    
    os.makedirs('reports', exist_ok=True)
    
    filename = f'reports/backtest_{strategy_name}_{timestamp}.csv'
    
    rows = []
    for result in results:
        rows.append({
            'timestamp': result.get('timestamp'),
            'symbol': result['symbol'],
            'timeframe': result['timeframe'],
            'strategy_name': strategy_name,
            'initial_capital': result['initial_capital'],
            'final_value': result.get('final_value', 'N/A'),
            'total_return_pct': result.get('total_return_pct', 'N/A'),
            'num_trades': result.get('num_trades', 'N/A'),
            'execution_time': result.get('execution_time', 'N/A'),
            'start_date': result.get('start_date', 'N/A'),
            'end_date': result.get('end_date', 'N/A'),
            'status': 'SUCCESS'
        })
    
    # Add skipped combinations
    for skip in skipped:
        rows.append({
            'timestamp': datetime.now().isoformat(),
            'symbol': skip['symbol'],
            'timeframe': skip['timeframe'],
            'strategy_name': strategy_name,
            'initial_capital': config['backtest']['initial_capital'],
            'final_value': 'N/A',
            'total_return_pct': 'N/A',
            'num_trades': 'N/A',
            'execution_time': 'N/A',
            'start_date': 'N/A',
            'end_date': 'N/A',
            'status': f"SKIPPED: {skip['reason']}"
        })
    
    df_results = pd.DataFrame(rows)
    df_results.to_csv(filename, index=False)
    
    print(f"\nResults saved to: {filename}")
    return filename


def save_performance_metrics(config, metrics):
    """Save performance metrics to JSONL file."""
    os.makedirs('performance', exist_ok=True)
    
    performance_entry = {
        'timestamp': datetime.now().isoformat(),
        'strategy_name': config['strategy']['name'],
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
    
    with open('performance/backtest_performance.jsonl', 'a') as f:
        f.write(json.dumps(performance_entry) + '\n')


def print_summary_table(results, skipped):
    """Print a formatted summary table of results."""
    if not results:
        print("\nNo successful backtests to display.")
        return
    
    # Sort by return (descending)
    sorted_results = sorted(results, key=lambda x: x.get('total_return_pct', -999), reverse=True)
    
    print("\n" + "="*140)
    print("BACKTEST SUMMARY")
    print("="*140)
    print(f"{'Symbol':<12} {'Timeframe':<10} {'Return %':<12} {'Final Value':<15} {'Trades':<8} {'Start Date':<12} {'End Date':<12} {'Duration':<10}")
    print("-"*140)
    
    for result in sorted_results:
        symbol = result.get('symbol', 'N/A')
        timeframe = result.get('timeframe', 'N/A')
        return_pct = result.get('total_return_pct', 'N/A')
        final_value = result.get('final_value', 'N/A')
        num_trades = result.get('num_trades', 'N/A')
        start_date = result.get('start_date', 'N/A')
        end_date = result.get('end_date', 'N/A')
        duration_days = result.get('duration_days', None)
        
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
        
        print(f"{symbol:<12} {timeframe:<10} {return_str:<12} {final_str:<15} {num_trades_str:<8} {start_date:<12} {end_date:<12} {duration_str:<10}")
    
    # Statistics
    print("-"*140)
    if results:
        returns = [r.get('total_return_pct') for r in results if isinstance(r.get('total_return_pct'), (int, float))]
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
            print(f"  ⚠️  {skip['symbol']} {skip['timeframe']}: {skip['reason']}")
    
    print("="*140)


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
    
    # Load configuration
    print("Loading configuration...")
    config_start = time.time()
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    config_time = time.time() - config_start
    print(f"Config loaded in {config_time:.3f} seconds\n")
    
    # Get symbols and timeframes
    if quick_test_mode:
        # Force BTC/USD 1h for quick test
        symbols = ['BTC/USD']
        timeframes = ['1h']
        print(f"Quick test mode: Testing single combination")
        print()
    else:
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
    
    # Use progress bar only if more than one combination
    use_progress_bar = len(combinations) > 1 and not quick_test_mode
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
            # Use verbose mode for quick test or single combination
            verbose_mode = quick_test_mode or (len(combinations) == 1 and not quick_test_mode)
            result = run_backtest(config, df, verbose=verbose_mode)
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
