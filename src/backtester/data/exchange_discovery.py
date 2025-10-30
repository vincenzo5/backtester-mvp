"""
Exchange discovery module for finding the exchange with the most historical data.

This module tests multiple exchanges to find which one has data going back
the furthest in time for a given market and timeframe.
"""

import ccxt
import pandas as pd
import logging
from typing import Optional, Tuple, List
from datetime import datetime, timezone

from backtester.data.fetcher import create_exchange, MarketNotFoundError

logger = logging.getLogger(__name__)


def get_earliest_date(exchange: ccxt.Exchange, symbol: str, timeframe: str) -> Optional[datetime]:
    """
    Find the earliest available date for a market on a specific exchange.
    
    Uses year-by-year sampling to efficiently find when data starts.
    
    Args:
        exchange: CCXT exchange instance
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
    
    Returns:
        Earliest available date, or None if no data exists or market not found
    """
    end_date = datetime.now(timezone.utc)
    target_start_date = datetime(2010, 1, 1, tzinfo=timezone.utc)  # Start from 2010
    
    # Try years from most recent backwards to find first year with data
    earliest_found = None
    for year in range(end_date.year, target_start_date.year - 1, -1):
        test_start = datetime(year, 1, 1, tzinfo=timezone.utc)
        test_start_ts = exchange.parse8601(test_start.strftime('%Y-%m-%dT00:00:00Z'))
        
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=test_start_ts, limit=1)
            if ohlcv and len(ohlcv) > 0:
                earliest_found = pd.to_datetime(ohlcv[0][0], unit='ms', utc=True)
                # Found data in this year - return this as earliest
                logger.debug(f"Found earliest data for {symbol} {timeframe} on {exchange.id} in {year}: {earliest_found.date()}")
                return earliest_found
        except (MarketNotFoundError, ccxt.ExchangeError) as e:
            # Market doesn't exist on this exchange, return None
            error_msg = str(e).lower()
            if 'not found' in error_msg or 'not have market' in error_msg or 'invalid symbol' in error_msg:
                logger.debug(f"Market {symbol} not found on {exchange.id}")
                return None
            # For other exchange errors, continue trying
            continue
        except Exception:
            # Network or other temporary errors, continue trying
            continue
    
    return earliest_found


def find_best_exchange(symbol: str, timeframe: str, exchanges: List[str]) -> Tuple[Optional[str], Optional[datetime]]:
    """
    Find the exchange with the most historical data for a given market/timeframe.
    
    Tests each exchange in the provided list and returns the one with the earliest
    available data date. If multiple exchanges have the same earliest date, returns
    the first one found (prioritizing order in the exchanges list).
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
        exchanges: List of exchange names to test (e.g., ['coinbase', 'binance', 'kraken'])
    
    Returns:
        Tuple of (exchange_name, earliest_date) or (None, None) if no exchange has data
    """
    best_exchange = None
    earliest_date = None
    
    logger.info(f"Finding best exchange for {symbol} {timeframe} among {exchanges}")
    
    for exchange_name in exchanges:
        try:
            exchange = create_exchange(exchange_name, enable_rate_limit=True)
            logger.debug(f"Testing {exchange_name} for {symbol} {timeframe}...")
            
            date = get_earliest_date(exchange, symbol, timeframe)
            
            if date is None:
                logger.debug(f"{exchange_name} has no data for {symbol} {timeframe}")
                continue
            
            # Check if this exchange has earlier data than current best
            if earliest_date is None or date < earliest_date:
                best_exchange = exchange_name
                earliest_date = date
                logger.debug(f"{exchange_name} has data from {date.date()} - new best so far")
        
        except Exception as e:
            logger.warning(f"Error testing {exchange_name} for {symbol} {timeframe}: {str(e)}")
            continue
    
    if best_exchange:
        logger.info(f"Best exchange for {symbol} {timeframe}: {best_exchange} (data from {earliest_date.date()})")
    else:
        logger.warning(f"No exchange found with data for {symbol} {timeframe}")
    
    return best_exchange, earliest_date

