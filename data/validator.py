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

