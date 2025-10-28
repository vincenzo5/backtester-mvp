"""
Data fetching module for retrieving historical cryptocurrency data.

This module handles fetching OHLCV data from exchanges via ccxt,
with built-in CSV caching for performance.
"""

import pandas as pd
import os
import time


def fetch_historical_data(config_manager, symbol=None, timeframe=None):
    """Fetch historical data from cryptocurrency exchange using ccxt.
    
    Args:
        config_manager: ConfigManager instance
        symbol (str, optional): Trading pair (e.g., 'BTC/USD'). 
                                 If None, must be provided via parameter
        timeframe (str, optional): Data granularity (e.g., '1h', '1d').
                                    If None, must be provided via parameter
    
    Returns:
        pandas.DataFrame: Historical OHLCV data with datetime index, or empty DataFrame if cache missing
    """
    start_time = time.time()
    
    # Get dates from config manager
    start_date = config_manager.get_start_date()
    end_date = config_manager.get_end_date()
    
    # Create cache filename based on config
    cache_file = f"data/cache/{symbol.replace('/', '_')}_{timeframe}_{start_date}_{end_date}.csv"
    
    # Check if cached data exists
    if os.path.exists(cache_file):
        df = pd.read_csv(cache_file, index_col='datetime', parse_dates=True)
        return df
    
    # Cache miss - return empty DataFrame (no fetching allowed during backtests)
    # The caller should handle skipping when cache is missing
    return pd.DataFrame()

