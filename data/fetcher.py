"""
Core CCXT fetching logic for OHLCV data.

This module handles fetching historical data from exchanges
with support for full historical fetches and delta fetches.
"""

import ccxt
import pandas as pd
from typing import Optional, Tuple
from datetime import datetime, timedelta


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


def fetch_historical(exchange: ccxt.Exchange, symbol: str, timeframe: str,
                    start_date: str, end_date: Optional[str] = None) -> Tuple[pd.DataFrame, int]:
    """
    Fetch full historical data from start_date to end_date.
    
    Args:
        exchange: CCXT exchange instance
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
        start_date: Start date string (YYYY-MM-DD) or datetime
        end_date: End date string (YYYY-MM-DD) or datetime. If None, uses today
    
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
    
    while since < end_ts and api_requests < max_iterations:
        ohlcv, requests = fetch_ohlcv_batch(exchange, symbol, timeframe, since, limit=1000)
        
        if not ohlcv:
            # No more data available
            break
        
        all_ohlcv.extend(ohlcv)
        api_requests += requests
        
        # Update since to next candle after the last one
        last_timestamp = ohlcv[-1][0]
        since = last_timestamp + 1
        
        # If we got fewer than limit candles, we've reached the end
        if len(ohlcv) < 1000:
            break
    
    if not all_ohlcv:
        return pd.DataFrame(), api_requests
    
    # Convert to DataFrame
    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df.set_index('datetime', inplace=True)
    df.drop('timestamp', axis=1, inplace=True)
    
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

