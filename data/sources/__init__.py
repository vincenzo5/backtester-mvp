"""
Data Sources Package

This package provides interfaces and implementations for third-party data sources
that can be used alongside OHLCV data in backtests. Examples include on-chain
metrics, sentiment data, news feeds, etc.

Quick Start:
    from data.sources.onchain import MockOnChainProvider
    
    provider = MockOnChainProvider()
    raw_data = provider.fetch('BTC/USD', '2024-01-01', '2024-01-31')
    aligned_data = provider.align_to_ohlcv(raw_data, ohlcv_df, prefix='onchain_')

Package Contents:
    - DataSourceProvider: Abstract base class for all data sources
    - MockOnChainProvider: Example implementation with synthetic on-chain metrics

Example Usage:
    See individual module docstrings for detailed examples:
    - data.sources.base: Base class and interface documentation
    - data.sources.onchain: Mock on-chain provider with usage examples
"""

from data.sources.base import DataSourceProvider
from data.sources.onchain import MockOnChainProvider

__all__ = [
    'DataSourceProvider',
    'MockOnChainProvider',
]
