"""
Mock On-Chain Metrics Data Source Provider.

This module provides a mock implementation of on-chain metrics data (e.g., active addresses,
transaction counts) for demonstration and testing purposes. It generates synthetic data
that follows realistic patterns but doesn't require actual blockchain API access.

Quick Start:
    from data.sources.onchain import MockOnChainProvider
    
    # Create provider
    provider = MockOnChainProvider()
    
    # Fetch mock data
    df = provider.fetch('BTC/USD', '2024-01-01', '2024-01-31')
    print(df.head())
    # Output: daily on-chain metrics (active_addresses, tx_count)
    
    # Align to OHLCV timeframe
    ohlcv_df = load_hourly_data()  # Your hourly OHLCV DataFrame
    aligned = provider.align_to_ohlcv(df, ohlcv_df, prefix='onchain_')
    # aligned now has hourly frequency with forward-filled daily values

Common Patterns:
    # Pattern 1: Using in backtest preparation
    from data.sources.onchain import MockOnChainProvider
    
    provider = MockOnChainProvider()
    ohlcv_df = load_ohlcv_data()
    
    # Fetch on-chain data for date range matching OHLCV
    start_date = ohlcv_df.index[0].strftime('%Y-%m-%d')
    end_date = ohlcv_df.index[-1].strftime('%Y-%m-%d')
    
    raw_data = provider.fetch('BTC/USD', start_date, end_date)
    aligned_data = provider.align_to_ohlcv(raw_data, ohlcv_df, prefix='onchain_')
    
    # Merge with OHLCV
    enriched_df = ohlcv_df.join(aligned_data)
    # enriched_df now has: open, high, low, close, volume, onchain_active_addresses, onchain_tx_count
    
    # Pattern 2: Realistic data generation patterns
    # The mock provider generates data that:
    # - Correlates with price movements (higher price = more active addresses)
    # - Has realistic daily patterns (higher on weekdays)
    # - Includes noise and variance
    
    provider = MockOnChainProvider(
        base_active_addresses=1000000,  # Base level
        volatility=0.1  # 10% daily variance
    )
    df = provider.fetch('BTC/USD', '2024-01-01', '2024-12-31')
    
    # Pattern 3: Multiple providers for different metrics
    from data.sources.onchain import MockOnChainProvider
    # (In future: SentimentProvider, NewsProvider, etc.)
    
    ohlcv_df = load_data()
    
    # Fetch from multiple sources
    onchain = MockOnChainProvider()
    onchain_data = onchain.align_to_ohlcv(
        onchain.fetch('BTC/USD', start, end),
        ohlcv_df,
        prefix='onchain_'
    )
    
    # Combine all
    enriched = ohlcv_df.join(onchain_data)  # ... and other sources

Extending:
    To replace mock with real on-chain API:
    1. Inherit from MockOnChainProvider or implement DataSourceProvider directly
    2. Override fetch() to call your blockchain API (e.g., Glassnode, CryptoQuant)
    3. Keep get_column_names() returning ['active_addresses', 'tx_count']
    4. align_to_ohlcv() should work unchanged (forward-fill is appropriate for daily -> hourly)
    
    Example:
        class GlassnodeOnChainProvider(DataSourceProvider):
            def __init__(self, api_key):
                self.api_key = api_key
            
            def fetch(self, symbol, start_date, end_date):
                import requests
                # Call Glassnode API
                response = requests.get(
                    'https://api.glassnode.com/v1/metrics/addresses/active_count',
                    params={
                        'a': symbol.split('/')[0],  # BTC
                        's': start_date,
                        'u': end_date,
                        'api_key': self.api_key
                    }
                )
                # Parse and return DataFrame
                return pd.DataFrame(response.json()).set_index('datetime')
            
            def get_column_names(self):
                return ['active_addresses']
"""

from typing import List
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from backtester.data.sources.base import DataSourceProvider


class MockOnChainProvider(DataSourceProvider):
    """
    Mock on-chain metrics data provider.
    
    Generates synthetic on-chain data (active addresses, transaction counts)
    that follows realistic patterns. Useful for development and testing
    before integrating real blockchain APIs.
    
    Attributes:
        base_active_addresses: Base level of active addresses (default: 1,000,000)
        base_tx_count: Base transaction count per day (default: 300,000)
        volatility: Daily volatility factor (default: 0.15 = 15%)
        correlation_factor: How much metrics correlate with price (0-1, default: 0.3)
    """
    
    def __init__(self, base_active_addresses: int = 1000000, 
                 base_tx_count: int = 300000, 
                 volatility: float = 0.15,
                 correlation_factor: float = 0.3):
        """
        Initialize mock on-chain provider.
        
        Args:
            base_active_addresses: Base daily active addresses
            base_tx_count: Base daily transaction count
            volatility: Daily volatility (0-1), higher = more variance
            correlation_factor: Correlation with price movements (0-1)
        """
        self.base_active_addresses = base_active_addresses
        self.base_tx_count = base_tx_count
        self.volatility = volatility
        self.correlation_factor = correlation_factor
    
    def fetch(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Generate mock on-chain data for the specified date range.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USD') - used for consistency
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            DataFrame with daily on-chain metrics:
            - datetime index
            - active_addresses: Daily active addresses
            - tx_count: Daily transaction count
        
        Data Generation:
            - Daily frequency
            - Correlated with price trends (if price data available)
            - Higher activity on weekdays
            - Realistic variance and noise
        """
        # Parse dates
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        # Generate daily date range
        date_range = pd.date_range(start=start_dt, end=end_dt, freq='D')
        
        if len(date_range) == 0:
            return pd.DataFrame(columns=['active_addresses', 'tx_count'])
        
        # Generate base trends with some correlation to typical market cycles
        # (in real implementation, this would correlate with actual price data)
        n_days = len(date_range)
        
        # Create a trend that simulates market cycles
        trend = np.sin(np.linspace(0, 4 * np.pi, n_days)) * 0.2 + 1.0
        
        # Add weekday effect (higher activity on weekdays)
        weekday_factor = np.array([1.2 if pd.Timestamp(d).weekday() < 5 else 0.8 for d in date_range])
        
        # Generate random noise
        np.random.seed(42)  # For reproducibility
        noise = np.random.normal(1.0, self.volatility, n_days)
        
        # Combine factors
        combined_factor = trend * weekday_factor * noise
        
        # Generate active addresses
        active_addresses = (self.base_active_addresses * combined_factor).astype(int)
        active_addresses = np.maximum(active_addresses, self.base_active_addresses * 0.5)  # Floor
        
        # Transaction count (similar pattern but different base)
        tx_factor = combined_factor * np.random.normal(1.0, 0.1, n_days)
        tx_count = (self.base_tx_count * tx_factor).astype(int)
        tx_count = np.maximum(tx_count, self.base_tx_count * 0.5)  # Floor
        
        # Create DataFrame
        df = pd.DataFrame({
            'active_addresses': active_addresses,
            'tx_count': tx_count
        }, index=date_range)
        
        return df
    
    def get_column_names(self) -> List[str]:
        """
        Return column names provided by this data source.
        
        Returns:
            ['active_addresses', 'tx_count']
        """
        return ['active_addresses', 'tx_count']
    
    def get_provider_name(self) -> str:
        """Return provider identifier."""
        return 'onchain'
