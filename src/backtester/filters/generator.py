"""
Generate filter configurations from filter names.

Creates cartesian product of all filter regimes plus baseline (no filters).

Quick Start:
    from backtester.filters.generator import generate_filter_configurations
    
    # Single filter
    configs = generate_filter_configurations(['volatility_regime_atr'])
    # Returns: [
    #   {'volatility_regime_atr': 'high'},
    #   {'volatility_regime_atr': 'normal'},
    #   {'volatility_regime_atr': 'low'},
    #   {'volatility_regime_atr': 'none'},
    #   {}  # baseline
    # ]
    
    # Multiple filters (cartesian product)
    configs = generate_filter_configurations(['volatility_regime_atr', 'trend_regime'])
    # Returns all combinations + baseline
"""

from typing import List, Dict
from itertools import product
from backtester.filters.registry import get_filter, list_filters


def generate_filter_configurations(filter_names: List[str]) -> List[Dict[str, str]]:
    """
    Generate all filter configurations from filter names.
    
    For each filter, generates configs for each regime + 'none'.
    Creates cartesian product for multiple filters + baseline.
    
    Args:
        filter_names: List of filter names from config (e.g., ['volatility_regime_atr'])
    
    Returns:
        List of filter configurations.
        Each config is a dict mapping filter_name -> regime (or 'none')
        Always includes baseline: {} (empty dict = no filters applied)
    
    Raises:
        ValueError: If any filter name is not found in registry
    
    Example:
        Input: ['volatility_regime_atr']  # regimes: ['high', 'normal', 'low']
        Output: [
            {'volatility_regime_atr': 'high'},
            {'volatility_regime_atr': 'normal'},
            {'volatility_regime_atr': 'low'},
            {'volatility_regime_atr': 'none'},
            {}  # baseline - no filters
        ]
        
        Input: ['volatility_regime_atr', 'trend_regime_sma']  
        # volatility_regime_atr: ['high', 'normal', 'low']
        # trend_regime_sma: ['uptrend', 'downtrend']
        Output: [
            {'volatility_regime_atr': 'high', 'trend_regime_sma': 'uptrend'},
            {'volatility_regime_atr': 'high', 'trend_regime_sma': 'downtrend'},
            {'volatility_regime_atr': 'high', 'trend_regime_sma': 'none'},
            {'volatility_regime_atr': 'normal', 'trend_regime_sma': 'uptrend'},
            # ... cartesian product of all regimes + 'none' for each
            {}  # baseline - no filters
        ]
    """
    if not filter_names:
        return [{}]  # Only baseline if no filters
    
    # Get filter classes and their regimes
    filter_regimes = {}
    for filter_name in filter_names:
        filter_class = get_filter(filter_name)
        if filter_class is None:
            raise ValueError(f"Filter '{filter_name}' not found in registry. "
                           f"Available filters: {list_filters()}")
        
        # Get regimes from filter class (create instance to access class attributes)
        filter_instance = filter_class()
        regimes = filter_instance.regimes
        
        # Add 'none' to regimes for this filter (allows disabling individual filters)
        regimes_with_none = list(regimes) + ['none']
        filter_regimes[filter_name] = regimes_with_none
    
    # Generate cartesian product of all filter regimes
    filter_names_list = list(filter_regimes.keys())
    regimes_list = [filter_regimes[name] for name in filter_names_list]
    
    configurations = []
    
    # Generate all combinations
    for regime_combo in product(*regimes_list):
        config = dict(zip(filter_names_list, regime_combo))
        
        # Skip config where all filters are 'none' (we'll add baseline separately)
        if not all(regime == 'none' for regime in regime_combo):
            configurations.append(config)
    
    # Always add baseline (no filters applied) as empty dict
    configurations.append({})
    
    return configurations
