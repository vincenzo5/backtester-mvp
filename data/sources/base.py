"""
Base class for third-party data source providers.

This module defines the abstract interface that all data source providers must implement.
Data sources provide non-OHLCV data (e.g., on-chain metrics, sentiment, news) that can
be used in backtests.

Quick Start:
    from data.sources.base import DataSourceProvider
    from abc import abstractmethod
    import pandas as pd
    
    class MyDataSource(DataSourceProvider):
        def fetch(self, symbol, start_date, end_date):
            # Fetch your data from API/file
            return pd.DataFrame({
                'datetime': pd.date_range(start_date, end_date, freq='D'),
                'metric': [...],
            })
        
        def get_column_names(self):
            return ['metric']
    
    provider = MyDataSource()
    raw_data = provider.fetch('BTC/USD', '2024-01-01', '2024-01-31')
    aligned = provider.align_to_ohlcv(raw_data, ohlcv_df)

Common Patterns:
    # Pattern 1: Fetching data from an external API
    class APIDataSource(DataSourceProvider):
        def __init__(self, api_key):
            self.api_key = api_key
        
        def fetch(self, symbol, start_date, end_date):
            import requests
            # Call your API
            response = requests.get(f"https://api.example.com/data", ...)
            return pd.DataFrame(response.json())
        
        def get_column_names(self):
            return ['external_metric']
    
    # Pattern 2: Reading from a file or database
    class FileDataSource(DataSourceProvider):
        def __init__(self, file_path):
            self.file_path = file_path
        
        def fetch(self, symbol, start_date, end_date):
            df = pd.read_csv(self.file_path)
            # Filter by symbol and date range
            return df[(df['symbol'] == symbol) & 
                     (df['date'] >= start_date) & 
                     (df['date'] <= end_date)]
        
        def get_column_names(self):
            return ['file_metric']
    
    # Pattern 3: Using aligned data in backtest
    provider = MyDataSource()
    raw_data = provider.fetch('BTC/USD', start, end)
    
    # Align to your OHLCV timeframe (e.g., hourly)
    aligned_data = provider.align_to_ohlcv(raw_data, ohlcv_df)
    
    # aligned_data now has same index as ohlcv_df
    # Can merge with ohlcv_df for backtesting

Extending:
    To create a new data source provider:
    1. Inherit from DataSourceProvider
    2. Implement fetch() method (required)
    3. Implement get_column_names() method (required)
    4. Optionally override align_to_ohlcv() for custom alignment logic
    
    Your fetch() method should return a DataFrame with:
    - datetime index (DatetimeIndex)
    - One or more metric columns
    - Column names should match what get_column_names() returns
    
    Example:
        class SentimentDataSource(DataSourceProvider):
            def fetch(self, symbol, start_date, end_date):
                # Fetch sentiment scores
                return pd.DataFrame({
                    'datetime': [...],
                    'sentiment_score': [...],
                    'tweet_volume': [...],
                }).set_index('datetime')
            
            def get_column_names(self):
                return ['sentiment_score', 'tweet_volume']
"""

from abc import ABC, abstractmethod
from typing import List
import pandas as pd
from datetime import datetime


class DataSourceProvider(ABC):
    """
    Abstract base class for third-party data source providers.
    
    Data source providers fetch non-OHLCV data (on-chain metrics, sentiment, etc.)
    and align it to OHLCV timeframes for use in backtests.
    
    All providers must implement:
    - fetch(): Get raw data from source
    - get_column_names(): Declare what columns this source provides
    
    The default align_to_ohlcv() uses forward-fill to align data, but can be overridden.
    """
    
    @abstractmethod
    def fetch(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch raw data from the data source.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USD')
            start_date: Start date string (YYYY-MM-DD format)
            end_date: End date string (YYYY-MM-DD format)
        
        Returns:
            DataFrame with:
            - datetime index (DatetimeIndex)
            - One or more metric columns (matching get_column_names())
            - All columns must be numeric
        
        Example:
            df = provider.fetch('BTC/USD', '2024-01-01', '2024-01-31')
            # df.index: DatetimeIndex
            # df.columns: ['metric1', 'metric2', ...]
        """
        pass
    
    @abstractmethod
    def get_column_names(self) -> List[str]:
        """
        Return list of column names this provider will add to the DataFrame.
        
        These column names will be prefixed with the provider's identifier
        when added to the OHLCV DataFrame to avoid naming conflicts.
        
        Returns:
            List of column name strings
        
        Example:
            return ['active_addresses', 'transaction_count']
            # Will become: 'onchain_active_addresses', 'onchain_transaction_count'
        """
        pass
    
    def align_to_ohlcv(self, source_df: pd.DataFrame, ohlcv_df: pd.DataFrame, 
                       prefix: str = '') -> pd.DataFrame:
        """
        Align source data to OHLCV DataFrame's timeframe.
        
        This method handles data alignment when source data has different
        frequency than OHLCV data (e.g., daily on-chain data -> hourly candles).
        Default behavior: forward-fill (carry last known value forward).
        
        Args:
            source_df: Raw data from fetch() method
            ohlcv_df: OHLCV DataFrame with target timeframe
            prefix: Prefix to add to column names (e.g., 'onchain_')
        
        Returns:
            DataFrame with same index as ohlcv_df and aligned columns
        
        Algorithm:
            1. Reindex source_df to ohlcv_df.index
            2. Forward-fill missing values (carry last known value forward)
            3. Back-fill initial missing values (if source starts after ohlcv)
            4. Add prefix to column names
        
        Example:
            # Daily on-chain data aligned to hourly OHLCV
            daily_data = provider.fetch('BTC/USD', start, end)  # Daily frequency
            hourly_ohlcv = load_hourly_data()  # Hourly candles
            
            aligned = provider.align_to_ohlcv(daily_data, hourly_ohlcv, 'onchain_')
            # aligned has hourly index matching hourly_ohlcv
            # Each hourly candle gets the day's on-chain value
        """
        if source_df.empty:
            # Return empty DataFrame with correct structure
            columns = [f"{prefix}{col}" for col in self.get_column_names()]
            return pd.DataFrame(index=ohlcv_df.index, columns=columns)
        
        # Ensure both have datetime index
        if not isinstance(source_df.index, pd.DatetimeIndex):
            raise ValueError("source_df must have DatetimeIndex")
        if not isinstance(ohlcv_df.index, pd.DatetimeIndex):
            raise ValueError("ohlcv_df must have DatetimeIndex")
        
        # Select only the columns that this provider is responsible for
        expected_cols = self.get_column_names()
        available_cols = [col for col in expected_cols if col in source_df.columns]
        
        if not available_cols:
            # No matching columns found
            columns = [f"{prefix}{col}" for col in expected_cols]
            return pd.DataFrame(index=ohlcv_df.index, columns=columns)
        
        # Select relevant columns
        source_subset = source_df[available_cols].copy()
        
        # Reindex to OHLCV timeframe
        aligned = source_subset.reindex(ohlcv_df.index)
        
        # Forward-fill to carry last known value forward
        # This handles cases where source data is lower frequency (e.g., daily -> hourly)
        aligned = aligned.ffill()
        
        # Back-fill initial NaN values (if source starts after OHLCV)
        aligned = aligned.bfill()
        
        # Fill any remaining NaN with 0 (shouldn't happen, but safety)
        aligned = aligned.fillna(0)
        
        # Add prefix to column names
        if prefix:
            aligned.columns = [f"{prefix}{col}" for col in aligned.columns]
        
        return aligned
    
    def get_provider_name(self) -> str:
        """
        Return a unique name/identifier for this provider.
        
        Used for prefixing columns when multiple providers are used.
        Default: class name in lowercase.
        
        Returns:
            String identifier
        
        Example:
            return 'onchain'  # Columns become: onchain_active_addresses
        """
        return self.__class__.__name__.lower().replace('provider', '').replace('datasource', '')
