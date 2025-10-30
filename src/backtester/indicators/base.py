"""
Base classes and interfaces for indicator computation.

This module defines the abstract interfaces that all indicators must implement.
It provides the foundation for both built-in TA-Lib indicators and custom indicators.

Quick Start:
    from indicators.base import IndicatorSpec, CustomIndicator
    
    # Define indicator specification
    spec = IndicatorSpec('SMA', {'timeperiod': 20}, 'SMA_20')
    
    # Create custom indicator
    def my_custom_indicator(df, params):
        return df['close'].rolling(window=params['period']).mean()
    
    custom = CustomIndicator('MY_SMA', my_custom_indicator)

Common Patterns:
    # Pattern 1: Using IndicatorSpec for built-in indicators
    from indicators.base import IndicatorSpec
    
    # Single indicator
    spec = IndicatorSpec(
        indicator_type='RSI',
        params={'timeperiod': 14},
        column_name='RSI_14'
    )
    
    # Pattern 2: Registering custom indicators
    from indicators.base import CustomIndicator, register_custom_indicator
    
    def bollinger_squeeze(df, params):
        '''Custom indicator: Bollinger Band width'''
        from ta.volatility import BollingerBands
        bb = BollingerBands(close=df['close'], window=params['window'])
        return bb.bollinger_wband()
    
    register_custom_indicator('BB_SQUEEZE', bollinger_squeeze)
    
    spec = IndicatorSpec('BB_SQUEEZE', {'window': 20}, 'bb_width')

Extending:
    To create a custom indicator:
    1. Define a function that takes (df, params) and returns a pandas Series/DataFrame
    2. Register it using register_custom_indicator(name, function)
    3. Use IndicatorSpec to reference it just like built-in indicators
    
    Example:
        def ema_cross(df, params):
        '''Detects when fast EMA crosses above slow EMA'''
        import pandas as pd
        fast_ema = df['close'].ewm(span=params['fast']).mean()
        slow_ema = df['close'].ewm(span=params['slow']).mean()
        return (fast_ema > slow_ema).astype(int)
    
        register_custom_indicator('EMA_CROSS', ema_cross)
"""

from typing import Dict, Any, Callable, Union, Optional
from dataclasses import dataclass
import pandas as pd


@dataclass
class IndicatorSpec:
    """
    Specification for an indicator computation.
    
    Attributes:
        indicator_type: Name of indicator (e.g., 'SMA', 'RSI', or custom name)
        params: Dictionary of parameters for the indicator
        column_name: Name to use for the resulting column in DataFrame
    """
    indicator_type: str
    params: Dict[str, Any]
    column_name: str
    
    def __post_init__(self):
        """Validate specification."""
        if not isinstance(self.indicator_type, str) or not self.indicator_type:
            raise ValueError("indicator_type must be a non-empty string")
        if not isinstance(self.params, dict):
            raise ValueError("params must be a dictionary")
        if not isinstance(self.column_name, str) or not self.column_name:
            raise ValueError("column_name must be a non-empty string")


class CustomIndicator:
    """
    Wrapper for custom indicator functions.
    
    Custom indicators are user-defined functions that compute technical indicators
    from OHLCV DataFrames.
    """
    
    def __init__(self, name: str, compute_func: Callable[[pd.DataFrame, Dict[str, Any]], Union[pd.Series, pd.DataFrame]]):
        """
        Initialize custom indicator.
        
        Args:
            name: Unique name for the indicator
            compute_func: Function that takes (df, params) and returns Series/DataFrame
                - df: DataFrame with OHLCV columns (open, high, low, close, volume)
                - params: Dictionary of indicator parameters
                - Returns: pandas Series or DataFrame
        
        Example:
            def my_sma(df, params):
                return df['close'].rolling(window=params['period']).mean()
            
            custom = CustomIndicator('MY_SMA', my_sma)
        """
        if not isinstance(name, str) or not name:
            raise ValueError("name must be a non-empty string")
        if not callable(compute_func):
            raise ValueError("compute_func must be callable")
        
        self.name = name
        self.compute_func = compute_func
    
    def compute(self, df: pd.DataFrame, params: Dict[str, Any]) -> Union[pd.Series, pd.DataFrame]:
        """
        Compute the indicator.
        
        Args:
            df: OHLCV DataFrame
            params: Indicator parameters
        
        Returns:
            Series or DataFrame with indicator values
        """
        return self.compute_func(df, params)


# Registry for custom indicators
_custom_indicators: Dict[str, CustomIndicator] = {}


def register_custom_indicator(name: str, compute_func: Callable[[pd.DataFrame, Dict[str, Any]], Union[pd.Series, pd.DataFrame]]) -> None:
    """
    Register a custom indicator function.
    
    Args:
        name: Unique name for the indicator (must not conflict with built-in names)
        compute_func: Function that computes the indicator
        
    Example:
        def volume_sma(df, params):
            return df['volume'].rolling(window=params['period']).mean()
        
        register_custom_indicator('VOLUME_SMA', volume_sma)
        
        # Now can use it like:
        spec = IndicatorSpec('VOLUME_SMA', {'period': 20}, 'vol_sma_20')
    """
    if name in _custom_indicators:
        raise ValueError(f"Custom indicator '{name}' is already registered")
    
    _custom_indicators[name] = CustomIndicator(name, compute_func)


def get_custom_indicator(name: str) -> Optional[CustomIndicator]:
    """
    Get a registered custom indicator.
    
    Args:
        name: Indicator name
    
    Returns:
        CustomIndicator instance or None if not found
    """
    return _custom_indicators.get(name)


def list_custom_indicators() -> list:
    """
    List all registered custom indicators.
    
    Returns:
        List of indicator names
    """
    return list(_custom_indicators.keys())
