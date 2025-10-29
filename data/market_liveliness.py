"""
Market liveliness detection module.

This module checks if markets are still trading on exchanges accessible through CCXT.
"""

import ccxt
import pandas as pd
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from data.fetcher import create_exchange, MarketNotFoundError

logger = logging.getLogger(__name__)


def check_market_on_exchange(exchange: ccxt.Exchange, symbol: str, timeframe: str = '1h') -> Optional[Dict[str, Any]]:
    """
    Check if a market exists on a specific exchange and get latest data timestamp.
    
    Args:
        exchange: CCXT exchange instance
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Timeframe to test (default: '1h')
    
    Returns:
        Dictionary with market info if found, None otherwise:
        {
            'exists': bool,
            'latest_timestamp': datetime,
            'exchange_id': str
        }
    """
    try:
        # Try to fetch the most recent candle
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=1)
        
        if ohlcv and len(ohlcv) > 0:
            latest_timestamp = pd.to_datetime(ohlcv[0][0], unit='ms', utc=True)
            return {
                'exists': True,
                'latest_timestamp': latest_timestamp,
                'exchange_id': exchange.id
            }
        else:
            return None
    except MarketNotFoundError:
        return None
    except ccxt.ExchangeError as e:
        error_msg = str(e).lower()
        if 'not found' in error_msg or 'not have market' in error_msg or 'invalid symbol' in error_msg:
            return None
        # Other exchange errors might be temporary, log but return None
        logger.debug(f"Exchange error checking {symbol} on {exchange.id}: {str(e)[:50]}")
        return None
    except Exception as e:
        # Network or other temporary errors
        logger.debug(f"Error checking {symbol} on {exchange.id}: {str(e)[:50]}")
        return None


def check_all_exchanges(symbol: str, exchange_list: List[str], timeframe: str = '1h') -> Dict[str, Any]:
    """
    Check if market exists on any exchange in the provided list.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        exchange_list: List of exchange names to check (e.g., ['coinbase', 'binance', 'kraken'])
        timeframe: Timeframe to test (default: '1h')
    
    Returns:
        Dictionary with:
        {
            'live': bool,
            'exchanges': [list of exchange names where market was found],
            'latest_timestamp': datetime (most recent across all exchanges),
            'verified_date': datetime (when check was performed),
            'delisted': bool (True if not found on any exchange)
        }
    """
    verified_date = datetime.now(timezone.utc)
    found_exchanges = []
    latest_timestamp = None
    
    logger.debug(f"Checking {symbol} on {len(exchange_list)} exchanges: {exchange_list}")
    
    for exchange_name in exchange_list:
        try:
            exchange = create_exchange(exchange_name, enable_rate_limit=True)
            logger.debug(f"Testing {exchange_name} for {symbol} {timeframe}...")
            
            market_info = check_market_on_exchange(exchange, symbol, timeframe)
            
            if market_info and market_info['exists']:
                found_exchanges.append(exchange_name)
                if latest_timestamp is None or market_info['latest_timestamp'] > latest_timestamp:
                    latest_timestamp = market_info['latest_timestamp']
                logger.debug(f"{exchange_name} has data for {symbol} - latest: {market_info['latest_timestamp']}")
        
        except Exception as e:
            logger.warning(f"Error testing {exchange_name} for {symbol} {timeframe}: {str(e)[:50]}")
            continue
    
    is_live = len(found_exchanges) > 0
    delisted = not is_live
    
    result = {
        'live': is_live,
        'exchanges': found_exchanges,
        'verified_date': verified_date.isoformat() + 'Z',
        'delisted': delisted
    }
    
    if latest_timestamp:
        result['latest_timestamp'] = latest_timestamp.isoformat()
    
    if is_live:
        logger.info(f"{symbol} is live on {len(found_exchanges)} exchange(s): {found_exchanges}")
    else:
        logger.info(f"{symbol} not found on any exchange - likely delisted")
    
    return result


def check_market_live(symbol: str, exchanges: List[str], timeframe: str = '1h') -> Dict[str, Any]:
    """
    Check if market is live on any exchange.
    
    Convenience wrapper around check_all_exchanges with consistent return format.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        exchanges: List of exchange names to check
        timeframe: Timeframe to test (default: '1h')
    
    Returns:
        Dictionary with market status:
        {
            'live': bool,
            'exchanges': [list],
            'latest_timestamp': datetime (ISO format string),
            'verified_date': datetime (ISO format string),
            'delisted': bool
        }
    """
    return check_all_exchanges(symbol, exchanges, timeframe)


def is_liveliness_stale(verified_date_str: Optional[str], cache_days: int = 30) -> bool:
    """
    Check if liveliness verification date is stale and needs re-checking.
    
    Args:
        verified_date_str: ISO format datetime string from manifest
        cache_days: Number of days to cache liveliness checks (default: 30)
    
    Returns:
        True if stale (needs re-check), False if still fresh
    """
    if verified_date_str is None:
        return True  # Never checked, needs checking
    
    try:
        verified_date = pd.to_datetime(verified_date_str)
        now = datetime.now(timezone.utc)
        
        if verified_date.tzinfo is None:
            # Assume UTC if no timezone
            verified_date = verified_date.replace(tzinfo=timezone.utc)
        
        days_since_check = (now - verified_date).days
        return days_since_check >= cache_days
    except Exception:
        # If we can't parse the date, consider it stale
        return True

