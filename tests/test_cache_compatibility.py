"""
Cache compatibility tests.

These tests ensure that cache files written by the data collection system
can be reliably read by the backtesting engine, maintaining compatibility
across system updates.
"""

import sys
import os
from pathlib import Path
import pandas as pd
import pytest
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.cache_manager import read_cache, write_cache, get_cache_path, delete_cache


@pytest.fixture
def test_symbol():
    """Test symbol for cache operations."""
    return "TEST/USD"


@pytest.fixture
def test_timeframe():
    """Test timeframe for cache operations."""
    return "1h"


@pytest.fixture
def sample_dataframe():
    """
    Create sample OHLCV DataFrame matching expected cache format.
    
    Format: DatetimeIndex with columns [open, high, low, close, volume]
    """
    dates = pd.date_range('2025-01-01', periods=100, freq='1h', tz='UTC')
    df = pd.DataFrame({
        'open': range(100, 200),
        'high': range(105, 205),
        'low': range(95, 195),
        'close': range(102, 202),
        'volume': range(1000, 1100)
    }, index=dates)
    
    return df


def test_write_read_roundtrip(test_symbol, test_timeframe, sample_dataframe):
    """
    Test that writing and reading cache preserves data integrity.
    
    This is the core compatibility contract: data written by cache_manager
    must be readable by cache_manager in the same format.
    """
    # Clean up any existing test cache
    delete_cache(test_symbol, test_timeframe)
    
    # Write data
    write_cache(test_symbol, test_timeframe, sample_dataframe)
    
    # Read data back
    df_read = read_cache(test_symbol, test_timeframe)
    
    # Verify data integrity
    assert not df_read.empty, "Read cache should not be empty"
    assert len(df_read) == len(sample_dataframe), \
        f"Row count mismatch: expected {len(sample_dataframe)}, got {len(df_read)}"
    assert list(df_read.columns) == ['open', 'high', 'low', 'close', 'volume'], \
        f"Column mismatch: expected OHLCV columns, got {list(df_read.columns)}"
    assert isinstance(df_read.index, pd.DatetimeIndex), \
        "Index must be DatetimeIndex"
    
    # Verify data values (allowing for float precision)
    # Note: read cache will have index.name='datetime', original may not
    df_read_for_compare = df_read.copy()
    df_orig_for_compare = sample_dataframe.copy()
    df_read_for_compare.index.name = df_orig_for_compare.index.name  # Match index names
    
    pd.testing.assert_frame_equal(
        df_read_for_compare.sort_index(),
        df_orig_for_compare.sort_index(),
        check_names=False,
        check_freq=False  # Frequency may differ after CSV roundtrip
    )
    
    # Cleanup
    delete_cache(test_symbol, test_timeframe)


def test_cache_file_format(test_symbol, test_timeframe, sample_dataframe):
    """
    Test that cache files use expected CSV format.
    
    Cache files must be readable as standard CSV with datetime index.
    """
    # Write data
    write_cache(test_symbol, test_timeframe, sample_dataframe)
    
    # Read directly from file (bypassing cache_manager to test raw format)
    cache_file = get_cache_path(test_symbol, test_timeframe)
    assert cache_file.exists(), "Cache file should exist"
    
    # Read using pandas directly
    df_direct = pd.read_csv(cache_file, index_col='datetime', parse_dates=True)
    
    # Verify format
    assert isinstance(df_direct.index, pd.DatetimeIndex), \
        "Raw CSV should have DatetimeIndex when read with parse_dates"
    assert list(df_direct.columns) == ['open', 'high', 'low', 'close', 'volume'], \
        "CSV should have OHLCV columns"
    
    # Cleanup
    delete_cache(test_symbol, test_timeframe)


def test_read_empty_cache(test_symbol, test_timeframe):
    """Test that reading non-existent cache returns empty DataFrame."""
    delete_cache(test_symbol, test_timeframe)
    
    df = read_cache(test_symbol, test_timeframe)
    
    assert isinstance(df, pd.DataFrame), "Should return DataFrame"
    assert df.empty, "Non-existent cache should return empty DataFrame"


def test_cache_append_behavior(test_symbol, test_timeframe):
    """
    Test that appending to cache (delta updates) maintains data integrity.
    
    This simulates the daily update process where new data is appended.
    """
    # Initial data
    dates1 = pd.date_range('2025-01-01', periods=50, freq='1h', tz='UTC')
    df1 = pd.DataFrame({
        'open': range(100, 150),
        'high': range(105, 155),
        'low': range(95, 145),
        'close': range(102, 152),
        'volume': range(1000, 1050)
    }, index=dates1)
    
    # New data (after initial data)
    dates2 = pd.date_range('2025-01-03', periods=50, freq='1h', tz='UTC')
    df2 = pd.DataFrame({
        'open': range(150, 200),
        'high': range(155, 205),
        'low': range(145, 195),
        'close': range(152, 202),
        'volume': range(1050, 1100)
    }, index=dates2)
    
    # Write initial data
    delete_cache(test_symbol, test_timeframe)
    write_cache(test_symbol, test_timeframe, df1)
    
    # Simulate append (what updater does)
    existing = read_cache(test_symbol, test_timeframe)
    combined = pd.concat([existing, df2])
    combined = combined[~combined.index.duplicated(keep='last')]
    combined = combined.sort_index()
    write_cache(test_symbol, test_timeframe, combined)
    
    # Verify combined data
    df_final = read_cache(test_symbol, test_timeframe)
    assert len(df_final) > len(df1), "Final cache should have more data"
    assert df_final.index.min() <= df1.index.min(), "Should contain original data"
    assert df_final.index.max() >= df2.index.max(), "Should contain new data"
    
    # Cleanup
    delete_cache(test_symbol, test_timeframe)


def test_datetime_index_required(test_symbol, test_timeframe):
    """Test that write_cache enforces DatetimeIndex requirement."""
    # Create DataFrame with non-datetime index (should fail)
    df_bad = pd.DataFrame({
        'open': [100, 101],
        'high': [105, 106],
        'low': [95, 96],
        'close': [102, 103],
        'volume': [1000, 1100]
    }, index=[0, 1])
    
    with pytest.raises(ValueError, match="must have DatetimeIndex"):
        write_cache(test_symbol, test_timeframe, df_bad)


def test_backtest_filtering_compatibility(test_symbol, test_timeframe, sample_dataframe):
    """
    Test that cached data works with backtest date filtering.
    
    This simulates how backtest/execution/parallel.py filters data.
    """
    # Write cache
    write_cache(test_symbol, test_timeframe, sample_dataframe)
    
    # Read cache (as backtest does)
    df = read_cache(test_symbol, test_timeframe)
    
    # Apply date filtering (as backtest does)
    start_date = "2025-01-01"
    end_date = "2025-01-05"
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    
    # Handle timezone-aware DataFrames (as backtest does)
    if df.index.tz is not None:
        from datetime import timezone
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
    
    df_filtered = df[(df.index >= start_dt) & (df.index <= end_dt)]
    
    # Verify filtering works
    assert not df_filtered.empty, "Filtered data should not be empty"
    assert df_filtered.index.min() >= start_dt, "Should respect start date"
    assert df_filtered.index.max() <= end_dt, "Should respect end date"
    
    # Cleanup
    delete_cache(test_symbol, test_timeframe)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

