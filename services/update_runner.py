"""
Daily delta update service.

This service reads the manifest and updates all markets/timeframes
that need updating with only new candles since last timestamp.
"""

import os
import yaml
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

from data.updater import update_market, MarketNotFoundError
from data.cache_manager import load_manifest, get_manifest_entry, update_manifest, read_cache
from data.fetcher import create_exchange
from data.market_liveliness import check_market_on_exchange, is_liveliness_stale


# Setup logging
LOG_DIR = Path('logs')
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'daily_update.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_exchange_metadata() -> Dict[str, Any]:
    """Load exchange metadata configuration."""
    metadata_path = Path('config/exchange_metadata.yaml')
    if not metadata_path.exists():
        raise FileNotFoundError(f"Exchange metadata not found: {metadata_path}")
    
    with open(metadata_path, 'r') as f:
        return yaml.safe_load(f)


def get_markets_to_update(metadata: Dict[str, Any]) -> List[tuple]:
    """
    Get list of (symbol, timeframe) tuples to update.
    
    Args:
        metadata: Exchange metadata dictionary
    
    Returns:
        List of (symbol, timeframe) tuples
    """
    markets = metadata.get('top_markets', [])
    timeframes = metadata.get('timeframes', [])
    
    combinations = []
    for market in markets:
        for timeframe in timeframes:
            combinations.append((market, timeframe))
    
    return combinations


def log_error(error_file: Path, message: str):
    """Log error to error file."""
    with open(error_file, 'a') as f:
        f.write(f"[{datetime.now().isoformat()}] {message}\n")


def log_validation(validation_file: Path, data: Dict[str, Any]):
    """Log validation issue to validation log."""
    with open(validation_file, 'a') as f:
        f.write(json.dumps(data) + '\n')


def update_exchange_metadata(removed_markets: List[str]):
    """Remove markets from exchange_metadata.yaml."""
    if not removed_markets:
        return
    
    metadata_path = Path('config/exchange_metadata.yaml')
    
    with open(metadata_path, 'r') as f:
        metadata = yaml.safe_load(f)
    
    # Remove markets
    top_markets = metadata.get('top_markets', [])
    metadata['top_markets'] = [m for m in top_markets if m not in removed_markets]
    metadata['last_updated'] = datetime.utcnow().isoformat()
    
    with open(metadata_path, 'w') as f:
        yaml.dump(metadata, f, default_flow_style=False, sort_keys=False)
    
    logger.info(f"Removed {len(removed_markets)} markets from metadata: {removed_markets}")


def check_market_liveliness_lightweight(symbol: str, timeframe: str, 
                                       exchange_name: str, metadata: Dict[str, Any]) -> None:
    """
    Perform lightweight liveliness check if verification date is stale.
    
    Only checks on the primary exchange to minimize API calls.
    Updates manifest with liveliness status.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
        exchange_name: Primary exchange name
        metadata: Exchange metadata dictionary (for cache_days config)
    """
    manifest_entry = get_manifest_entry(symbol, timeframe)
    if not manifest_entry:
        return
    
    # Check if liveliness verification is stale
    verified_date_str = manifest_entry.get('market_verified_date')
    
    # Load cache days from config, default to 30
    try:
        import yaml
        config_path = Path('config/config.yaml')
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            cache_days = config.get('data_quality', {}).get('liveliness_cache_days', 30)
        else:
            cache_days = 30
    except Exception:
        cache_days = 30
    
    if not is_liveliness_stale(verified_date_str, cache_days=cache_days):
        return  # Still fresh, no need to check
    
    # Perform lightweight check on primary exchange only
    try:
        exchange = create_exchange(exchange_name, enable_rate_limit=True)
        market_info = check_market_on_exchange(exchange, symbol, timeframe='1h')
        
        if market_info:
            market_live = market_info['exists']
            market_verified_date = datetime.utcnow().isoformat() + 'Z'
            
            # Update manifest
            df = read_cache(symbol, timeframe)
            if not df.empty:
                update_manifest(
                    symbol, timeframe, df,
                    market_live=market_live,
                    market_verified_date=market_verified_date
                )
                logger.debug(f"Updated liveliness for {symbol} {timeframe}: live={market_live}")
        else:
            # Market not found on primary exchange - mark as potentially delisted
            # (full check across all exchanges happens in quality service)
            market_verified_date = datetime.utcnow().isoformat() + 'Z'
            df = read_cache(symbol, timeframe)
            if not df.empty:
                update_manifest(
                    symbol, timeframe, df,
                    market_live=False,
                    market_verified_date=market_verified_date
                )
                logger.debug(f"Market {symbol} not found on {exchange_name}")
    except Exception as e:
        logger.debug(f"Error checking liveliness for {symbol} {timeframe}: {str(e)}")
        # Don't fail the update if liveliness check fails


def run_update(target_end_date: str = None) -> Dict[str, Any]:
    """
    Run daily update for all markets/timeframes.
    
    Args:
        target_end_date: Target end date (YYYY-MM-DD). If None, uses yesterday
    
    Returns:
        Summary dictionary with results
    """
    start_time = datetime.utcnow()
    
    if target_end_date is None:
        target_end_date = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    logger.info("=" * 80)
    logger.info("Daily Data Update Started")
    logger.info("=" * 80)
    logger.info(f"Target end date: {target_end_date}")
    logger.info("")
    
    # Load metadata
    try:
        metadata = load_exchange_metadata()
        exchange_name = metadata.get('exchange', 'coinbase')
        combinations = get_markets_to_update(metadata)
        
        logger.info(f"Exchange: {exchange_name}")
        logger.info(f"Markets: {len(metadata.get('top_markets', []))}")
        logger.info(f"Timeframes: {len(metadata.get('timeframes', []))}")
        logger.info(f"Total combinations: {len(combinations)}")
        logger.info("-" * 80)
        
    except Exception as e:
        logger.error(f"Failed to load metadata: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'updated': 0,
            'failed': 0,
            'skipped': 0
        }
    
    # Setup log files
    error_file = LOG_DIR / 'fetch_errors.log'
    validation_file = LOG_DIR / 'data_validation.log'
    
    # Track statistics
    updated = 0
    skipped = 0
    failed = 0
    removed_markets = []
    total_candles = 0
    total_api_requests = 0
    warnings = []
    
    # Update each market/timeframe
    for i, (symbol, timeframe) in enumerate(combinations, 1):
        logger.info(f"[{i}/{len(combinations)}] Updating {symbol} {timeframe}...")
        
        try:
            result = update_market(
                exchange_name, symbol, timeframe, 
                target_end_date=target_end_date,
                force_refresh=False
            )
            
            status = result.get('status')
            
            if status == 'success':
                candles_added = result.get('candles_added', 0)
                total_candles += candles_added
                total_api_requests += result.get('api_requests', 0)
                
                if result.get('warnings'):
                    warnings.extend([
                        f"{symbol} {timeframe}: {w}" 
                        for w in result.get('warnings', [])
                    ])
                
                logger.info(f"✓ Added {candles_added} candles")
                updated += 1
                
                # Lightweight liveliness check (only if stale)
                try:
                    check_market_liveliness_lightweight(symbol, timeframe, exchange_name, metadata)
                except Exception as e:
                    logger.debug(f"Liveliness check failed for {symbol} {timeframe}: {str(e)}")
                
            elif status == 'up_to_date':
                logger.info("✓ Up to date")
                skipped += 1
                
                # Lightweight liveliness check (only if stale)
                try:
                    check_market_liveliness_lightweight(symbol, timeframe, exchange_name, metadata)
                except Exception as e:
                    logger.debug(f"Liveliness check failed for {symbol} {timeframe}: {str(e)}")
                
            elif status == 'market_not_found':
                error_msg = result.get('error', 'Market not found')
                logger.info(f"✗ Market not found")
                log_error(error_file, f"{symbol} {timeframe}: {error_msg}")
                removed_markets.append(symbol)
                failed += 1
                
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.info(f"✗ Error: {error_msg[:50]}")
                log_error(error_file, f"{symbol} {timeframe}: {error_msg}")
                failed += 1
        
        except Exception as e:
            logger.info(f"✗ Exception: {str(e)[:50]}")
            log_error(error_file, f"{symbol} {timeframe}: {str(e)}")
            failed += 1
    
    # Remove invalid markets from metadata
    if removed_markets:
        removed_markets = list(set(removed_markets))  # Deduplicate
        update_exchange_metadata(removed_markets)
    
    # Log validation warnings
    if warnings:
        for warning in warnings:
            log_validation(validation_file, {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'type': 'warning',
                'message': warning
            })
    
    # Calculate summary
    duration = (datetime.utcnow() - start_time).total_seconds()
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("Daily Update Summary")
    logger.info("=" * 80)
    logger.info(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
    logger.info(f"Updated: {updated}")
    logger.info(f"Skipped: {skipped}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Total candles added: {total_candles:,}")
    logger.info(f"Total API requests: {total_api_requests:,}")
    if warnings:
        logger.info(f"Warnings: {len(warnings)}")
    logger.info("=" * 80)
    
    # Update metadata last_updated timestamp
    metadata_path = Path('config/exchange_metadata.yaml')
    with open(metadata_path, 'r') as f:
        metadata = yaml.safe_load(f)
    metadata['last_updated'] = datetime.utcnow().isoformat()
    with open(metadata_path, 'w') as f:
        yaml.dump(metadata, f, default_flow_style=False, sort_keys=False)
    
    return {
        'status': 'success',
        'updated': updated,
        'skipped': skipped,
        'failed': failed,
        'total_candles': total_candles,
        'total_api_requests': total_api_requests,
        'warnings': len(warnings),
        'duration_seconds': duration,
        'removed_markets': removed_markets
    }


def main():
    """Main entry point for update runner."""
    import sys
    
    # Allow target date to be passed as command line argument
    target_date = None
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
    
    result = run_update(target_end_date=target_date)
    
    # Exit with error code if there were failures
    if result.get('failed', 0) > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()

