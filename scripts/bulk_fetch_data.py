"""
Bulk data collection script for fetching historical OHLCV data from exchanges.

This script reads markets and timeframes from exchange_metadata.yaml and downloads
historical data for all combinations, with comprehensive error handling and performance tracking.
"""

import ccxt
import pandas as pd
import os
import time
import yaml
import json
from datetime import datetime, timedelta
from pathlib import Path


def load_metadata():
    """Load exchange metadata configuration."""
    with open('config/exchange_metadata.yaml', 'r') as f:
        return yaml.safe_load(f)


def setup_directories():
    """Create necessary directories if they don't exist."""
    directories = ['logs', 'performance', 'data/cache']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)


def fetch_market_data(exchange, symbol, timeframe, start_date, end_date):
    """
    Fetch OHLCV data for a specific market and timeframe.
    
    Returns:
        tuple: (df, api_requests, source)
            - df: pandas DataFrame with OHLCV data
            - api_requests: number of API requests made
            - source: "cache" or "api"
    """
    # Generate cache filename
    cache_filename = f"{symbol.replace('/', '_')}_{timeframe}_{start_date}_{end_date}.csv"
    cache_file = f"data/cache/{cache_filename}"
    
    # Check if cached data exists
    if os.path.exists(cache_file):
        df = pd.read_csv(cache_file, index_col='datetime', parse_dates=True)
        return df, 0, "cache"
    
    # Fetch from API
    start_ts = exchange.parse8601(start_date + 'T00:00:00Z')
    end_ts = exchange.parse8601(end_date + 'T00:00:00Z')
    
    since = start_ts
    all_ohlcv = []
    api_requests = 0
    
    while since < end_ts:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since, limit=1000)
            if not ohlcv:
                break
            all_ohlcv.extend(ohlcv)
            since = ohlcv[-1][0] + 1  # Start from next candle
            api_requests += 1
        except Exception as e:
            print(f"  Error fetching chunk: {e}")
            break
    
    if not all_ohlcv:
        return None, api_requests, "api"
    
    # Convert to DataFrame
    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('datetime', inplace=True)
    df.drop('timestamp', axis=1, inplace=True)
    
    # Save to cache
    df.to_csv(cache_file)
    
    return df, api_requests, "api"


def log_performance(performance_file, data):
    """Log performance metrics to JSON Lines file."""
    with open(performance_file, 'a') as f:
        f.write(json.dumps(data) + '\n')


def main():
    """Main execution function."""
    print("=" * 80)
    print("Bulk Data Collection Script")
    print("=" * 80)
    print()
    
    # Setup directories
    setup_directories()
    
    # Load metadata
    metadata = load_metadata()
    exchange_name = metadata['exchange']
    markets = metadata['top_markets']
    timeframes = metadata['timeframes']
    
    # Calculate date range
    start_date = "2017-01-01"
    end_date = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"Exchange: {exchange_name}")
    print(f"Markets: {len(markets)}")
    print(f"Timeframes: {len(timeframes)}")
    print(f"Date range: {start_date} to {end_date}")
    print(f"Total combinations: {len(markets) * len(timeframes)}")
    print()
    
    # Initialize exchange with rate limiting
    exchange = getattr(ccxt, exchange_name)({'enableRateLimit': True})
    
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
    cache_hits = 0
    total_candles = 0
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
            
            print(f"[{current}/{total_combinations}] Fetching {market} {timeframe}...", end=' ')
            
            try:
                df, api_requests, source = fetch_market_data(
                    exchange, market, timeframe, start_date, end_date
                )
                
                if df is not None:
                    duration = time.time() - fetch_start_time
                    candles = len(df)
                    total_candles += candles
                    total_api_requests += api_requests
                    
                    if source == "cache":
                        cache_hits += 1
                    
                    # Log performance
                    perf_data = {
                        'timestamp': datetime.utcnow().isoformat() + 'Z',
                        'market': market,
                        'timeframe': timeframe,
                        'candles': candles,
                        'duration': round(duration, 2),
                        'status': 'success',
                        'source': source,
                        'api_requests': api_requests
                    }
                    log_performance(performance_file, perf_data)
                    
                    # Calculate candles per second
                    candles_per_sec = candles / duration if duration > 0 else 0
                    
                    print(f"✓ {candles:,} candles in {duration:.1f}s ({candles_per_sec:.0f} candles/s) [{source}]")
                    successful += 1
                else:
                    # Data fetch returned None (likely no data available)
                    duration = time.time() - fetch_start_time
                    perf_data = {
                        'timestamp': datetime.utcnow().isoformat() + 'Z',
                        'market': market,
                        'timeframe': timeframe,
                        'candles': 0,
                        'duration': round(duration, 2),
                        'status': 'no_data',
                        'source': 'api',
                        'api_requests': api_requests
                    }
                    log_performance(performance_file, perf_data)
                    print(f"⚠ No data available")
                    failed += 1
                    
            except ccxt.ExchangeError as e:
                duration = time.time() - fetch_start_time
                failed += 1
                error_msg = f"Exchange error for {market} {timeframe}: {str(e)}"
                print(f"✗ Exchange error")
                
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
                    'source': 'api',
                    'api_requests': 0,
                    'error': str(e)
                }
                log_performance(performance_file, perf_data)
                
            except ccxt.NetworkError as e:
                duration = time.time() - fetch_start_time
                failed += 1
                error_msg = f"Network error for {market} {timeframe}: {str(e)}"
                print(f"✗ Network error")
                
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
                    'source': 'api',
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
                    'source': 'api',
                    'api_requests': 0,
                    'error': str(e)
                }
                log_performance(performance_file, perf_data)
    
    # Calculate summary statistics
    total_duration = time.time() - start_time
    cache_hit_rate = (cache_hits / successful * 100) if successful > 0 else 0
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
    print(f"Cache hit rate: {cache_hit_rate:.1f}%")
    print(f"Total candles fetched: {total_candles:,}")
    print(f"Average fetch time: {total_duration / total_combinations:.1f}s per market")
    print(f"Total API requests: {total_api_requests:,}")
    print(f"Average candles per second: {avg_candles_per_sec:.0f}")
    print()
    print(f"✓ Performance data logged to: {performance_file}")
    if failed > 0:
        print(f"✗ Error details logged to: {error_file}")
    print("=" * 80)


if __name__ == '__main__':
    main()

