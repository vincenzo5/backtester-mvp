"""
Data quality scoring module.

This module calculates component scores and composite quality scores
for OHLCV datasets based on various quality metrics.
"""

import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime

from backtester.data.validator import (
    validate_ohlcv_integrity, validate_volume, detect_outliers,
    validate_cross_candle_consistency, validate_missing_values,
    validate_chronological_order, detect_gaps, get_timeframe_delta
)
from backtester.data.cache_manager import read_cache, get_manifest_entry


def load_quality_weights(config_manager=None) -> Dict[str, float]:
    """
    Load quality scoring weights from config.
    
    Args:
        config_manager: Optional ConfigManager instance (creates one if not provided)
    
    Returns:
        Dictionary of component weights
    """
    default_weights = {
        'coverage': 0.30,
        'integrity': 0.25,
        'gaps': 0.20,
        'completeness': 0.15,
        'consistency': 0.10,
        'volume': 0.05,
        'outliers': 0.05
    }
    
    try:
        if config_manager is None:
            from config import ConfigManager
            config_manager = ConfigManager()
        
        dq_config = config_manager.get_data_quality_config()
        weights = dq_config.weights
        
        # Merge with defaults (use defaults if not specified)
        result = default_weights.copy()
        result.update(weights)
        
        return result
    except Exception:
        return default_weights


def load_quality_thresholds(config_manager=None) -> Dict[str, Any]:
    """
    Load quality thresholds from config.
    
    Args:
        config_manager: Optional ConfigManager instance (creates one if not provided)
    
    Returns:
        Dictionary of threshold values
    """
    default_thresholds = {
        'consistency_tolerance': 0.01,
        'outlier_iqr_multiplier': 1.5,
        'gap_penalty_small': 0.5,
        'gap_penalty_large': 1.0,
        'outlier_penalty': 0.1,
        'warning_threshold': 70
    }
    
    try:
        if config_manager is None:
            from config import ConfigManager
            config_manager = ConfigManager()
        
        dq_config = config_manager.get_data_quality_config()
        thresholds = dq_config.thresholds
        
        # Merge with defaults
        result = default_thresholds.copy()
        result.update(thresholds)
        
        return result
    except Exception:
        return default_thresholds


def calculate_coverage_score(df: pd.DataFrame, timeframe: str,
                            start_date: Optional[pd.Timestamp] = None,
                            end_date: Optional[pd.Timestamp] = None) -> float:
    """
    Calculate coverage score: percentage of expected candles present.
    
    Args:
        df: DataFrame with datetime index
        timeframe: Expected timeframe (e.g., '1h', '1d')
        start_date: Expected start date (uses df.min() if None)
        end_date: Expected end date (uses df.max() if None)
    
    Returns:
        Coverage score (0-100)
    """
    if df.empty:
        return 0.0
    
    if start_date is None:
        start_date = df.index.min()
    if end_date is None:
        end_date = df.index.max()
    
    # Ensure timezone awareness matches
    if isinstance(start_date, pd.Timestamp):
        if df.index.tz is not None and start_date.tz is None:
            start_date = pd.to_datetime(start_date).tz_localize(df.index.tz)
        elif df.index.tz is None and start_date.tz is not None:
            start_date = start_date.tz_localize(None)
    
    if isinstance(end_date, pd.Timestamp):
        if df.index.tz is not None and end_date.tz is None:
            end_date = pd.to_datetime(end_date).tz_localize(df.index.tz)
        elif df.index.tz is None and end_date.tz is not None:
            end_date = end_date.tz_localize(None)
    
    timeframe_delta = get_timeframe_delta(timeframe)
    expected_interval = timeframe_delta.total_seconds()
    
    total_duration = (end_date - start_date).total_seconds()
    expected_count = int(total_duration / expected_interval) + 1
    
    if expected_count <= 0:
        return 0.0
    
    # Filter data to date range
    df_filtered = df[(df.index >= start_date) & (df.index <= end_date)]
    actual_count = len(df_filtered)
    
    coverage_score = (actual_count / expected_count) * 100
    
    # Cap at 100% (can exceed if data extends beyond expected range)
    return min(100.0, coverage_score)


def calculate_gaps_score(df: pd.DataFrame, timeframe: str,
                        thresholds: Dict[str, Any]) -> float:
    """
    Calculate gaps score: inverse of gap count/severity.
    
    Args:
        df: DataFrame with datetime index
        timeframe: Expected timeframe
        thresholds: Dictionary with gap_penalty_small and gap_penalty_large
    
    Returns:
        Gaps score (0-100)
    """
    gaps = detect_gaps(df, timeframe)
    
    if not gaps:
        return 100.0
    
    small_gap_penalty = thresholds.get('gap_penalty_small', 0.5)
    large_gap_penalty = thresholds.get('gap_penalty_large', 1.0)
    
    small_gap_count = 0
    large_gap_count = 0
    
    for gap in gaps:
        duration_hours = gap['duration_seconds'] / 3600
        if duration_hours >= 24:
            large_gap_count += 1
        else:
            small_gap_count += 1
    
    penalty = (small_gap_count * small_gap_penalty) + (large_gap_count * large_gap_penalty)
    gaps_score = max(0.0, 100.0 - penalty)
    
    return gaps_score


def calculate_integrity_score(df: pd.DataFrame) -> float:
    """
    Calculate integrity score: percentage of candles with valid OHLCV relationships.
    
    Args:
        df: DataFrame with datetime index and OHLCV columns
    
    Returns:
        Integrity score (0-100)
    """
    if df.empty:
        return 0.0
    
    integrity_result = validate_ohlcv_integrity(df)
    valid_count = integrity_result['valid_count']
    invalid_count = integrity_result['invalid_count']
    total_count = valid_count + invalid_count
    
    if total_count == 0:
        return 0.0
    
    integrity_score = (valid_count / total_count) * 100
    
    return integrity_score


def calculate_volume_score(df: pd.DataFrame, thresholds: Dict[str, Any]) -> float:
    """
    Calculate volume score: percentage of candles with reasonable volume.
    
    Args:
        df: DataFrame with datetime index and 'volume' column
        thresholds: Dictionary with outlier configuration
    
    Returns:
        Volume score (0-100)
    """
    if df.empty or 'volume' not in df.columns:
        return 0.0
    
    volume_result = validate_volume(df)
    total_count = len(df)
    zero_volume_count = volume_result['zero_volume_count']
    outlier_count = volume_result['outlier_count']
    
    # Count valid volume candles (non-zero, non-outlier)
    valid_volume_count = total_count - zero_volume_count - outlier_count
    
    if total_count == 0:
        return 0.0
    
    # Base score from valid volume percentage
    volume_score = (valid_volume_count / total_count) * 100
    
    # Apply penalty for outliers (smaller penalty since already counted)
    outlier_penalty = thresholds.get('outlier_penalty', 0.1)
    volume_score = max(0.0, volume_score - (outlier_count * outlier_penalty * 0.5))
    
    return volume_score


def calculate_consistency_score(df: pd.DataFrame, thresholds: Dict[str, Any]) -> float:
    """
    Calculate consistency score: percentage of smooth cross-candle transitions.
    
    Args:
        df: DataFrame with datetime index and OHLCV columns
        thresholds: Dictionary with consistency_tolerance
    
    Returns:
        Consistency score (0-100)
    """
    if df.empty or len(df) < 2:
        return 100.0  # Single candle or empty is considered consistent
    
    tolerance = thresholds.get('consistency_tolerance', 0.01)
    consistency_result = validate_cross_candle_consistency(df, tolerance=tolerance)
    
    total_transitions = consistency_result['total_transitions']
    
    if total_transitions == 0:
        return 100.0
    
    consistent_count = consistency_result['consistent_count']
    consistency_score = (consistent_count / total_transitions) * 100
    
    return consistency_score


def calculate_outliers_score(df: pd.DataFrame, thresholds: Dict[str, Any]) -> float:
    """
    Calculate outliers score: inverse of outlier count.
    
    Args:
        df: DataFrame with datetime index
        thresholds: Dictionary with outlier_iqr_multiplier and outlier_penalty
    
    Returns:
        Outliers score (0-100)
    """
    if df.empty:
        return 100.0
    
    multiplier = thresholds.get('outlier_iqr_multiplier', 1.5)
    outlier_indices = detect_outliers(df, method='iqr', multiplier=multiplier)
    outlier_count = len(outlier_indices)
    
    total_count = len(df)
    if total_count == 0:
        return 100.0
    
    # Penalty per outlier
    penalty = thresholds.get('outlier_penalty', 0.1)
    outliers_score = max(0.0, 100.0 - (outlier_count * penalty))
    
    return outliers_score


def calculate_completeness_score(df: pd.DataFrame, timeframe: str,
                               expected_start_date: Optional[pd.Timestamp] = None,
                               expected_end_date: Optional[pd.Timestamp] = None) -> float:
    """
    Calculate completeness score: coverage of desired vs actual date range.
    
    Args:
        df: DataFrame with datetime index
        timeframe: Expected timeframe
        expected_start_date: Desired start date (uses df.min() if None)
        expected_end_date: Desired end date (uses df.max() if None)
    
    Returns:
        Completeness score (0-100)
    """
    if df.empty:
        return 0.0
    
    actual_start = df.index.min()
    actual_end = df.index.max()
    
    if expected_start_date is None:
        expected_start_date = actual_start
    if expected_end_date is None:
        expected_end_date = actual_end
    
    # Ensure timezone awareness matches
    if isinstance(expected_start_date, pd.Timestamp):
        if df.index.tz is not None and expected_start_date.tz is None:
            expected_start_date = pd.to_datetime(expected_start_date).tz_localize(df.index.tz)
        elif df.index.tz is None and expected_start_date.tz is not None:
            expected_start_date = expected_start_date.tz_localize(None)
    
    if isinstance(expected_end_date, pd.Timestamp):
        if df.index.tz is not None and expected_end_date.tz is None:
            expected_end_date = pd.to_datetime(expected_end_date).tz_localize(df.index.tz)
        elif df.index.tz is None and expected_end_date.tz is not None:
            expected_end_date = expected_end_date.tz_localize(None)
    
    # Calculate coverage for start and end
    timeframe_delta = get_timeframe_delta(timeframe)
    expected_interval = timeframe_delta.total_seconds()
    
    # Start date coverage (how close actual start is to expected start)
    if expected_start_date <= actual_start:
        start_coverage = 1.0  # Actual starts on or before expected (good)
    else:
        # Actual starts later than expected (penalty)
        delay_seconds = (actual_start - expected_start_date).total_seconds()
        delay_candles = delay_seconds / expected_interval
        # Penalize: lose points for delay, but don't go negative
        start_coverage = max(0.0, 1.0 - (delay_candles / 10000))  # Scale down large delays
    
    # End date coverage (how close actual end is to expected end)
    if actual_end >= expected_end_date:
        end_coverage = 1.0  # Actual ends on or after expected (good)
    else:
        # Actual ends earlier than expected (penalty, could be delisted)
        shortfall_seconds = (expected_end_date - actual_end).total_seconds()
        shortfall_candles = shortfall_seconds / expected_interval
        # Penalize: lose points for shortfall
        end_coverage = max(0.0, 1.0 - (shortfall_candles / 10000))  # Scale down large shortfalls
    
    # Average of start and end coverage
    completeness_score = ((start_coverage + end_coverage) / 2.0) * 100
    
    return completeness_score


def calculate_component_scores(df: pd.DataFrame, timeframe: str,
                              start_date: Optional[pd.Timestamp] = None,
                              end_date: Optional[pd.Timestamp] = None,
                              weights: Optional[Dict[str, float]] = None,
                              thresholds: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Calculate all component quality scores.
    
    Args:
        df: DataFrame with datetime index and OHLCV columns
        timeframe: Expected timeframe (e.g., '1h', '1d')
        start_date: Expected start date
        end_date: Expected end date
        weights: Component weights dictionary (loads from config if None)
        thresholds: Quality thresholds dictionary (loads from config if None)
    
    Returns:
        Dictionary with all component scores
    """
    if weights is None:
        weights = load_quality_weights()
    if thresholds is None:
        thresholds = load_quality_thresholds()
    
    # Parse dates if strings
    if isinstance(start_date, str):
        start_date = pd.to_datetime(start_date)
        # Match timezone to dataframe
        if df.index.tz is not None and start_date.tz is None:
            start_date = start_date.tz_localize(df.index.tz)
        elif df.index.tz is None and start_date.tz is not None:
            start_date = start_date.tz_localize(None)
    
    if isinstance(end_date, str):
        end_date = pd.to_datetime(end_date)
        # Match timezone to dataframe
        if df.index.tz is not None and end_date.tz is None:
            end_date = end_date.tz_localize(df.index.tz)
        elif df.index.tz is None and end_date.tz is not None:
            end_date = end_date.tz_localize(None)
    
    # Calculate all component scores
    scores = {
        'coverage': calculate_coverage_score(df, timeframe, start_date, end_date),
        'gaps': calculate_gaps_score(df, timeframe, thresholds),
        'integrity': calculate_integrity_score(df),
        'volume': calculate_volume_score(df, thresholds),
        'consistency': calculate_consistency_score(df, thresholds),
        'outliers': calculate_outliers_score(df, thresholds),
        'completeness': calculate_completeness_score(df, timeframe, start_date, end_date)
    }
    
    return scores


def calculate_composite_score(component_scores: Dict[str, float],
                             weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """
    Calculate composite quality score and grade.
    
    Args:
        component_scores: Dictionary of component scores
        weights: Component weights dictionary (loads from config if None)
    
    Returns:
        Dictionary with composite score and grade
    """
    if weights is None:
        weights = load_quality_weights()
    
    # Calculate weighted average
    composite = sum(component_scores.get(comp, 0) * weights.get(comp, 0)
                   for comp in weights.keys())
    
    # Normalize by sum of weights (in case they don't sum to 1.0)
    weight_sum = sum(weights.values())
    if weight_sum > 0:
        composite = composite / weight_sum
    
    # Determine grade
    if composite >= 90:
        grade = 'A'
    elif composite >= 80:
        grade = 'B'
    elif composite >= 70:
        grade = 'C'
    elif composite >= 60:
        grade = 'D'
    else:
        grade = 'F'
    
    return {
        'composite': round(composite, 2),
        'grade': grade
    }


def assess_data_quality(symbol: str, timeframe: str,
                       start_date: Optional[pd.Timestamp] = None,
                       end_date: Optional[pd.Timestamp] = None) -> Dict[str, Any]:
    """
    Complete data quality assessment pipeline.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
        start_date: Expected start date
        end_date: Expected end date
    
    Returns:
        Complete assessment dictionary with component scores, composite score, and grade
    """
    # Load data
    df = read_cache(symbol, timeframe)
    
    if df.empty:
        return {
            'status': 'no_data',
            'component_scores': {},
            'composite': 0.0,
            'grade': 'F'
        }
    
    # Get dates from manifest if not provided
    if start_date is None or end_date is None:
        manifest_entry = get_manifest_entry(symbol, timeframe)
        if manifest_entry:
            if start_date is None and manifest_entry.get('first_date'):
                start_date = pd.to_datetime(manifest_entry['first_date'])
            if end_date is None and manifest_entry.get('last_date'):
                end_date = pd.to_datetime(manifest_entry['last_date'])
    
    # If still no dates, use actual data range
    if start_date is None:
        start_date = df.index.min()
    if end_date is None:
        end_date = df.index.max()
    
    # Calculate component scores
    component_scores = calculate_component_scores(df, timeframe, start_date, end_date)
    
    # Calculate composite score
    composite_result = calculate_composite_score(component_scores)
    
    # Round component scores
    rounded_scores = {k: round(v, 2) for k, v in component_scores.items()}
    
    return {
        'status': 'assessed',
        'component_scores': rounded_scores,
        'composite': composite_result['composite'],
        'grade': composite_result['grade'],
        'assessment_date': datetime.utcnow().isoformat() + 'Z'
    }

