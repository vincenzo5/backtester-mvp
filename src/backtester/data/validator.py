"""
Data validation utilities for timeseries OHLCV data.

This module provides functions to detect gaps, remove duplicates,
and validate data coverage.
"""

import pandas as pd
import numpy as np
from typing import Tuple, List, Dict, Any
from datetime import timedelta


def get_timeframe_delta(timeframe: str) -> timedelta:
    """
    Convert timeframe string to timedelta.
    
    Args:
        timeframe: Timeframe string (e.g., '1m', '5m', '1h', '1d')
    
    Returns:
        Timedelta object representing the timeframe duration
    """
    timeframe_map = {
        '1m': timedelta(minutes=1),
        '5m': timedelta(minutes=5),
        '15m': timedelta(minutes=15),
        '30m': timedelta(minutes=30),
        '1h': timedelta(hours=1),
        '2h': timedelta(hours=2),
        '4h': timedelta(hours=4),
        '6h': timedelta(hours=6),
        '12h': timedelta(hours=12),
        '1d': timedelta(days=1),
        '1w': timedelta(weeks=1),
        '1M': timedelta(days=30),  # Approximate
    }
    
    return timeframe_map.get(timeframe, timedelta(hours=1))


def remove_duplicates(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """
    Remove duplicate timestamps from DataFrame.
    
    Args:
        df: DataFrame with datetime index
    
    Returns:
        Tuple of (cleaned DataFrame, number of duplicates removed)
    """
    if df.empty:
        return df, 0
    
    original_count = len(df)
    
    # Remove duplicates, keeping the last occurrence
    df_cleaned = df[~df.index.duplicated(keep='last')]
    
    duplicates_removed = original_count - len(df_cleaned)
    
    # Sort by index to ensure chronological order
    df_cleaned = df_cleaned.sort_index()
    
    return df_cleaned, duplicates_removed


def detect_gaps(df: pd.DataFrame, timeframe: str, 
                tolerance: float = 0.05) -> List[Dict[str, Any]]:
    """
    Detect gaps in timeseries data.
    
    Args:
        df: DataFrame with datetime index
        timeframe: Expected timeframe (e.g., '1h', '1d')
        tolerance: Tolerance for gap detection (0.05 = 5% missing is acceptable)
    
    Returns:
        List of gap dictionaries with start, end, expected_count, actual_count
    """
    if df.empty or len(df) < 2:
        return []
    
    gaps = []
    timeframe_delta = get_timeframe_delta(timeframe)
    
    # Sort by index
    df_sorted = df.sort_index()
    
    # Calculate expected intervals
    expected_interval = timeframe_delta.total_seconds()
    
    # Find gaps
    for i in range(len(df_sorted) - 1):
        current_time = df_sorted.index[i]
        next_time = df_sorted.index[i + 1]
        
        actual_interval = (next_time - current_time).total_seconds()
        
        # Check if gap is significantly larger than expected
        if actual_interval > expected_interval * 1.5:  # 50% tolerance for timing variations
            expected_candles = int(actual_interval / expected_interval)
            missing_candles = expected_candles - 1  # -1 because we have the end candle
            
            gaps.append({
                'start': current_time.isoformat(),
                'end': next_time.isoformat(),
                'expected_candles': expected_candles,
                'missing_candles': missing_candles,
                'duration_seconds': actual_interval
            })
    
    return gaps


def validate_coverage(df: pd.DataFrame, timeframe: str, 
                     start_date: pd.Timestamp, end_date: pd.Timestamp,
                     tolerance: float = 0.05) -> Dict[str, Any]:
    """
    Validate data coverage for a date range.
    
    Args:
        df: DataFrame with datetime index
        timeframe: Expected timeframe (e.g., '1h', '1d')
        start_date: Expected start date
        end_date: Expected end date
        tolerance: Acceptable percentage of missing data (0.05 = 5%)
    
    Returns:
        Validation results dictionary
    """
    timeframe_delta = get_timeframe_delta(timeframe)
    
    # Calculate expected candle count
    total_duration = (end_date - start_date).total_seconds()
    expected_interval = timeframe_delta.total_seconds()
    expected_count = int(total_duration / expected_interval)
    
    # Filter data to date range
    df_filtered = df[(df.index >= start_date) & (df.index <= end_date)]
    actual_count = len(df_filtered)
    
    # Calculate coverage percentage
    coverage_pct = (actual_count / expected_count) if expected_count > 0 else 0.0
    
    # Check if coverage meets tolerance
    is_valid = coverage_pct >= (1.0 - tolerance)
    
    return {
        'expected_count': expected_count,
        'actual_count': actual_count,
        'missing_count': expected_count - actual_count,
        'coverage_pct': coverage_pct,
        'is_valid': is_valid,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'actual_start': df_filtered.index.min().isoformat() if not df_filtered.empty else None,
        'actual_end': df_filtered.index.max().isoformat() if not df_filtered.empty else None
    }


def validate_ohlcv_integrity(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Validate OHLCV price relationships and ensure all prices are positive.
    
    Args:
        df: DataFrame with datetime index and OHLCV columns (open, high, low, close, volume)
    
    Returns:
        Dictionary with valid_count, invalid_count, and issues list
    """
    if df.empty:
        return {
            'valid_count': 0,
            'invalid_count': 0,
            'issues': []
        }
    
    required_cols = ['open', 'high', 'low', 'close', 'volume']
    if not all(col in df.columns for col in required_cols):
        return {
            'valid_count': 0,
            'invalid_count': len(df),
            'issues': ['Missing required OHLCV columns']
        }
    
    issues = []
    invalid_mask = pd.Series(False, index=df.index)
    
    # Check all prices > 0
    price_cols = ['open', 'high', 'low', 'close']
    for col in price_cols:
        invalid = df[col] <= 0
        invalid_mask |= invalid
        if invalid.any():
            issues.append(f"{col}: {invalid.sum()} candles with non-positive values")
    
    # Check volume >= 0
    invalid_volume = df['volume'] < 0
    invalid_mask |= invalid_volume
    if invalid_volume.any():
        issues.append(f"volume: {invalid_volume.sum()} candles with negative volume")
    
    # Check High >= Low (fundamental requirement)
    invalid_high_low = df['high'] < df['low']
    invalid_mask |= invalid_high_low
    if invalid_high_low.any():
        issues.append(f"high_low: {invalid_high_low.sum()} candles with high < low")
    
    # Check High >= Open and High >= Close
    invalid_high_open = df['high'] < df['open']
    invalid_mask |= invalid_high_open
    if invalid_high_open.any():
        issues.append(f"high_open: {invalid_high_open.sum()} candles with high < open")
    
    invalid_high_close = df['high'] < df['close']
    invalid_mask |= invalid_high_close
    if invalid_high_close.any():
        issues.append(f"high_close: {invalid_high_close.sum()} candles with high < close")
    
    # Check Low <= Open and Low <= Close
    invalid_low_open = df['low'] > df['open']
    invalid_mask |= invalid_low_open
    if invalid_low_open.any():
        issues.append(f"low_open: {invalid_low_open.sum()} candles with low > open")
    
    invalid_low_close = df['low'] > df['close']
    invalid_mask |= invalid_low_close
    if invalid_low_close.any():
        issues.append(f"low_close: {invalid_low_close.sum()} candles with low > close")
    
    valid_count = (~invalid_mask).sum()
    invalid_count = invalid_mask.sum()
    
    return {
        'valid_count': int(valid_count),
        'invalid_count': int(invalid_count),
        'issues': issues
    }


def detect_outliers(df: pd.DataFrame, method: str = 'iqr', multiplier: float = 1.5,
                   columns: list = None) -> List[Any]:
    """
    Detect outliers in OHLCV data using statistical methods.
    
    Args:
        df: DataFrame with datetime index
        method: Method to use ('iqr' for Interquartile Range)
        multiplier: Multiplier for IQR method (default 1.5)
        columns: Columns to check for outliers (default: ['open', 'high', 'low', 'close', 'volume'])
    
    Returns:
        List of outlier indices (row positions)
    """
    if df.empty or len(df) < 4:  # Need at least 4 points for IQR
        return []
    
    if columns is None:
        columns = ['open', 'high', 'low', 'close', 'volume']
    
    # Filter to columns that exist
    columns = [col for col in columns if col in df.columns]
    if not columns:
        return []
    
    outlier_indices = set()
    
    if method == 'iqr':
        for col in columns:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            
            if IQR == 0:
                continue  # Skip if no variance
            
            lower_bound = Q1 - multiplier * IQR
            upper_bound = Q3 + multiplier * IQR
            
            outliers = df[(df[col] < lower_bound) | (df[col] > upper_bound)]
            outlier_indices.update(outliers.index.tolist())
    
    return sorted(outlier_indices)


def validate_volume(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Validate volume data: non-negative, detect zero volume, detect extreme outliers.
    
    Args:
        df: DataFrame with datetime index and 'volume' column
    
    Returns:
        Dictionary with zero_volume_count, outlier_count, outlier_indices
    """
    if df.empty or 'volume' not in df.columns:
        return {
            'zero_volume_count': 0,
            'outlier_count': 0,
            'outlier_indices': []
        }
    
    # Check for negative volume
    negative_volume = (df['volume'] < 0).sum()
    
    # Count zero volume
    zero_volume_count = int((df['volume'] == 0).sum())
    
    # Detect volume outliers using IQR
    outlier_indices = detect_outliers(df, method='iqr', multiplier=1.5, columns=['volume'])
    outlier_count = len(outlier_indices)
    
    return {
        'zero_volume_count': zero_volume_count,
        'negative_volume_count': int(negative_volume),
        'outlier_count': outlier_count,
        'outlier_indices': outlier_indices
    }


def validate_cross_candle_consistency(df: pd.DataFrame, tolerance: float = 0.01) -> Dict[str, Any]:
    """
    Validate cross-candle consistency: next candle's open should be close to previous candle's close.
    
    Args:
        df: DataFrame with datetime index and OHLCV columns
        tolerance: Maximum allowed price difference as fraction (0.01 = 1%)
    
    Returns:
        Dictionary with consistent_count, inconsistent_count, gap_count
    """
    if df.empty or len(df) < 2:
        return {
            'consistent_count': 0,
            'inconsistent_count': 0,
            'gap_count': 0
        }
    
    if 'open' not in df.columns or 'close' not in df.columns:
        return {
            'consistent_count': 0,
            'inconsistent_count': 0,
            'gap_count': 0
        }
    
    # Sort by index to ensure chronological order
    df_sorted = df.sort_index()
    
    consistent_count = 0
    inconsistent_count = 0
    
    # Compare each candle's open to previous candle's close
    for i in range(1, len(df_sorted)):
        prev_close = df_sorted.iloc[i - 1]['close']
        curr_open = df_sorted.iloc[i]['open']
        
        # Skip if either value is invalid
        if pd.isna(prev_close) or pd.isna(curr_open) or prev_close <= 0:
            continue
        
        # Calculate percentage difference
        price_diff_pct = abs(curr_open - prev_close) / prev_close
        
        if price_diff_pct <= tolerance:
            consistent_count += 1
        else:
            inconsistent_count += 1
    
    total_transitions = len(df_sorted) - 1
    gap_count = inconsistent_count
    
    return {
        'consistent_count': consistent_count,
        'inconsistent_count': inconsistent_count,
        'total_transitions': total_transitions,
        'gap_count': gap_count
    }


def validate_missing_values(df: pd.DataFrame) -> Dict[str, int]:
    """
    Detect missing values (NaN) in OHLCV columns.
    
    Args:
        df: DataFrame with datetime index
    
    Returns:
        Dictionary with missing value counts by column
    """
    if df.empty:
        return {}
    
    missing_counts = {}
    for col in df.columns:
        missing_count = int(df[col].isna().sum())
        if missing_count > 0:
            missing_counts[col] = missing_count
    
    return missing_counts


def validate_chronological_order(df: pd.DataFrame) -> bool:
    """
    Validate that DataFrame index is strictly increasing (chronological order).
    
    Args:
        df: DataFrame with datetime index
    
    Returns:
        True if index is strictly increasing, False otherwise
    """
    if df.empty or len(df) < 2:
        return True
    
    df_sorted = df.sort_index()
    
    # Check if sorted index equals original index (means already in order)
    if df.index.equals(df_sorted.index):
        # Verify strictly increasing
        diffs = df.index[1:] - df.index[:-1]
        return (diffs > pd.Timedelta(0)).all()
    
    return False


def validate_data(df: pd.DataFrame, timeframe: str) -> Dict[str, Any]:
    """
    Comprehensive data validation.
    
    Args:
        df: DataFrame with datetime index
        timeframe: Expected timeframe (e.g., '1h', '1d')
    
    Returns:
        Validation results dictionary
    """
    if df.empty:
        return {
            'valid': False,
            'error': 'Empty DataFrame',
            'duplicates': 0,
            'gaps': [],
            'candle_count': 0
        }
    
    # Remove duplicates
    df_cleaned, duplicates_removed = remove_duplicates(df)
    
    # Detect gaps
    gaps = detect_gaps(df_cleaned, timeframe)
    
    # Calculate basic stats
    candle_count = len(df_cleaned)
    first_date = df_cleaned.index.min()
    last_date = df_cleaned.index.max()
    
    # Determine if data is valid (has data, no major issues)
    is_valid = candle_count > 0 and len(gaps) == 0
    
    return {
        'valid': is_valid,
        'duplicates': duplicates_removed,
        'gaps': gaps,
        'candle_count': candle_count,
        'first_date': first_date.isoformat() if candle_count > 0 else None,
        'last_date': last_date.isoformat() if candle_count > 0 else None,
        'date_range_days': (last_date - first_date).days if candle_count > 1 else 0
    }

