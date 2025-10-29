"""
Gap filling module.

This module handles filling gaps in cached OHLCV data by fetching
missing date ranges from exchanges.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import pandas as pd

from data.fetcher import create_exchange, fetch_historical
from data.fetcher import MarketNotFoundError, FetchError
from data.cache_manager import read_cache, update_manifest, get_manifest_entry
from data.validator import detect_gaps
from data.updater import apply_update

logger = logging.getLogger(__name__)


def fill_gap(symbol: str, timeframe: str, gap_start: datetime, gap_end: datetime,
            source_exchange: str) -> Dict[str, Any]:
    """
    Fill a specific gap in cached data.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
        gap_start: Start of gap (datetime)
        gap_end: End of gap (datetime)
        source_exchange: Exchange name to fetch from
    
    Returns:
        Dictionary with fill results:
        {
            'status': 'success' | 'failed' | 'no_data',
            'candles_added': int,
            'error': str (if failed)
        }
    """
    try:
        # Fetch data for gap range
        start_date_str = gap_start.strftime('%Y-%m-%d')
        end_date_str = gap_end.strftime('%Y-%m-%d')
        
        logger.info(f"Filling gap for {symbol} {timeframe}: {start_date_str} to {end_date_str}")
        
        exchange = create_exchange(source_exchange, enable_rate_limit=True)
        gap_data, api_requests = fetch_historical(
            exchange, symbol, timeframe, 
            start_date_str, end_date_str,
            source_exchange=source_exchange
        )
        
        if gap_data.empty:
            return {
                'status': 'no_data',
                'candles_added': 0,
                'error': f'No data available for gap range {start_date_str} to {end_date_str}'
            }
        
        # Merge with existing cache
        result = apply_update(symbol, timeframe, gap_data, validate=True, source_exchange=source_exchange)
        
        if result.get('status') == 'success':
            candles_added = result.get('candles_added', 0)
            logger.info(f"✓ Filled gap: added {candles_added} candles")
            return {
                'status': 'success',
                'candles_added': candles_added,
                'api_requests': api_requests
            }
        else:
            return {
                'status': 'failed',
                'candles_added': 0,
                'error': f"Merge failed: {result.get('warnings', ['Unknown error'])}"
            }
    
    except MarketNotFoundError as e:
        logger.warning(f"Market {symbol} not found on {source_exchange} for gap fill")
        return {
            'status': 'failed',
            'candles_added': 0,
            'error': f'Market not found: {str(e)}'
        }
    except FetchError as e:
        logger.warning(f"Fetch error for {symbol} {timeframe}: {str(e)}")
        return {
            'status': 'failed',
            'candles_added': 0,
            'error': f'Fetch error: {str(e)}'
        }
    except Exception as e:
        logger.error(f"Error filling gap for {symbol} {timeframe}: {str(e)}", exc_info=True)
        return {
            'status': 'failed',
            'candles_added': 0,
            'error': f'Unexpected error: {str(e)}'
        }


def fill_all_gaps(symbol: str, timeframe: str, source_exchange: str,
                 fallback_exchanges: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Detect and fill all gaps for a dataset.
    
    Gaps are sorted by size (largest first) for priority filling.
    Uses primary exchange first, falls back to other exchanges if needed.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
        source_exchange: Primary exchange name
        fallback_exchanges: List of fallback exchange names (optional)
    
    Returns:
        Dictionary with fill summary:
        {
            'status': 'success' | 'partial' | 'failed',
            'gaps_found': int,
            'gaps_filled': int,
            'total_candles_added': int,
            'failed_gaps': list
        }
    """
    # Load cached data
    df = read_cache(symbol, timeframe)
    
    if df.empty:
        return {
            'status': 'no_data',
            'gaps_found': 0,
            'gaps_filled': 0,
            'total_candles_added': 0,
            'failed_gaps': []
        }
    
    # Detect all gaps
    gaps = detect_gaps(df, timeframe)
    
    if not gaps:
        return {
            'status': 'success',
            'gaps_found': 0,
            'gaps_filled': 0,
            'total_candles_added': 0,
            'failed_gaps': []
        }
    
    logger.info(f"Found {len(gaps)} gap(s) for {symbol} {timeframe}")
    
    # Sort gaps by size (largest first) - duration_seconds
    gaps_sorted = sorted(gaps, key=lambda x: x['duration_seconds'], reverse=True)
    
    gaps_filled = 0
    total_candles_added = 0
    failed_gaps = []
    
    for i, gap in enumerate(gaps_sorted, 1):
        gap_start = pd.to_datetime(gap['start'])
        gap_end = pd.to_datetime(gap['end'])
        
        logger.info(f"[{i}/{len(gaps_sorted)}] Filling gap: {gap_start.date()} to {gap_end.date()} "
                   f"({gap['missing_candles']} missing candles)")
        
        # Try primary exchange first
        result = fill_gap(symbol, timeframe, gap_start, gap_end, source_exchange)
        
        if result['status'] == 'success':
            gaps_filled += 1
            total_candles_added += result.get('candles_added', 0)
        elif fallback_exchanges:
            # Try fallback exchanges
            filled = False
            for fallback_exchange in fallback_exchanges:
                if fallback_exchange == source_exchange:
                    continue  # Skip if same as primary
                
                logger.info(f"Trying fallback exchange: {fallback_exchange}")
                result = fill_gap(symbol, timeframe, gap_start, gap_end, fallback_exchange)
                
                if result['status'] == 'success':
                    gaps_filled += 1
                    total_candles_added += result.get('candles_added', 0)
                    filled = True
                    break
            
            if not filled:
                logger.warning(f"Failed to fill gap: {gap_start.date()} to {gap_end.date()}")
                failed_gaps.append({
                    'gap': gap,
                    'error': result.get('error', 'All exchanges failed')
                })
        else:
            logger.warning(f"Failed to fill gap: {gap_start.date()} to {gap_end.date()}")
            failed_gaps.append({
                'gap': gap,
                'error': result.get('error', 'Fill failed')
            })
        
        # Re-read cache after each gap fill to get updated data for next gap detection
        df = read_cache(symbol, timeframe)
    
    # Determine overall status
    if gaps_filled == len(gaps_sorted):
        status = 'success'
    elif gaps_filled > 0:
        status = 'partial'
    else:
        status = 'failed'
    
    logger.info(f"Gap filling complete: {gaps_filled}/{len(gaps_sorted)} gaps filled, "
               f"{total_candles_added} candles added")
    
    return {
        'status': status,
        'gaps_found': len(gaps_sorted),
        'gaps_filled': gaps_filled,
        'total_candles_added': total_candles_added,
        'failed_gaps': failed_gaps
    }

