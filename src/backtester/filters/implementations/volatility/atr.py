"""
ATR-based volatility regime filter.

Classifies market bars as high, normal, or low volatility based on Average True Range (ATR).
Uses percentile thresholds computed on the full dataset for performance.
"""

import pandas as pd
import numpy as np
from backtester.filters.base import BaseFilter


class VolatilityRegimeATR(BaseFilter):
    """
    ATR-based volatility regime filter.
    
    Classifies each bar as:
    - 'high': ATR value above high_threshold percentile (default 75th)
    - 'low': ATR value below low_threshold percentile (default 25th)
    - 'normal': ATR value between thresholds
    
    Uses full dataset for percentile calculation (most performant approach).
    """
    
    name = 'volatility_regime_atr'
    regimes = ['high', 'normal', 'low']
    matching = 'entry'  # Filter trades based on entry regime
    
    default_params = {
        'lookback': 14,  # ATR period
        'high_threshold': 0.75,  # 75th percentile for high volatility
        'low_threshold': 0.25,   # 25th percentile for low volatility
        'threshold_method': 'full_dataset'  # Use full dataset for percentiles
    }
    
    def compute_classification(self, df: pd.DataFrame, params: dict = None) -> pd.Series:
        """
        Compute ATR-based volatility regime classification for each bar.
        
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
        
        # Calculate ATR
        # ATR = Average of True Range over lookback period
        # True Range = max(high - low, abs(high - prev_close), abs(low - prev_close))
        high = df['high']
        low = df['low']
        close = df['close']
        
        # Calculate true range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Calculate ATR as rolling mean of true range
        atr = true_range.rolling(window=lookback).mean()
        
        # Handle NaN values (first lookback-1 bars will be NaN)
        # Fill with first valid ATR value or use 'normal' regime
        if atr.isna().any():
            first_valid_idx = atr.first_valid_index()
            if first_valid_idx is not None:
                first_valid_atr = atr.loc[first_valid_idx]
                atr = atr.fillna(first_valid_atr)
            else:
                # No valid ATR values, return all 'normal'
                return pd.Series('normal', index=df.index)
        
        # Calculate percentile thresholds on full dataset
        high_threshold_value = atr.quantile(high_threshold)
        low_threshold_value = atr.quantile(low_threshold)
        
        # Classify each bar
        regime_series = pd.Series('normal', index=df.index, dtype=str)
        regime_series[atr > high_threshold_value] = 'high'
        regime_series[atr <= low_threshold_value] = 'low'
        
        # Ensure all values are valid regimes
        regime_series = regime_series.fillna('normal')
        
        return regime_series

