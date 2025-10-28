"""
Bulk data collection script for initial historical fetch.

This script reads markets and timeframes from exchange_metadata.yaml and downloads
all available historical data for all combinations, with validation and auto-cleanup.
"""

import os
import time
import yaml
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from config.manager import ConfigManager
from data.fetcher import create_exchange, fetch_historical, MarketNotFoundError, FetchError
from data.cache_manager import write_cache, get_cache_path
from data.validator import validate_data, remove_duplicates
from services.update_runner import update_exchange_metadata


# Setup logging
LOG_DIR = Path('logs')
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'bulk_fetch.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_metadata():
    """Load exchange metadata configuration."""
    metadata_path = Path('config/exchange_metadata.yaml')
    with open(metadata_path, 'r') as f:
        return yaml.safe_load(f)


def log_performance(performance_file, data):
    """Log performance metrics to JSON Lines file."""
    with open(performance_file, 'a') as f:
        f.write(json.dumps(data) + '\n')


def log_error(error_file, message):
    """Log error to error file."""
    with open(error_file, 'a') as f:
        f.write(f"[{datetime.now().isoformat()}] {message}\n")


def setup_directories():
    """Create necessary directories if they don't exist."""
    directories = ['logs', 'performance', 'data/cache']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)


def fetch_and_save_market(exchange, symbol, timeframe, start_date, end_date, config_manager):
    """
    Fetch market data and save to cache with validation.
    
    Returns:
        tuple: (success bool, df or None, api_requests, source, error_message)
    """
    cache_file = get_cache_path(symbol, timeframe)
    
    # Check if cache already exists
    if cache_file.exists():
        logger.info(f"  Cache exists, skipping {symbol} {timeframe}")
        return True, None, 0, "cache", None
    
    try:
        # Fetch from API
        df, api_requests = fetch_historical(exchange, symbol, timeframe, start_date, end_date)
        
        if df.empty:
            return False, None, api_requests, "api", "No data available"
        
        # Validate and clean data
        validation_result = validate_data(df, timeframe)
        
        if validation_result.get('duplicates', 0) > 0:
            df, _ = remove_duplicates(df)
            logger.info(f"  Removed {validation_result['duplicates']} duplicates")
        
        # Log validation warnings
        if validation_result.get('gaps'):
            logger.warning(f"  Detected {len(validation_result['gaps'])} gaps in data")
        
        # Save to cache
        write_cache(symbol, timeframe, df)
        
        return True, df, api_requests, "api", None
        
    except MarketNotFoundError as e:
        return False, None, 0, "api", f"Market not found: {str(e)}"
    except FetchError as e:
        return False, None, 0, "api", f"Fetch error: {str(e)}"
    except Exception as e:
        return False, None, 0, "api", f"Unexpected error: {str(e)}"


def main():
    """Main execution function."""
    logger.info("=" * 80)
    logger.info("Bulk Data Collection Script")
    logger.info("=" * 80)
    logger.info("")
    
    # Setup directories
    setup_directories()
    
    # Load metadata and config
    metadata = load_metadata()
    try:
        config_manager = ConfigManager()
    except Exception:
        # Config manager might not have historical_start_date yet, use default
        config_manager = None
    
    exchange_name = metadata['exchange']
    markets = metadata['top_markets'].copy()  # Copy to allow modification
    timeframes = metadata['timeframes']
    
    # Get start date from config or use default
    if config_manager and hasattr(config_manager, 'get_historical_start_date'):
        start_date = config_manager.get_historical_start_date()
    else:
        start_date = "2017-01-01"
    
    end_date = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    logger.info(f"Exchange: {exchange_name}")
    logger.info(f"Markets: {len(markets)}")
    logger.info(f"Timeframes: {len(timeframes)}")
    logger.info(f"Start date: {start_date}")
    logger.info(f"End date: {end_date}")
    logger.info(f"Total combinations: {len(markets) * len(timeframes)}")
    logger.info("")
    
    # Initialize exchange with rate limiting
    exchange = create_exchange(exchange_name, enable_rate_limit=True)
    
    # Performance tracking
    performance_file = 'performance/fetch_performance.jsonl'
    error_file = 'logs/fetch_errors.log'
    
    # Clear previous logs
    if os.path.exists(performance_file):
        os.remove(performance_file)
    if os.path.exists(error_file):
        os.remove(error_file)
    
    # Track statistics
    successful = 0
    failed = 0
    skipped = 0
    removed_markets = []
    total_api_requests = 0
    cache_hits = 0
    total_candles = 0
    start_time = time.time()
    
    # Progress tracking
    total_combinations = len(markets) * len(timeframes)
    current = 0
    
    logger.info("Starting data collection...")
    logger.info("-" * 80)
    
    # Fetch data for each market/timeframe combination
    for market in markets.copy():  # Iterate over copy, modify original
        market_available = True
        
        for timeframe in timeframes:
            current += 1
            fetch_start_time = time.time()
            
            logger.info(f"[{current}/{total_combinations}] Fetching {market} {timeframe}...")
            
            success, df, api_requests, source, error_msg = fetch_and_save_market(
                exchange, market, timeframe, start_date, end_date, config_manager
            )
            
            if success and df is not None:
                duration = time.time() - fetch_start_time
                candles = len(df)
                total_candles += candles
                total_api_requests += api_requests
                
                if source == "cache":
                    cache_hits += 1
                    skipped += 1
                else:
                    successful += 1
                
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
                
                logger.info(f"✓ {candles:,} candles in {duration:.1f}s ({candles_per_sec:.0f} candles/s) [{source}]")
            
            elif error_msg and "Market not found" in error_msg:
                duration = time.time() - fetch_start_time
                failed += 1
                logger.info(f"✗ Market not found")
                log_error(error_file, f"{market} {timeframe}: {error_msg}")
                
                # Mark market as unavailable
                if market_available:
                    removed_markets.append(market)
                    market_available = False
            
            else:
                duration = time.time() - fetch_start_time
                failed += 1
                error_msg = error_msg or "No data available"
                logger.info(f"✗ {error_msg[:50]}")
                
                log_error(error_file, f"{market} {timeframe}: {error_msg}")
                
                # Log to performance file
                perf_data = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'market': market,
                    'timeframe': timeframe,
                    'candles': 0,
                    'duration': round(duration, 2),
                    'status': 'error',
                    'source': 'api',
                    'api_requests': api_requests or 0,
                    'error': error_msg
                }
                log_performance(performance_file, perf_data)
    
    # Remove invalid markets from metadata
    if removed_markets:
        removed_markets = list(set(removed_markets))  # Deduplicate
        update_exchange_metadata(removed_markets)
        logger.info(f"Removed {len(removed_markets)} invalid markets: {removed_markets}")
    
    # Calculate summary statistics
    total_duration = time.time() - start_time
    cache_hit_rate = (cache_hits / (successful + skipped) * 100) if (successful + skipped) > 0 else 0
    avg_candles_per_sec = total_candles / total_duration if total_duration > 0 else 0
    
    # Print summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("Summary")
    logger.info("=" * 80)
    logger.info(f"Total runtime: {total_duration / 60:.1f} minutes")
    logger.info(f"Successful fetches: {successful}")
    logger.info(f"Skipped (already cached): {skipped}")
    logger.info(f"Failed fetches: {failed}")
    logger.info(f"Success rate: {((successful + skipped) / total_combinations * 100):.1f}%")
    logger.info(f"Cache hit rate: {cache_hit_rate:.1f}%")
    logger.info(f"Total candles fetched: {total_candles:,}")
    logger.info(f"Average fetch time: {total_duration / total_combinations:.1f}s per market")
    logger.info(f"Total API requests: {total_api_requests:,}")
    logger.info(f"Average candles per second: {avg_candles_per_sec:.0f}")
    logger.info("")
    logger.info(f"✓ Performance data logged to: {performance_file}")
    if failed > 0:
        logger.info(f"✗ Error details logged to: {error_file}")
    logger.info("=" * 80)


if __name__ == '__main__':
    main()

