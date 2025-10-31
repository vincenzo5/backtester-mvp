"""
StdDev-based volatility regime filter.

Classifies market bars as high, normal, or low volatility based on standard deviation of returns.
Uses percentile thresholds computed on the full dataset for performance.
"""

import pandas as pd
import numpy as np
from backtester.filters.base import BaseFilter


class VolatilityRegimeStdDev(BaseFilter):
    """
    Standard deviation-based volatility regime filter.
    
    Classifies each bar as:
    - 'high': StdDev value above high_threshold percentile (default 75th)
    - 'low': StdDev value below low_threshold percentile (default 25th)
    - 'normal': StdDev value between thresholds
    
    Uses full dataset for percentile calculation (most performant approach).
    """
    
    name = 'volatility_regime_stddev'
    regimes = ['high', 'normal', 'low']
    matching = 'entry'  # Filter trades based on entry regime
    
    default_params = {
        'lookback': 14,  # Rolling window for standard deviation
        'high_threshold': 0.75,  # 75th percentile for high volatility
        'low_threshold': 0.25,   # 25th percentile for low volatility
        'threshold_method': 'full_dataset'  # Use full dataset for percentiles
    }
    
    def compute_classification(self, df: pd.DataFrame, params: dict = None) -> pd.Series:
        """
        Compute StdDev-based volatility regime classification for each bar.
        
        Args:
            df: OHLCV DataFrame with datetime index
            params: Optional parameter dictionary to override default_params
        
        Returns:
            Series with regime labels ('high', 'normal', 'low') indexed by df.index
        """
        params = params or self.default_params
        lookback = params.get('lookback', 14)
        high_threshold = params.get('high_threshold', 0.75)
        low_threshold = params.get('low_threshold', 0.25)
        
        if df.empty:
            return pd.Series(dtype=str, index=df.index)
        
        # Calculate returns (percentage change)
        close = df['close']
        returns = close.pct_change()
        
        # Calculate rolling standard deviation of returns
        stddev = returns.rolling(window=lookback).std()
        
        # Handle NaN values (first lookback-1 bars will be NaN)
        # Fill with first valid StdDev value or use 'normal' regime
        if stddev.isna().any():
            first_valid_idx = stddev.first_valid_index()
            if first_valid_idx is not None:
                first_valid_stddev = stddev.loc[first_valid_idx]
                stddev = stddev.fillna(first_valid_stddev)
            else:
                # No valid StdDev values, return all 'normal'
                return pd.Series('normal', index=df.index)
        
        # Calculate percentile thresholds on full dataset
        high_threshold_value = stddev.quantile(high_threshold)
        low_threshold_value = stddev.quantile(low_threshold)
        
        # Classify each bar
        regime_series = pd.Series('normal', index=df.index, dtype=str)
        regime_series[stddev > high_threshold_value] = 'high'
        regime_series[stddev <= low_threshold_value] = 'low'
        
        # Ensure all values are valid regimes
        regime_series = regime_series.fillna('normal')
        
        return regime_series

