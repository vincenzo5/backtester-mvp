"""
Core CCXT fetching logic for OHLCV data.

This module handles fetching historical data from exchanges
with support for full historical fetches and delta fetches.
"""

import ccxt
import pandas as pd
import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def create_exchange(exchange_name: str, enable_rate_limit: bool = True) -> ccxt.Exchange:
    """
    Create and configure exchange instance.
    
    Args:
        exchange_name: Name of exchange (e.g., 'coinbase')
        enable_rate_limit: Enable rate limiting
    
    Returns:
        Configured exchange instance
    """
    exchange_class = getattr(ccxt, exchange_name)
    return exchange_class({'enableRateLimit': enable_rate_limit})


def fetch_ohlcv_batch(exchange: ccxt.Exchange, symbol: str, timeframe: str,
                      since: int, limit: int = 1000) -> Tuple[list, int]:
    """
    Fetch a batch of OHLCV data from exchange.
    
    Args:
        exchange: CCXT exchange instance
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
        since: Starting timestamp in milliseconds
        limit: Maximum number of candles to fetch
    
    Returns:
        Tuple of (list of OHLCV data, number of API requests made)
    """
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since, limit=limit)
        return ohlcv, 1
    except ccxt.ExchangeError as e:
        # Check if it's a "market not found" error
        error_msg = str(e).lower()
        if 'not found' in error_msg or 'invalid symbol' in error_msg:
            raise MarketNotFoundError(f"Market {symbol} not found on {exchange.id}") from e
        raise
    except Exception as e:
        raise FetchError(f"Error fetching data: {str(e)}") from e


def find_earliest_available_date(exchange: ccxt.Exchange, symbol: str, timeframe: str,
                                 target_start_date: datetime, end_date: datetime) -> Optional[datetime]:
    """
    Find the earliest available date for a market by testing year-by-year.
    
    Returns:
        Earliest available date, or None if no data exists
    """
    from datetime import timezone
    
    # Ensure timezone-aware
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=timezone.utc)
    if target_start_date.tzinfo is None:
        target_start_date = target_start_date.replace(tzinfo=timezone.utc)
    
    # Try years from most recent backwards to find first year with data
    earliest_found = None
    for year in range(end_date.year, target_start_date.year - 1, -1):
        test_start = datetime(year, 1, 1, tzinfo=timezone.utc)
        test_start_ts = exchange.parse8601(test_start.strftime('%Y-%m-%dT00:00:00Z'))
        
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=test_start_ts, limit=1)
            if ohlcv and len(ohlcv) > 0:
                earliest_found = pd.to_datetime(ohlcv[0][0], unit='ms', utc=True)
                # Found data in this year - this is likely the earliest we can easily find
                # Return it rather than doing expensive binary search
                logger.debug(f"Found earliest data for {symbol} {timeframe} in {year}: {earliest_found.date()}")
                return earliest_found
        except Exception:
            continue
    
    return earliest_found


def fetch_historical(exchange: ccxt.Exchange, symbol: str, timeframe: str,
                    start_date: str, end_date: Optional[str] = None, 
                    auto_find_earliest: bool = True, source_exchange: Optional[str] = None) -> Tuple[pd.DataFrame, int]:
    """
    Fetch full historical data from start_date to end_date.
    
    If start_date has no data and auto_find_earliest is True, will automatically
    find and use the earliest available date.
    
    Args:
        exchange: CCXT exchange instance
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
        start_date: Start date string (YYYY-MM-DD) or datetime
        end_date: End date string (YYYY-MM-DD) or datetime. If None, uses today
        auto_find_earliest: If True, automatically find earliest available date if start_date has no data
        source_exchange: Exchange name for logging purposes (optional)
    
    Returns:
        Tuple of (DataFrame with OHLCV data, number of API requests made)
    
    Raises:
        MarketNotFoundError: If market doesn't exist on exchange
        FetchError: If fetch fails for other reasons
    """
    # Parse dates
    if isinstance(start_date, str):
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    else:
        start_dt = start_date
    
    if end_date is None:
        end_dt = datetime.utcnow() - timedelta(days=1)  # Use yesterday by default
    elif isinstance(end_date, str):
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    else:
        end_dt = end_date
    
    # Convert to timestamps
    start_ts = exchange.parse8601(start_dt.strftime('%Y-%m-%dT00:00:00Z'))
    end_ts = exchange.parse8601(end_dt.strftime('%Y-%m-%dT23:59:59Z'))
    
    # Fetch data in batches
    since = start_ts
    all_ohlcv = []
    api_requests = 0
    max_iterations = 10000  # Safety limit to prevent infinite loops
    consecutive_empty_batches = 0
    max_consecutive_empty = 3  # Stop after 3 consecutive empty batches
    
    exchange_info = f" from {source_exchange}" if source_exchange else ""
    logger.debug(f"Fetching {symbol} {timeframe}{exchange_info} from {start_dt} to {end_dt} (API requests: {api_requests})")
    
    while since < end_ts and api_requests < max_iterations:
        try:
            ohlcv, requests = fetch_ohlcv_batch(exchange, symbol, timeframe, since, limit=1000)
            
            if not ohlcv:
                # No data in this batch
                consecutive_empty_batches += 1
                logger.debug(f"Empty batch {consecutive_empty_batches}/{max_consecutive_empty} for {symbol} {timeframe} at {pd.to_datetime(since, unit='ms', utc=True)}")
                if consecutive_empty_batches >= max_consecutive_empty:
                    # Stop if we've hit multiple consecutive empty batches
                    logger.info(f"Stopping fetch for {symbol} {timeframe}: {max_consecutive_empty} consecutive empty batches")
                    break
                # Try moving forward a bit to see if there's a gap
                # For daily candles, move forward 1 day; for hourly, 1 hour, etc.
                timeframe_to_hours = {
                    '1m': 1/60, '5m': 5/60, '15m': 15/60, '30m': 30/60,
                    '1h': 1, '2h': 2, '6h': 6, '1d': 24
                }
                hours_per_candle = timeframe_to_hours.get(timeframe, 24)
                since += int(hours_per_candle * 3600 * 1000)  # Convert to milliseconds
                continue
            
            # Reset empty batch counter on successful fetch
            consecutive_empty_batches = 0
            
            all_ohlcv.extend(ohlcv)
            api_requests += requests
            
            # Update since to next candle after the last one
            last_timestamp = ohlcv[-1][0]
            
            # Check if we've reached or passed the end date
            last_dt = pd.to_datetime(last_timestamp, unit='ms', utc=True)
            # Ensure end_dt is timezone-aware for comparison
            from datetime import timezone
            if end_dt.tzinfo is None:
                end_dt_aware = end_dt.replace(tzinfo=timezone.utc)
            else:
                end_dt_aware = end_dt
            
            if last_dt >= end_dt_aware:
                # We've reached or passed the end date - filter out future data
                break
            
            # Move to next batch: start from the next candle
            since = last_timestamp + 1
            
            # Don't break just because we got fewer than 1000 candles
            # Continue fetching until we reach end_date or hit consecutive empty batches
                
        # Note: MarketNotFoundError and FetchError are handled in the outer exception handler below
        except (MarketNotFoundError, FetchError) as e:
            # Re-raise these immediately - don't retry
            raise
        except ccxt.ExchangeError as e:
            # Check if it's a "market not found" error
            error_msg = str(e).lower()
            if 'not have market' in error_msg or 'not found' in error_msg or 'invalid symbol' in error_msg:
                raise MarketNotFoundError(f"Market {symbol} not found on {exchange.id}") from e
            # For other exchange errors, treat as temporary and retry
            consecutive_empty_batches += 1
            if consecutive_empty_batches >= max_consecutive_empty:
                raise FetchError(f"Multiple consecutive exchange errors: {str(e)}") from e
            # Move forward and retry
            timeframe_to_hours = {
                '1m': 1/60, '5m': 5/60, '15m': 15/60, '30m': 30/60,
                '1h': 1, '2h': 2, '6h': 6, '1d': 24
            }
            hours_per_candle = timeframe_to_hours.get(timeframe, 24)
            since += int(hours_per_candle * 3600 * 1000)
            continue
        except Exception as e:
            # For other errors, log and continue to next batch
            # This handles temporary API issues
            consecutive_empty_batches += 1
            if consecutive_empty_batches >= max_consecutive_empty:
                raise FetchError(f"Multiple consecutive fetch errors: {str(e)}") from e
            # Move forward and retry
            timeframe_to_hours = {
                '1m': 1/60, '5m': 5/60, '15m': 15/60, '30m': 30/60,
                '1h': 1, '2h': 2, '6h': 6, '1d': 24
            }
            hours_per_candle = timeframe_to_hours.get(timeframe, 24)
            since += int(hours_per_candle * 3600 * 1000)
            continue
    
    if not all_ohlcv:
        # If we got no data and auto_find_earliest is enabled, try to find earliest available date
        if auto_find_earliest:
            logger.info(f"No data found for {symbol} {timeframe} from {start_date}. Searching for earliest available date...")
            earliest_date = find_earliest_available_date(exchange, symbol, timeframe, start_dt, end_dt)
            if earliest_date:
                logger.info(f"Found earliest available date: {earliest_date.date()}. Fetching from that date...")
                # Retry fetch from earliest available date
                earliest_str = earliest_date.strftime('%Y-%m-%d')
                return fetch_historical(exchange, symbol, timeframe, earliest_str, end_date, auto_find_earliest=False)
            else:
                logger.warning(f"No data available for {symbol} {timeframe} at any date")
        else:
            logger.warning(f"No data fetched for {symbol} {timeframe} from {start_date} to {end_date}")
        return pd.DataFrame(), api_requests
    
    logger.debug(f"Fetched {len(all_ohlcv)} total candles for {symbol} {timeframe} in {api_requests} API requests")
    
    # Convert to DataFrame
    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df = df.set_index('datetime')
    df = df.drop('timestamp', axis=1)
    
    # Remove duplicates and sort
    df = df[~df.index.duplicated(keep='last')]
    df = df.sort_index()
    
    # Filter to requested date range
    # Ensure timezone-aware comparison
    if df.index.tz is not None:
        # DataFrame is timezone-aware, convert start/end to UTC
        from datetime import timezone
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
    else:
        # DataFrame is timezone-naive, ensure dates are naive too
        if start_dt.tzinfo is not None:
            start_dt = start_dt.replace(tzinfo=None)
        if end_dt.tzinfo is not None:
            end_dt = end_dt.replace(tzinfo=None)
    
    df = df[(df.index >= start_dt) & (df.index <= end_dt)]
    
    return df, api_requests


def fetch_from_date(exchange: ccxt.Exchange, symbol: str, timeframe: str,
                   from_timestamp: pd.Timestamp, end_date: Optional[str] = None) -> Tuple[pd.DataFrame, int]:
    """
    Fetch data from a specific timestamp to end_date.
    
    Args:
        exchange: CCXT exchange instance
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
        from_timestamp: Starting timestamp (will fetch from next candle)
        end_date: End date string (YYYY-MM-DD) or datetime. If None, uses today
    
    Returns:
        Tuple of (DataFrame with OHLCV data, number of API requests made)
    """
    # Calculate next candle start time
    if isinstance(from_timestamp, pd.Timestamp):
        from_dt = from_timestamp.to_pydatetime()
    else:
        from_dt = from_timestamp
    
    # Add 1 minute to ensure we get the next candle (not the last one we already have)
    from_dt = from_dt + timedelta(minutes=1)
    
    start_date_str = from_dt.strftime('%Y-%m-%d')
    
    return fetch_historical(exchange, symbol, timeframe, start_date_str, end_date)


class MarketNotFoundError(Exception):
    """Raised when a market doesn't exist on the exchange."""
    pass


class FetchError(Exception):
    """Raised when data fetch fails."""
    pass

