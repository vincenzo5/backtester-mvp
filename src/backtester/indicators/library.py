"""
Indicator Library: Wraps TA-Lib and supports custom indicators.

This module provides a centralized indicator computation system that:
- Wraps the 'ta' library (Technical Analysis library) for common indicators
- Supports custom indicator registration
- Pre-computes indicators efficiently for walk-forward optimization

Quick Start:
    from indicators.library import IndicatorLibrary
    
    lib = IndicatorLibrary()
    
    # Compute single indicator
    import pandas as pd
    df = pd.DataFrame({'close': [100, 101, 102, 103, 104]})
    result = lib.compute_indicator(df, 'SMA', {'timeperiod': 3}, 'SMA_3')
    print(result)  # Series with SMA values
    
    # Compute multiple indicators
    specs = [
        IndicatorSpec('SMA', {'timeperiod': 20}, 'SMA_20'),
        IndicatorSpec('RSI', {'timeperiod': 14}, 'RSI_14'),
    ]
    enriched_df = lib.compute_all(df, specs)

Common Patterns:
    # Pattern 1: Computing indicators for a strategy
    from indicators.library import IndicatorLibrary
    from indicators.base import IndicatorSpec
    
    lib = IndicatorLibrary()
    df = load_ohlcv_data()  # Your OHLCV DataFrame
    
    # Define what indicators your strategy needs
    indicator_specs = [
        IndicatorSpec('SMA', {'timeperiod': 20}, 'SMA_fast'),
        IndicatorSpec('SMA', {'timeperiod': 50}, 'SMA_slow'),
        IndicatorSpec('RSI', {'timeperiod': 14}, 'RSI_14'),
    ]
    
    # Compute all at once (fast, optimized)
    enriched_df = lib.compute_all(df, indicator_specs)
    
    # Now enriched_df has columns: open, high, low, close, volume, SMA_fast, SMA_slow, RSI_14
    
    # Pattern 2: Using custom indicators
    from indicators.base import register_custom_indicator
    
    def my_volume_indicator(df, params):
        '''Average volume over last N periods'''
        return df['volume'].rolling(window=params['period']).mean()
    
    register_custom_indicator('AVG_VOLUME', my_volume_indicator)
    
    lib = IndicatorLibrary()
    spec = IndicatorSpec('AVG_VOLUME', {'period': 10}, 'avg_vol_10')
    result = lib.compute_indicator(df, 'AVG_VOLUME', {'period': 10}, 'avg_vol_10')
    
    # Pattern 3: Batch computation for walk-forward optimization
    # Compute indicators once, then reuse for multiple parameter combinations
    base_indicators = [
        IndicatorSpec('SMA', {'timeperiod': 10}, 'SMA_10'),
        IndicatorSpec('SMA', {'timeperiod': 20}, 'SMA_20'),
        IndicatorSpec('SMA', {'timeperiod': 50}, 'SMA_50'),
        IndicatorSpec('RSI', {'timeperiod': 14}, 'RSI_14'),
    ]
    
    precomputed_df = lib.compute_all(df, base_indicators)
    
    # Now run multiple backtests with different strategy parameters
    # All using the same pre-computed indicators (very fast!)

Extending:
    To add support for a new indicator from 'ta' library:
    1. Import the indicator class from ta
    2. Add a case in IndicatorLibrary._compute_ta_indicator()
    3. Map indicator name to ta class and handle parameters
    
    To add a completely new indicator library:
    1. Create a new method like _compute_alt_library_indicator()
    2. Update compute_indicator() to route to the new method
    3. Follow the same pattern: function takes (df, params) -> Series/DataFrame
"""

from typing import List, Dict, Any, Union, Optional
import warnings
import pandas as pd
import numpy as np
import json
import time
from backtester.indicators.base import IndicatorSpec, get_custom_indicator


class IndicatorLibrary:
    """
    Library for computing technical indicators.
    
    Wraps the 'ta' library (Technical Analysis library) and supports custom indicators.
    Designed for pre-computation before backtests, optimizing for walk-forward optimization.
    """
    
    def __init__(self):
        """Initialize the indicator library."""
        # Cache for computed indicators to avoid redundant calculations
        self._computation_cache: Dict[str, pd.Series] = {}
        
        # Cache metrics tracking
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'computations': 0,
            'time_saved_seconds': 0.0
        }
    
    def compute_indicator(self, df: pd.DataFrame, indicator_type: str, 
                         params: Dict[str, Any], column_name: str,
                         track_performance: bool = False) -> Union[pd.Series, pd.DataFrame]:
        """
        Compute a single indicator and return the result.
        
        Args:
            df: OHLCV DataFrame with columns: open, high, low, close, volume
                Must have datetime index
            indicator_type: Name of indicator (e.g., 'SMA', 'RSI', 'MACD')
            params: Dictionary of parameters for the indicator
            column_name: Name for the result column (for identification/debugging)
            track_performance: If True, track cache hits/misses for metrics
        
        Returns:
            pandas Series or DataFrame with computed indicator values
            Series returned for single-value indicators
            DataFrame returned for multi-value indicators (e.g., MACD returns 3 columns)
        
        Raises:
            ValueError: If indicator type is unknown
            KeyError: If required DataFrame columns are missing
        
        Example:
            lib = IndicatorLibrary()
            df = load_ohlcv_data()
            
            # Compute SMA
            sma = lib.compute_indicator(df, 'SMA', {'timeperiod': 20}, 'SMA_20')
            
            # Compute RSI
            rsi = lib.compute_indicator(df, 'RSI', {'timeperiod': 14}, 'RSI_14')
        """
        if df.empty:
            raise ValueError("DataFrame is empty")
        
        # Check required columns
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise KeyError(f"Missing required columns: {missing}")
        
        # Generate cache key for performance tracking
        cache_key = None
        if track_performance:
            cache_key = self._generate_cache_key(indicator_type, params, column_name, df)
            start_time = time.time()
        
        # Check cache if performance tracking is enabled
        if track_performance and cache_key and cache_key in self._computation_cache:
            # Cache hit
            self._cache_stats['hits'] += 1
            if start_time:
                # Estimate time saved (use a small fixed value for cache hits)
                self._cache_stats['time_saved_seconds'] += 0.001  # Minimal overhead for cache lookup
            return self._computation_cache[cache_key].copy()
        
        # Cache miss - compute indicator
        if track_performance:
            self._cache_stats['misses'] += 1
            self._cache_stats['computations'] += 1
        
        # Compute the indicator
        # Check if it's a custom indicator
        custom_indicator = get_custom_indicator(indicator_type)
        if custom_indicator:
            result = custom_indicator.compute(df, params)
        elif indicator_type in self._get_ta_indicator_names():
            result = self._compute_ta_indicator(df, indicator_type, params)
        else:
            raise ValueError(f"Unknown indicator type: {indicator_type}. "
                           f"Use register_custom_indicator() to add custom indicators.")
        
        # Store in cache if performance tracking is enabled
        if track_performance and cache_key:
            self._computation_cache[cache_key] = result.copy()
            if start_time:
                compute_time = time.time() - start_time
                # Track that this computation will save time on next hit
                self._cache_stats['time_saved_seconds'] += compute_time
        
        return result
    
    def compute_all(self, df: pd.DataFrame, indicator_specs: List[IndicatorSpec],
                   track_performance: bool = False) -> pd.DataFrame:
        """
        Compute multiple indicators and add them to the DataFrame.
        
        This is the recommended method for computing indicators before backtests.
        All indicators are computed once and added as columns to the DataFrame.
        
        Args:
            df: OHLCV DataFrame (will not be modified)
            indicator_specs: List of IndicatorSpec objects
        
        Returns:
            New DataFrame with original columns plus all indicator columns
        
        Example:
            lib = IndicatorLibrary()
            df = load_ohlcv_data()
            
            specs = [
                IndicatorSpec('SMA', {'timeperiod': 20}, 'SMA_20'),
                IndicatorSpec('RSI', {'timeperiod': 14}, 'RSI_14'),
                IndicatorSpec('MACD', {'fastperiod': 12, 'slowperiod': 26, 'signalperiod': 9}, 'MACD'),
            ]
            
            enriched_df = lib.compute_all(df, specs)
            # enriched_df now has: open, high, low, close, volume, SMA_20, RSI_14, MACD, MACD_signal, MACD_hist
        """
        if df.empty:
            return df.copy()
        
        # Create copy to avoid modifying original
        result_df = df.copy()
        
        for spec in indicator_specs:
            try:
                indicator_data = self.compute_indicator(
                    df,  # Use original df to avoid dependencies between indicators
                    spec.indicator_type,
                    spec.params,
                    spec.column_name,
                    track_performance=track_performance
                )
                
                # Handle multi-column indicators (e.g., MACD, Bollinger Bands)
                if isinstance(indicator_data, pd.DataFrame):
                    # Add each column with a prefix based on column_name
                    for col in indicator_data.columns:
                        result_df[f"{spec.column_name}_{col}"] = indicator_data[col]
                else:
                    # Single column indicator
                    result_df[spec.column_name] = indicator_data
                    
            except Exception as e:
                # Log error but continue with other indicators
                warnings.warn(f"Failed to compute indicator {spec.indicator_type} "
                            f"({spec.column_name}): {str(e)}", UserWarning, stacklevel=2)
                continue
        
        return result_df
    
    def _generate_cache_key(self, indicator_type: str, params: dict, 
                           column_name: str, df: pd.DataFrame) -> str:
        """
        Generate cache key from indicator spec and data fingerprint.
        
        Args:
            indicator_type: Type of indicator
            params: Indicator parameters
            column_name: Column name for the indicator
            df: DataFrame to compute fingerprint from
        
        Returns:
            Cache key string
        """
        # Use data hash (first/last row + length) for fingerprint
        if df.empty:
            data_fingerprint = "empty"
        else:
            data_fingerprint = f"{len(df)}_{df.index[0]}_{df.index[-1]}"
        params_str = json.dumps(params, sort_keys=True)
        return f"{indicator_type}:{column_name}:{params_str}:{data_fingerprint}"
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache effectiveness statistics.
        
        Returns:
            Dictionary with cache hit/miss stats and time saved
        """
        total = self._cache_stats['hits'] + self._cache_stats['misses']
        hit_rate = self._cache_stats['hits'] / total if total > 0 else 0.0
        
        return {
            'hits': self._cache_stats['hits'],
            'misses': self._cache_stats['misses'],
            'hit_rate': hit_rate,
            'total_requests': total,
            'time_saved_seconds': self._cache_stats['time_saved_seconds']
        }
    
    def reset_cache_stats(self):
        """Reset cache statistics (for new workflow)."""
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'computations': 0,
            'time_saved_seconds': 0.0
        }
    
    def _get_ta_indicator_names(self) -> List[str]:
        """Get list of supported TA-Lib indicator names."""
        return ['SMA', 'EMA', 'RSI', 'MACD', 'BBANDS']
    
    def _compute_ta_indicator(self, df: pd.DataFrame, indicator_type: str, 
                              params: Dict[str, Any]) -> Union[pd.Series, pd.DataFrame]:
        """
        Compute indicator using the 'ta' library.
        
        Args:
            df: OHLCV DataFrame
            indicator_type: Indicator name
            params: Indicator parameters
        
        Returns:
            Series or DataFrame
        """
        if indicator_type == 'SMA':
            from ta.trend import SMAIndicator
            indicator = SMAIndicator(close=df['close'], window=params.get('timeperiod', 14))
            return indicator.sma_indicator()
        
        elif indicator_type == 'EMA':
            from ta.trend import EMAIndicator
            indicator = EMAIndicator(close=df['close'], window=params.get('timeperiod', 14))
            return indicator.ema_indicator()
        
        elif indicator_type == 'RSI':
            from ta.momentum import RSIIndicator
            indicator = RSIIndicator(close=df['close'], window=params.get('timeperiod', 14))
            return indicator.rsi()
        
        elif indicator_type == 'MACD':
            from ta.trend import MACD
            indicator = MACD(
                close=df['close'],
                window_fast=params.get('fastperiod', 12),
                window_slow=params.get('slowperiod', 26),
                window_sign=params.get('signalperiod', 9)
            )
            # Return DataFrame with all MACD components
            return pd.DataFrame({
                'macd': indicator.macd(),
                'signal': indicator.macd_signal(),
                'hist': indicator.macd_diff()
            })
        
        elif indicator_type == 'BBANDS':
            from ta.volatility import BollingerBands
            indicator = BollingerBands(
                close=df['close'],
                window=params.get('timeperiod', 20),
                window_dev=params.get('nbdevup', 2)  # Typically 2 standard deviations
            )
            # Return DataFrame with upper, middle, lower bands
            return pd.DataFrame({
                'upper': indicator.bollinger_hband(),
                'middle': indicator.bollinger_mavg(),
                'lower': indicator.bollinger_lband()
            })
        
        else:
            raise ValueError(f"TA-Lib indicator '{indicator_type}' not yet implemented")
