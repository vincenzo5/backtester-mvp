"""
Base classes and interfaces for filter computation.

Filters classify market regimes (e.g., volatility regimes) for each bar in the DataFrame.
Trade filtering happens post-execution based on these classifications.

Quick Start:
    # BaseFilter is defined in this file
    
    class MyFilter(BaseFilter):
        name = 'my_filter'
        regimes = ['high', 'low']
        matching = 'entry'
        default_params = {'lookback': 14}
        
        def compute_classification(self, df, params=None):
            # Your classification logic
            return pd.Series(['high', 'low', ...], index=df.index)

Common Patterns:
    # Pattern 1: Basic filter
    class VolatilityFilter(BaseFilter):
        name = 'volatility_regime'
        regimes = ['high', 'normal', 'low']
        matching = 'entry'
        default_params = {'lookback': 14, 'high_threshold': 0.75}
        
        def compute_classification(self, df, params=None):
            params = params or self.default_params
            # Compute volatility measure
            # Classify based on thresholds
            return regime_series

Extending:
    To create a new filter:
    1. Inherit from BaseFilter
    2. Define name, regimes, matching, default_params as class attributes
    3. Implement compute_classification() to return Series with regime labels per bar
    4. Register in implementations/__init__.py
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import pandas as pd


class BaseFilter(ABC):
    """
    Abstract base class for all trade filters.
    
    Filters classify market regimes for each bar in a DataFrame.
    The classifications are then used to filter trades post-execution.
    
    Each filter is self-contained with its own:
    - name: Identifier used in configuration
    - regimes: List of regime labels this filter produces
    - matching: How to match trades ('entry', 'both', 'either')
    - default_params: Default parameters for computation
    - compute_classification(): Method to compute regime labels
    
    Example:
        class VolatilityRegimeATR(BaseFilter):
            name = 'volatility_regime_atr'
            regimes = ['high', 'normal', 'low']
            matching = 'entry'
            default_params = {'lookback': 14, 'high_threshold': 0.75, 'low_threshold': 0.25}
            
            def compute_classification(self, df: pd.DataFrame, params: Dict[str, Any] = None) -> pd.Series:
                params = params or self.default_params
                # Compute ATR, classify, return Series
                ...
    """
    
    # Class attributes that must be defined by subclasses
    name: str = ""
    regimes: List[str] = []
    matching: str = 'entry'  # 'entry', 'both', or 'either'
    default_params: Dict[str, Any] = {}
    
    def __init__(self):
        """Initialize filter instance."""
        # Validate that subclass defined required attributes
        if not self.name:
            raise ValueError(f"{self.__class__.__name__} must define 'name' attribute")
        if not self.regimes:
            raise ValueError(f"{self.__class__.__name__} must define 'regimes' attribute")
        if self.matching not in ['entry', 'both', 'either']:
            raise ValueError(f"{self.__class__.__name__}.matching must be 'entry', 'both', or 'either'")
    
    @abstractmethod
    def compute_classification(self, df: pd.DataFrame, params: Dict[str, Any] = None) -> pd.Series:
        """
        Compute regime classification for each bar in the DataFrame.
        
        Args:
            df: OHLCV DataFrame with datetime index
                Must have columns: open, high, low, close, volume
            params: Optional parameter dictionary to override default_params
        
        Returns:
            pandas Series with regime labels, indexed by DataFrame's datetime index
            Values should be one of the filter's regimes (e.g., 'high', 'normal', 'low')
        
        Example:
            Input DataFrame:
                datetime          | open | high | low | close | volume
                2024-01-15 10:00 | 100  | 105  | 99  | 103   | 1000
                2024-01-15 11:00 | 103  | 107  | 102 | 106   | 1100
            
            Output Series:
                2024-01-15 10:00    'normal'
다음 2024-01-15 11:00    'high'
                
        Notes:
            - Index must match df.index exactly
            - Missing values should be filled (e.g., with 'normal' as default)
            - Classification should be deterministic based on DataFrame data
        """
        pass
