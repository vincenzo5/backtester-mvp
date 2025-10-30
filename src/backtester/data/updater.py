"""
Smart delta update orchestration.

This module coordinates fetching new data and updating caches
with validation and manifest updates.
"""

import pandas as pd
from typing import Tuple, Optional
from datetime import datetime, timedelta

from backtester.data.fetcher import create_exchange, fetch_from_date, MarketNotFoundError, FetchError
from backtester.data.cache_manager import (
    read_cache, write_cache, get_last_cached_timestamp, 
    update_manifest, cache_exists, get_manifest_entry
)
from backtester.data.validator import remove_duplicates, validate_data


def needs_update(symbol: str, timeframe: str, target_end_date: Optional[str] = None) -> Tuple[bool, Optional[pd.Timestamp]]:
    """
    Check if cache needs updating.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
        target_end_date: Target end date (YYYY-MM-DD). If None, uses yesterday
    
    Returns:
        Tuple of (needs_update bool, last_cached_timestamp)
    """
    if not cache_exists(symbol, timeframe):
        return True, None
    
    last_timestamp = get_last_cached_timestamp(symbol, timeframe)
    
    if last_timestamp is None:
        return True, None
    
    # Parse target end date
    if target_end_date is None:
        target_end = datetime.utcnow() - timedelta(days=1)
    else:
        target_end = datetime.strptime(target_end_date, '%Y-%m-%d')
    
    # Handle timezone-aware timestamps
    if last_timestamp.tz is not None:
        # Convert target_end to timezone-aware if timestamp is aware
        from datetime import timezone
        if target_end.tzinfo is None:
            target_end = target_end.replace(tzinfo=timezone.utc)
    
    # Check if cache is up to date (within 1 day of target)
    cache_age = (target_end - last_timestamp).days
    
    # Needs update if cache is more than 1 day old
    needs_update_flag = cache_age > 1
    
    return needs_update_flag, last_timestamp


def fetch_delta(exchange_name: str, symbol: str, timeframe: str,
               from_timestamp: pd.Timestamp, 
               target_end_date: Optional[str] = None) -> Tuple[pd.DataFrame, int]:
    """
    Fetch only new candles since last cached timestamp.
    
    Args:
        exchange_name: Name of exchange (e.g., 'coinbase')
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
        from_timestamp: Last cached timestamp
        target_end_date: Target end date (YYYY-MM-DD). If None, uses yesterday
    
    Returns:
        Tuple of (DataFrame with new data, number of API requests made)
    
    Raises:
        MarketNotFoundError: If market doesn't exist
        FetchError: If fetch fails
    """
    exchange = create_exchange(exchange_name)
    return fetch_from_date(exchange, symbol, timeframe, from_timestamp, target_end_date)


def apply_update(symbol: str, timeframe: str, new_data: pd.DataFrame, 
                validate: bool = True, source_exchange: Optional[str] = None) -> dict:
    """
    Apply delta update to cache with validation.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
        new_data: DataFrame with new OHLCV data
        validate: Whether to validate data before saving
        source_exchange: Exchange name from which data was fetched (optional)
    
    Returns:
        Dictionary with update results
    """
    if new_data.empty:
        return {
            'status': 'no_new_data',
            'candles_added': 0,
            'warnings': []
        }
    
    # If source_exchange not provided, try to get from manifest
    if source_exchange is None:
        manifest_entry = get_manifest_entry(symbol, timeframe)
        if manifest_entry and 'source_exchange' in manifest_entry:
            source_exchange = manifest_entry['source_exchange']
    
    # Validate new data
    validation_result = validate_data(new_data, timeframe) if validate else {'valid': True}
    
    warnings = []
    if not validation_result.get('valid', True):
        warnings.append(f"Data validation issues detected: {validation_result}")
    
    # Read existing cache
    existing_data = read_cache(symbol, timeframe)
    
    if existing_data.empty:
        # No existing data, just write new data
        combined_data = new_data
    else:
        # Combine existing and new data
        combined_data = pd.concat([existing_data, new_data])
        
        # Remove duplicates (in case of overlap)
        combined_data, duplicates_removed = remove_duplicates(combined_data)
        
        if duplicates_removed > 0:
            warnings.append(f"Removed {duplicates_removed} duplicate candles")
        
        # Sort by index
        combined_data = combined_data.sort_index()
    
    # Validate combined data
    final_validation = validate_data(combined_data, timeframe) if validate else {}
    
    if final_validation.get('gaps'):
        warnings.append(f"Detected {len(final_validation['gaps'])} gaps in data")
    
    # Write to cache with source_exchange
    write_cache(symbol, timeframe, combined_data, source_exchange=source_exchange)
    
    candles_added = len(new_data)
    
    return {
        'status': 'success',
        'candles_added': candles_added,
        'total_candles': len(combined_data),
        'warnings': warnings,
        'validation': final_validation
    }


def update_market(exchange_name: str, symbol: str, timeframe: str,
                 target_end_date: Optional[str] = None,
                 force_refresh: bool = False) -> dict:
    """
    Update a single market/timeframe combination.
    
    Uses source_exchange from manifest if available, otherwise uses provided exchange_name.
    If manifest has no source_exchange (legacy), triggers full re-fetch using multi-exchange discovery.
    
    Args:
        exchange_name: Name of exchange to use as fallback (e.g., 'coinbase')
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
        target_end_date: Target end date (YYYY-MM-DD). If None, uses yesterday
        force_refresh: If True, re-fetch from beginning. If False, delta update only
    
    Returns:
        Dictionary with update results
    """
    try:
        # Get source_exchange from manifest if available
        manifest_entry = get_manifest_entry(symbol, timeframe)
        source_exchange = None
        if manifest_entry and 'source_exchange' in manifest_entry:
            source_exchange = manifest_entry['source_exchange']
        
        # If no source_exchange in manifest and force_refresh, trigger multi-exchange discovery
        if force_refresh and source_exchange is None:
            # Import here to avoid circular dependency
            import yaml
            with open('config/markets.yaml', 'r') as f:
                metadata = yaml.safe_load(f)
            exchanges = metadata.get('exchanges', ['coinbase', 'binance', 'kraken'])
            
            from data.exchange_discovery import find_best_exchange
            best_exchange, _ = find_best_exchange(symbol, timeframe, exchanges)
            if best_exchange:
                source_exchange = best_exchange
            else:
                # Fall back to provided exchange_name
                source_exchange = exchange_name
        elif source_exchange is None:
            # Use provided exchange_name as fallback
            source_exchange = exchange_name
        
        # Check if update is needed
        if not force_refresh:
            needs_update_flag, last_timestamp = needs_update(symbol, timeframe, target_end_date)
            
            if not needs_update_flag:
                return {
                    'status': 'up_to_date',
                    'candles_added': 0,
                    'last_timestamp': last_timestamp.isoformat() if last_timestamp else None
                }
        
        # Fetch new data
        if force_refresh or last_timestamp is None:
            # Full historical fetch needed
            from data.fetcher import fetch_historical
            exchange = create_exchange(source_exchange)
            start_date = "2017-01-01"  # Default start
            new_data, api_requests = fetch_historical(
                exchange, symbol, timeframe, start_date, target_end_date,
                source_exchange=source_exchange
            )
        else:
            # Delta fetch using source_exchange
            new_data, api_requests = fetch_delta(
                source_exchange, symbol, timeframe, last_timestamp, target_end_date
            )
        
        # Apply update with source_exchange
        update_result = apply_update(symbol, timeframe, new_data, validate=True, source_exchange=source_exchange)
        update_result['api_requests'] = api_requests
        update_result['source_exchange'] = source_exchange
        
        return update_result
        
    except MarketNotFoundError as e:
        return {
            'status': 'market_not_found',
            'error': str(e),
            'candles_added': 0
        }
    except FetchError as e:
        return {
            'status': 'fetch_error',
            'error': str(e),
            'candles_added': 0
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'candles_added': 0
        }

