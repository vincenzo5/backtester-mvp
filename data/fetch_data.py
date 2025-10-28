"""
Data fetching module for retrieving historical cryptocurrency data.

This module handles fetching OHLCV data from exchanges via ccxt,
with built-in CSV caching for performance.
"""

import ccxt
import pandas as pd
import os
import time
import yaml


def fetch_historical_data(config, symbol=None, timeframe=None):
    """Fetch historical data from cryptocurrency exchange using ccxt.
    
    Args:
        config (dict): Configuration dictionary containing:
            - exchange: exchange name and settings
            - backtest: start_date and end_date
        symbol (str, optional): Trading pair (e.g., 'BTC/USD'). 
                                 If None, reads from config['exchange']['symbol']
        timeframe (str, optional): Data granularity (e.g., '1h', '1d').
                                    If None, reads from config['exchange']['timeframe']
    
    Returns:
        pandas.DataFrame: Historical OHLCV data with datetime index, or empty DataFrame if cache missing
    """
    start_time = time.time()
    
    # Use provided params or fall back to config
    symbol = symbol or config['exchange'].get('symbol')
    timeframe = timeframe or config['exchange'].get('timeframe')
    start_date = config['backtest']['start_date']
    end_date = config['backtest']['end_date']
    
    # Create cache filename based on config
    cache_file = f"data/cache/{symbol.replace('/', '_')}_{timeframe}_{start_date}_{end_date}.csv"
    
    # Check if cached data exists
    if os.path.exists(cache_file):
        df = pd.read_csv(cache_file, index_col='datetime', parse_dates=True)
        return df
    
    # Cache miss - return empty DataFrame (no fetching allowed during backtests)
    # The caller should handle skipping when cache is missing
    return pd.DataFrame()


def load_exchange_fees(config):
    """Load fees from exchange metadata or config override.
    
    Args:
        config (dict): Configuration dictionary containing trading settings
    
    Returns:
        float: Commission rate to use for backtesting
    """
    trading_config = config.get('trading', {})
    
    # Check if we should use exchange fees
    use_exchange_fees = trading_config.get('use_exchange_fees', False)
    
    if use_exchange_fees:
        try:
            # Load from exchange metadata
            metadata_file = 'config/exchange_metadata.yaml'
            
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r') as f:
                    metadata = yaml.safe_load(f)
                
                fee_type = trading_config.get('fee_type', 'taker')
                fee = metadata['fees'].get(fee_type, 0.006)  # Default taker fee
                
                print(f"Using exchange fee from metadata ({fee_type}): {fee*100:.2f}%")
                return fee
            else:
                print("Warning: exchange_metadata.yaml not found. Run: python scripts/fetch_exchange_info.py")
                print("Falling back to config fees.")
        except Exception as e:
            print(f"Warning: Could not load exchange fees: {e}")
            print("Falling back to config fees.")
    
    # Use hardcoded fees based on fee_type
    fee_type = trading_config.get('fee_type', 'taker')
    
    if fee_type == 'maker':
        fee = trading_config.get('commission_maker', 0.004)  # Default maker fee
        print(f"Using hardcoded maker fee: {fee*100:.2f}%")
    else:
        fee = trading_config.get('commission', 0.006)  # Default taker fee
        print(f"Using hardcoded taker fee: {fee*100:.2f}%")
    
    return fee

