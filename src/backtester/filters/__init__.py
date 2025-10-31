"""
Filter system for walk-forward optimization.

Filters allow filtering trades by market regimes (e.g., volatility regimes).
All filters are self-contained (logic + parameters in filter file).

Quick Start:
    from backtester.filters import get_filter, generate_filter_configurations
    
    # Get a filter by name
    filter_class = get_filter('volatility_regime_atr')
    instance = filter_class()
    classification = instance.compute_classification(df)
    
    # Generate filter configurations
    configs = generate_filter_configurations(['volatility_regime_atr'])
    # Returns: [{'volatility_regime_atr': 'high'}, {'volatility_regime_atr': 'normal'}, 
    #           {'volatility_regime_atr': 'low'}, {}]  # {} is baseline (no filters)
"""

# Import implementations to trigger auto-registration
from backtester.filters import implementations  # noqa

# Public API
from backtester.filters.base import BaseFilter
from backtester.filters.registry import (
    register_filter,
    get_filter,
    list_filters,
    get_all_filters
)
from backtester.filters.generator import generate_filter_configurations
from backtester.filters.applicator import apply_filters_to_trades

__all__ = [
    'BaseFilter',
    'register_filter',
    'get_filter',
    'list_filters',
    'get_all_filters',
    'generate_filter_configurations',
    'apply_filters_to_trades',
]

