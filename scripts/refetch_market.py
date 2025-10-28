"""
Manual re-fetch utility for fixing corrupted or missing data.

This script allows re-fetching a specific market/timeframe combination
from the configurable start date to today.
"""

import sys
import argparse
import logging
from datetime import datetime

from config.manager import ConfigManager
from data.fetcher import create_exchange, fetch_historical, MarketNotFoundError, FetchError
from data.cache_manager import delete_cache, write_cache, get_cache_path
from data.validator import validate_data, remove_duplicates


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def refetch_market(symbol: str, timeframe: str, exchange_name: str = None, 
                  start_date: str = None, force: bool = False):
    """
    Re-fetch a specific market/timeframe.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
        exchange_name: Exchange name (defaults to config)
        start_date: Start date (YYYY-MM-DD, defaults to config)
        force: If True, delete existing cache before fetching
    """
    logger.info("=" * 80)
    logger.info(f"Re-fetching {symbol} {timeframe}")
    logger.info("=" * 80)
    
    # Load config
    try:
        config_manager = ConfigManager()
        if exchange_name is None:
            exchange_name = config_manager.get_exchange_name()
        if start_date is None:
            if hasattr(config_manager, 'get_historical_start_date'):
                start_date = config_manager.get_historical_start_date()
            else:
                start_date = "2017-01-01"
    except Exception:
        if exchange_name is None:
            exchange_name = "coinbase"
        if start_date is None:
            start_date = "2017-01-01"
        logger.warning("Config not available, using defaults")
    
    end_date = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    logger.info(f"Exchange: {exchange_name}")
    logger.info(f"Symbol: {symbol}")
    logger.info(f"Timeframe: {timeframe}")
    logger.info(f"Start date: {start_date}")
    logger.info(f"End date: {end_date}")
    logger.info("")
    
    # Delete existing cache if force is True
    cache_file = get_cache_path(symbol, timeframe)
    if cache_file.exists():
        if force:
            logger.info(f"Deleting existing cache: {cache_file}")
            delete_cache(symbol, timeframe)
        else:
            logger.warning(f"Cache already exists: {cache_file}")
            logger.warning("Use --force to delete and re-fetch")
            return
    
    # Create exchange and fetch data
    try:
        logger.info("Fetching data...")
        exchange = create_exchange(exchange_name, enable_rate_limit=True)
        
        df, api_requests = fetch_historical(
            exchange, symbol, timeframe, start_date, end_date
        )
        
        if df.empty:
            logger.error("No data returned from exchange")
            return
        
        # Validate and clean
        logger.info("Validating data...")
        validation_result = validate_data(df, timeframe)
        
        if validation_result.get('duplicates', 0) > 0:
            df, _ = remove_duplicates(df)
            logger.info(f"Removed {validation_result['duplicates']} duplicates")
        
        if validation_result.get('gaps'):
            logger.warning(f"Detected {len(validation_result['gaps'])} gaps in data")
        
        # Save to cache
        logger.info("Saving to cache...")
        write_cache(symbol, timeframe, df)
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("Success!")
        logger.info("=" * 80)
        logger.info(f"Candles fetched: {len(df):,}")
        logger.info(f"Date range: {df.index.min()} to {df.index.max()}")
        logger.info(f"API requests: {api_requests}")
        logger.info(f"Cache file: {cache_file}")
        logger.info("=" * 80)
        
    except MarketNotFoundError as e:
        logger.error(f"Market not found: {e}")
        sys.exit(1)
    except FetchError as e:
        logger.error(f"Fetch error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Re-fetch data for a specific market/timeframe'
    )
    parser.add_argument('symbol', help='Trading pair (e.g., BTC/USD)')
    parser.add_argument('timeframe', help='Timeframe (e.g., 1h, 1d)')
    parser.add_argument('--exchange', help='Exchange name (defaults to config)')
    parser.add_argument('--start-date', help='Start date (YYYY-MM-DD, defaults to config)')
    parser.add_argument('--force', action='store_true', 
                       help='Delete existing cache before fetching')
    
    args = parser.parse_args()
    
    refetch_market(
        args.symbol,
        args.timeframe,
        exchange_name=args.exchange,
        start_date=args.start_date,
        force=args.force
    )


if __name__ == '__main__':
    from datetime import timedelta
    main()

