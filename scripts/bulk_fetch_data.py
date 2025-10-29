"""
Bulk data collection script for fetching historical OHLCV data from exchanges.

This script reads markets and timeframes from exchange_metadata.yaml, discovers
the best exchange for each market/timeframe combination, and downloads historical
data with comprehensive error handling and performance tracking.
"""

import os
import sys
import time
import yaml
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.exchange_discovery import find_best_exchange
from data.fetcher import create_exchange, fetch_historical, MarketNotFoundError, FetchError
from data.cache_manager import delete_cache, write_cache, get_cache_path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_metadata():
    """Load exchange metadata configuration."""
    with open('config/exchange_metadata.yaml', 'r') as f:
        return yaml.safe_load(f)


def setup_directories():
    """Create necessary directories if they don't exist."""
    directories = ['logs', 'performance', 'data/cache']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)


def log_performance(performance_file, data):
    """Log performance metrics to JSON Lines file."""
    with open(performance_file, 'a') as f:
        f.write(json.dumps(data) + '\n')


def main():
    """Main execution function."""
    print("=" * 80)
    print("Multi-Exchange Bulk Data Collection Script")
    print("=" * 80)
    print()
    
    # Setup directories
    setup_directories()
    
    # Load metadata
    metadata = load_metadata()
    execution_exchange = metadata.get('exchange', 'coinbase')
    exchanges = metadata.get('exchanges', ['coinbase', 'binance', 'kraken'])
    markets = metadata['top_markets']
    timeframes = metadata['timeframes']
    
    # Calculate date range
    start_date = "2017-01-01"
    end_date = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"Execution exchange: {execution_exchange}")
    print(f"Data collection exchanges: {exchanges}")
    print(f"Markets: {len(markets)}")
    print(f"Timeframes: {len(timeframes)}")
    print(f"Date range: {start_date} to {end_date}")
    print(f"Total combinations: {len(markets) * len(timeframes)}")
    print()
    
    # Performance tracking
    performance_file = 'performance/fetch_performance.jsonl'
    error_file = 'logs/fetch_errors.log'
    
    # Clear previous performance log
    if os.path.exists(performance_file):
        os.remove(performance_file)
    
    # Clear previous error log
    if os.path.exists(error_file):
        os.remove(error_file)
    
    # Track statistics
    successful = 0
    failed = 0
    total_api_requests = 0
    total_candles = 0
    exchange_usage = {}  # Track exchange usage
    start_time = time.time()
    
    # Progress tracking
    total_combinations = len(markets) * len(timeframes)
    current = 0
    
    print("Starting data collection...")
    print("-" * 80)
    
    # Fetch data for each market/timeframe combination
    for market in markets:
        for timeframe in timeframes:
            current += 1
            fetch_start_time = time.time()
            
            print(f"[{current}/{total_combinations}] {market} {timeframe}...", end=' ', flush=True)
            
            try:
                # Step 1: Find best exchange for this market/timeframe
                best_exchange, earliest_date = find_best_exchange(market, timeframe, exchanges)
                
                if best_exchange is None:
                    duration = time.time() - fetch_start_time
                    perf_data = {
                        'timestamp': datetime.utcnow().isoformat() + 'Z',
                        'market': market,
                        'timeframe': timeframe,
                        'candles': 0,
                        'duration': round(duration, 2),
                        'status': 'no_exchange',
                        'source_exchange': None,
                        'api_requests': 0
                    }
                    log_performance(performance_file, perf_data)
                    print(f"⚠ No exchange found with data")
                    failed += 1
                    continue
                
                # Step 2: Delete existing cache (clean replacement)
                cache_path = get_cache_path(market, timeframe)
                if cache_path.exists():
                    delete_cache(market, timeframe)
                
                # Step 3: Fetch data from best exchange
                exchange = create_exchange(best_exchange, enable_rate_limit=True)
                
                # Use earliest date found as start date, or default to 2017-01-01
                fetch_start = earliest_date.strftime('%Y-%m-%d') if earliest_date else start_date
                
                df, api_requests = fetch_historical(
                    exchange, market, timeframe,
                    fetch_start, end_date,
                    auto_find_earliest=True,
                    source_exchange=best_exchange
                )
                
                if df.empty:
                    duration = time.time() - fetch_start_time
                    perf_data = {
                        'timestamp': datetime.utcnow().isoformat() + 'Z',
                        'market': market,
                        'timeframe': timeframe,
                        'candles': 0,
                        'duration': round(duration, 2),
                        'status': 'no_data',
                        'source_exchange': best_exchange,
                        'api_requests': api_requests
                    }
                    log_performance(performance_file, perf_data)
                    print(f"⚠ No data fetched from {best_exchange}")
                    failed += 1
                else:
                    # Step 4: Save to cache with source_exchange in manifest
                    write_cache(market, timeframe, df, source_exchange=best_exchange)
                    
                    duration = time.time() - fetch_start_time
                    candles = len(df)
                    total_candles += candles
                    total_api_requests += api_requests
                    
                    # Track exchange usage
                    if best_exchange not in exchange_usage:
                        exchange_usage[best_exchange] = 0
                    exchange_usage[best_exchange] += 1
                    
                    # Log performance
                    perf_data = {
                        'timestamp': datetime.utcnow().isoformat() + 'Z',
                        'market': market,
                        'timeframe': timeframe,
                        'candles': candles,
                        'duration': round(duration, 2),
                        'status': 'success',
                        'source_exchange': best_exchange,
                        'earliest_date': fetch_start,
                        'api_requests': api_requests
                    }
                    log_performance(performance_file, perf_data)
                    
                    # Calculate candles per second
                    candles_per_sec = candles / duration if duration > 0 else 0
                    
                    print(f"✓ {candles:,} candles from {best_exchange} ({earliest_date.date() if earliest_date else 'N/A'}) in {duration:.1f}s ({candles_per_sec:.0f} candles/s)")
                    successful += 1
                    
            except (MarketNotFoundError, FetchError) as e:
                duration = time.time() - fetch_start_time
                failed += 1
                error_msg = f"Fetch error for {market} {timeframe}: {str(e)}"
                print(f"✗ {str(e)[:50]}")
                
                # Log to error file
                with open(error_file, 'a') as f:
                    f.write(f"[{datetime.now().isoformat()}] {error_msg}\n")
                
                # Log to performance file
                perf_data = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'market': market,
                    'timeframe': timeframe,
                    'candles': 0,
                    'duration': round(duration, 2),
                    'status': 'error',
                    'source_exchange': None,
                    'api_requests': 0,
                    'error': str(e)
                }
                log_performance(performance_file, perf_data)
                
            except Exception as e:
                duration = time.time() - fetch_start_time
                failed += 1
                error_msg = f"Unexpected error for {market} {timeframe}: {str(e)}"
                print(f"✗ Error: {str(e)[:50]}")
                
                # Log to error file
                with open(error_file, 'a') as f:
                    f.write(f"[{datetime.now().isoformat()}] {error_msg}\n")
                
                # Log to performance file
                perf_data = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'market': market,
                    'timeframe': timeframe,
                    'candles': 0,
                    'duration': round(duration, 2),
                    'status': 'error',
                    'source_exchange': None,
                    'api_requests': 0,
                    'error': str(e)
                }
                log_performance(performance_file, perf_data)
    
    # Calculate summary statistics
    total_duration = time.time() - start_time
    avg_candles_per_sec = total_candles / total_duration if total_duration > 0 else 0
    
    # Print summary
    print()
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"Total runtime: {total_duration / 60:.1f} minutes")
    print(f"Successful fetches: {successful}")
    print(f"Failed fetches: {failed}")
    print(f"Success rate: {(successful / total_combinations * 100):.1f}%")
    print(f"Total candles fetched: {total_candles:,}")
    print(f"Average fetch time: {total_duration / total_combinations:.1f}s per market")
    print(f"Total API requests: {total_api_requests:,}")
    print(f"Average candles per second: {avg_candles_per_sec:.0f}")
    print()
    print("Exchange usage:")
    for exchange, count in sorted(exchange_usage.items(), key=lambda x: x[1], reverse=True):
        print(f"  {exchange}: {count} market/timeframe combinations")
    print()
    print(f"✓ Performance data logged to: {performance_file}")
    if failed > 0:
        print(f"✗ Error details logged to: {error_file}")
    print("=" * 80)


if __name__ == '__main__':
    main()
