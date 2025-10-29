"""
Indicator Library Package

This package provides a unified interface for computing technical indicators,
wrapping the 'ta' library and supporting custom indicators. All indicators
are designed to be pre-computed before backtests for optimal performance.

Quick Start:
    from indicators import IndicatorLibrary, IndicatorSpec
    
    # Create library instance
    lib = IndicatorLibrary()
    
    # Define indicators your strategy needs
    specs = [
        IndicatorSpec('SMA', {'timeperiod': 20}, 'SMA_20'),
        IndicatorSpec('RSI', {'timeperiod': 14}, 'RSI_14'),
    ]
    
    # Compute and add to DataFrame
    enriched_df = lib.compute_all(df, specs)

Package Contents:
    - IndicatorLibrary: Main class for computing indicators
    - IndicatorSpec: Dataclass for specifying indicator requirements
    - CustomIndicator: Base class for custom indicators
    - register_custom_indicator(): Register your own indicator functions

Supported Built-in Indicators:
    - SMA: Simple Moving Average
    - EMA: Exponential Moving Average
    - RSI: Relative Strength Index
    - MACD: Moving Average Convergence Divergence
    - BBANDS: Bollinger Bands

Example Usage:
    See individual module docstrings for detailed examples:
    - indicators.library: Main computation logic
    - indicators.base: Base classes and custom indicator registration
"""

from indicators.library import IndicatorLibrary
from indicators.base import (
    IndicatorSpec,
    CustomIndicator,
    register_custom_indicator,
    get_custom_indicator,
    list_custom_indicators
)

__all__ = [
    'IndicatorLibrary',
    'IndicatorSpec',
    'CustomIndicator',
    'register_custom_indicator',
    'get_custom_indicator',
    'list_custom_indicators',
]
